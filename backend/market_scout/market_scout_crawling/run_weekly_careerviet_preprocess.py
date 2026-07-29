
from __future__ import annotations

import argparse
import json
import math
import re
import statistics
import subprocess
import sys
import unicodedata
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.market_scout.repositories.salary_benchmark.salary_repository import build_firestore_client, load_env_file
from backend.market_scout.services.salary_benchmark.salary_competitive_prediction_service import (
    SalaryCompetitivePredictionService,
)

MILLION_VND = 1_000_000
RANGE_RE = re.compile(r"(?P<min>\d+(?:[\.,]\d+)?)\s*(?:tr|trieu|m|million)?\s*(?:-|\u2013|\u2014|den|to)\s*(?P<max>\d+(?:[\.,]\d+)?)\s*(?:tr|trieu|m|million)?", re.IGNORECASE)
ABOVE_RE = re.compile(r"(?:tren|from|tu)\s*(?P<min>\d+(?:[\.,]\d+)?)\s*(?:tr|trieu|m|million)?", re.IGNORECASE)
UP_TO_RE = re.compile(r"(?:len den|upto|up to|toi da)\s*(?P<max>\d+(?:[\.,]\d+)?)\s*(?:tr|trieu|m|million)?", re.IGNORECASE)
EXPERIENCE_RE = re.compile(r"(?P<years>\d{1,2})\s*(?:nam|year|years)", re.IGNORECASE)

OUTPUT_FIELDS = (
    "job_id",
    "source_job_id",
    "job_url",
    "canonical_job_url",
    "job_title",
    "title",
    "company",
    "Công ty",
    "Ngành nghề",
    "Cấp bậc",
    "Mô tả Công việc",
    "Yêu cầu Công việc",
    "Thông tin khác",
    "Phúc lợi",
    "Địa điểm làm việc",
    "min_experience",
    "min_salary",
    "max_salary",
    "source",
    "scope",
    "batch_id",
    "discovered_at",
    "crawled_at",
)


@dataclass
class PreprocessSummary:
    status: str
    batch_id: str
    source_collection: str
    processed_collection: str
    embedding_collection: str
    raw_records: int = 0
    written_processed_records: int = 0
    dropped_records: int = 0
    salary_range_records: int = 0
    competitive_salary_records: int = 0
    above_salary_records: int = 0
    up_to_salary_records: int = 0
    skipped_existing_records: int = 0
    embed_result: dict[str, Any] | None = None
    estimate_bounds_result: dict[str, Any] | None = None
    build_index_result: dict[str, Any] | None = None
    dry_run: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Preprocess weekly CareerViet raw jobs and update salary benchmark vectors.")
    parser.add_argument("--batch-id", default=None, help="Batch id, for example 2026W31. Defaults to current ISO week.")
    parser.add_argument("--source-collection", default=None)
    parser.add_argument("--processed-collection", default=None)
    parser.add_argument("--embedding-collection", default="data_vector_embeddings")
    parser.add_argument("--error-collection", default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--batch-size", type=int, default=400)
    parser.add_argument("--competitive-salary-method", choices=("xgboost", "batch_median"), default="xgboost")
    parser.add_argument("--model-artifact-dir", default=None, help="Directory containing salary_prediction_xgb.pkl and model_features.joblib.")
    parser.add_argument("--open-ended-factor", type=float, default=1.44)
    parser.add_argument("--skip-embedding", action="store_true")
    parser.add_argument("--skip-estimate-bounds", action="store_true")
    parser.add_argument("--skip-build-index", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--allow-empty", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


def default_batch_id(now: datetime | None = None) -> str:
    current = now or datetime.now(timezone.utc)
    iso_year, iso_week, _ = current.isocalendar()
    return f"{iso_year}W{iso_week:02d}"


def main() -> None:
    load_env_file()
    args = parse_args()
    batch_id = args.batch_id or default_batch_id()
    source_collection = args.source_collection or f"careerviet_jobs_weekly_{batch_id}"
    processed_collection = args.processed_collection or f"data_for_vectorize_{batch_id}"
    error_collection = args.error_collection or f"data_for_vectorize_errors_{batch_id}"

    db = build_firestore_client()
    raw_records = load_raw_records(db, source_collection, limit=args.limit)
    salary_prior = build_salary_prior(raw_records)
    competitive_predictor = (
        SalaryCompetitivePredictionService(artifact_dir=args.model_artifact_dir)
        if args.competitive_salary_method == "xgboost"
        else None
    )

    summary = PreprocessSummary(
        status="success",
        batch_id=batch_id,
        source_collection=source_collection,
        processed_collection=processed_collection,
        embedding_collection=args.embedding_collection,
        raw_records=len(raw_records),
        dry_run=args.dry_run,
    )

    if not raw_records and not args.allow_empty:
        summary.status = "failed"
        print(json.dumps(summary.to_dict(), ensure_ascii=False, indent=2))
        raise SystemExit(2)

    processed_records: list[tuple[str, dict[str, Any]]] = []
    error_records: list[tuple[str, dict[str, Any]]] = []

    for doc_id, raw in raw_records:
        normalized = normalize_record(doc_id, raw, batch_id=batch_id)
        salary_result = parse_salary_bounds(
            raw,
            normalized_record=normalized,
            salary_prior=salary_prior,
            open_ended_factor=args.open_ended_factor,
            competitive_salary_method=args.competitive_salary_method,
            competitive_predictor=competitive_predictor,
        )
        if salary_result is None:
            summary.dropped_records += 1
            error_records.append((doc_id, build_error_record(doc_id, raw, batch_id, "unsupported_or_missing_salary")))
            continue

        min_salary, max_salary, salary_method = salary_result
        normalized["min_salary"] = min_salary
        normalized["max_salary"] = max_salary
        normalized["salary_processing_method"] = salary_method
        normalized["salary_processing_updated_at"] = datetime.now(timezone.utc).isoformat()

        if salary_method == "range":
            summary.salary_range_records += 1
        elif salary_method.startswith("competitive_"):
            summary.competitive_salary_records += 1
        elif salary_method == "above_factor":
            summary.above_salary_records += 1
        elif salary_method == "up_to_factor":
            summary.up_to_salary_records += 1

        processed_records.append((normalized["job_id"], {field: to_firestore_value(normalized.get(field)) for field in OUTPUT_FIELDS if field in normalized}))

    if not args.dry_run:
        summary.written_processed_records = write_records(db, processed_collection, processed_records, batch_size=args.batch_size)
        write_records(db, error_collection, error_records, batch_size=args.batch_size)
    else:
        summary.written_processed_records = 0

    if processed_records and not args.skip_embedding:
        summary.embed_result = run_json_step(
            [
                sys.executable,
                str(PROJECT_ROOT / "backend/market_scout/local_scripts/salary_benchmark/run_embedJobs.py"),
                "--source-collection",
                processed_collection,
                "--vector-collection",
                args.embedding_collection,
                "--verbose",
                *( ["--dry-run"] if args.dry_run else [] ),
            ],
            verbose=args.verbose,
        )

    if processed_records and not args.skip_estimate_bounds:
        summary.estimate_bounds_result = run_json_step(
            [
                sys.executable,
                str(PROJECT_ROOT / "backend/market_scout/local_scripts/salary_benchmark/run_estimateSalaryBounds.py"),
                "--collection",
                args.embedding_collection,
                "--source-collection-filter",
                processed_collection,
                *( ["--dry-run"] if args.dry_run else [] ),
            ],
            verbose=args.verbose,
        )

    if processed_records and not args.skip_build_index:
        summary.build_index_result = run_json_step(
            [
                sys.executable,
                str(PROJECT_ROOT / "backend/market_scout/local_scripts/salary_benchmark/run_buildSalaryIndex.py"),
                "--collection",
                args.embedding_collection,
                "--source-collection-filter",
                processed_collection,
                *( ["--dry-run"] if args.dry_run else [] ),
            ],
            verbose=args.verbose,
        )

    if not processed_records and not args.allow_empty:
        summary.status = "failed"
        print(json.dumps(summary.to_dict(), ensure_ascii=False, indent=2))
        raise SystemExit(3)

    print(json.dumps(summary.to_dict(), ensure_ascii=False, indent=2))


def load_raw_records(db: Any, collection_name: str, *, limit: int | None) -> list[tuple[str, dict[str, Any]]]:
    query = db.collection(collection_name).order_by("__name__")
    if limit is not None:
        query = query.limit(limit)
    records: list[tuple[str, dict[str, Any]]] = []
    for snapshot in query.stream():
        records.append((snapshot.id, snapshot.to_dict() or {}))
    return records


def normalize_record(document_id: str, raw: dict[str, Any], *, batch_id: str) -> dict[str, Any]:
    job_id = clean_text(first_value(raw, "job_id", "source_job_id")) or document_id
    job_url = clean_text(first_value(raw, "job_url", "href", "url"))
    job_title = clean_text(first_value(raw, "job_title", "title")) or ""
    company = clean_text(first_value(raw, "company", "Công ty", "Cong ty"))
    locations = normalize_locations(first_value(raw, "Địa điểm làm việc", "Dia diem lam viec", "location", "locations"))

    record = {
        "job_id": job_id,
        "source_job_id": clean_text(first_value(raw, "source_job_id")) or job_id,
        "job_url": job_url,
        "canonical_job_url": canonical_url(job_url),
        "job_title": job_title,
        "title": job_title,
        "company": company,
        "Công ty": company,
        "Ngành nghề": first_value(raw, "Ngành nghề", "Nganh nghe", "industry"),
        "Cấp bậc": first_value(raw, "Cấp bậc", "Cap bac", "level"),
        "Mô tả Công việc": first_value(raw, "Mô tả Công việc", "Mo ta Cong viec", "description"),
        "Yêu cầu Công việc": first_value(raw, "Yêu cầu Công việc", "Yeu Cau Cong Viec", "requirements"),
        "Thông tin khác": first_value(raw, "Thông tin khác", "Thong tin khac", "other_info"),
        "Phúc lợi": first_value(raw, "Phúc lợi", "Phuc loi", "benefits"),
        "Địa điểm làm việc": locations,
        "min_experience": parse_min_experience(first_value(raw, "Kinh nghiệm", "Kinh nghiem", "experience", "min_experience")),
        "source": clean_text(first_value(raw, "source")) or "careerviet",
        "scope": clean_text(first_value(raw, "scope")),
        "batch_id": clean_text(first_value(raw, "batch_id")) or batch_id,
        "discovered_at": first_value(raw, "discovered_at"),
        "crawled_at": first_value(raw, "crawled_at"),
    }
    return record


def build_salary_prior(raw_records: list[tuple[str, dict[str, Any]]]) -> tuple[float, float]:
    mins: list[float] = []
    maxs: list[float] = []
    for _, raw in raw_records:
        parsed = parse_range_salary(salary_text(raw))
        if parsed is None:
            continue
        min_salary, max_salary = parsed
        if min_salary > 0 and max_salary >= min_salary:
            mins.append(min_salary)
            maxs.append(max_salary)
    if len(mins) >= 2 and len(maxs) >= 2:
        return round(statistics.median(mins), 2), round(statistics.median(maxs), 2)
    return 12.0, 20.0


def parse_salary_bounds(
    raw: dict[str, Any],
    *,
    normalized_record: dict[str, Any] | None = None,
    salary_prior: tuple[float, float],
    open_ended_factor: float,
    competitive_salary_method: str = "xgboost",
    competitive_predictor: SalaryCompetitivePredictionService | None = None,
) -> tuple[float, float, str] | None:
    text = salary_text(raw)
    normalized = normalize_ascii(text)
    if not normalized:
        return None

    range_salary = parse_range_salary(text)
    if range_salary is not None:
        min_salary, max_salary = range_salary
        return min_salary, max_salary, "range"

    if "canh tranh" in normalized or "competitive" in normalized or "thoa thuan" in normalized:
        if competitive_salary_method == "xgboost":
            if competitive_predictor is None or normalized_record is None:
                raise ValueError("XGBoost competitive salary prediction requires a predictor and normalized record.")
            prediction = competitive_predictor.predict_record(normalized_record)
            return prediction.min_salary, prediction.max_salary, prediction.method
        min_salary, max_salary = salary_prior
        return min_salary, max_salary, "competitive_batch_median"

    up_to = UP_TO_RE.search(normalized)
    if up_to:
        max_salary = parse_number(up_to.group("max"))
        if max_salary is None or max_salary <= 0:
            return None
        min_salary = max(round(max_salary / open_ended_factor, 2), 1.0)
        return min_salary, max_salary, "up_to_factor"

    above = ABOVE_RE.search(normalized)
    if above:
        min_salary = parse_number(above.group("min"))
        if min_salary is None or min_salary <= 0:
            return None
        max_salary = round(min_salary * open_ended_factor, 2)
        return min_salary, max_salary, "above_factor"

    return None


def parse_range_salary(text: Any) -> tuple[float, float] | None:
    normalized = normalize_ascii(text)
    match = RANGE_RE.search(normalized)
    if not match:
        return None
    min_salary = parse_number(match.group("min"))
    max_salary = parse_number(match.group("max"))
    if min_salary is None or max_salary is None or min_salary <= 0 or max_salary <= 0:
        return None
    if min_salary > max_salary:
        min_salary, max_salary = max_salary, min_salary
    return round(min_salary, 2), round(max_salary, 2)


def salary_text(raw: dict[str, Any]) -> str:
    return clean_text(first_value(raw, "Lương", "Luong", "salary", "salary_text")) or ""


def parse_min_experience(value: Any) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, int | float):
        if isinstance(value, float) and math.isnan(value):
            return None
        return int(value)
    text = normalize_ascii(value)
    match = EXPERIENCE_RE.search(text)
    if match:
        return int(match.group("years"))
    number = re.search(r"\d{1,2}", text)
    return int(number.group(0)) if number else None


def build_error_record(document_id: str, raw: dict[str, Any], batch_id: str, reason: str) -> dict[str, Any]:
    return {
        "source_document_id": document_id,
        "job_id": clean_text(first_value(raw, "job_id", "source_job_id")) or document_id,
        "batch_id": clean_text(first_value(raw, "batch_id")) or batch_id,
        "reason": reason,
        "salary_text": salary_text(raw),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def write_records(db: Any, collection_name: str, records: list[tuple[str, dict[str, Any]]], *, batch_size: int) -> int:
    written = 0
    for start in range(0, len(records), batch_size):
        batch = db.batch()
        chunk = records[start : start + batch_size]
        for doc_id, record in chunk:
            batch.set(db.collection(collection_name).document(str(doc_id)), record, merge=True)
        if chunk:
            batch.commit()
            written += len(chunk)
    return written


def run_json_step(command: list[str], *, verbose: bool) -> dict[str, Any]:
    if verbose:
        print("Running:", " ".join(command), flush=True)
    completed = subprocess.run(command, check=True, text=True, capture_output=True)
    if verbose and completed.stderr:
        print(completed.stderr, file=sys.stderr, flush=True)
    stdout = completed.stdout.strip()
    if verbose and stdout:
        print(stdout, flush=True)
    if not stdout:
        return {}
    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        return {"raw_stdout": stdout}


def first_value(data: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in data and data[key] not in (None, ""):
            return data[key]
    normalized_lookup = {normalize_ascii(key): value for key, value in data.items() if value not in (None, "")}
    for key in keys:
        value = normalized_lookup.get(normalize_ascii(key))
        if value not in (None, ""):
            return value
    return None


def normalize_locations(value: Any) -> list[str]:
    if value is None:
        return []
    values = value if isinstance(value, list) else [value]
    result: list[str] = []
    seen: set[str] = set()
    for item in values:
        if isinstance(item, dict):
            candidates = item.values()
        else:
            candidates = [item]
        for candidate in candidates:
            text = clean_text(candidate)
            if not text:
                continue
            key = text.casefold()
            if key in seen:
                continue
            seen.add(key)
            result.append(text)
    return result


def canonical_url(value: str | None) -> str | None:
    if not value:
        return None
    return value.split("?", 1)[0].strip()


def clean_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, list):
        value = ", ".join(str(item) for item in value if item not in (None, ""))
    elif isinstance(value, dict):
        value = " ".join(str(item) for item in value.values() if item not in (None, ""))
    text = " ".join(str(value).split())
    return text or None


def parse_number(value: str) -> float | None:
    try:
        return float(value.replace(",", "."))
    except (TypeError, ValueError):
        return None


def normalize_ascii(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).replace("\u0111", "d").replace("\u0110", "D")
    text = unicodedata.normalize("NFD", text)
    text = "".join(character for character in text if unicodedata.category(character) != "Mn")
    return " ".join(text.casefold().split())


def to_firestore_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): to_firestore_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [to_firestore_value(v) for v in value]
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


if __name__ == "__main__":
    main()
