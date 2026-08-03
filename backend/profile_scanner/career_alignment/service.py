import datetime
import unicodedata

from assessments.repository import get_latest_assessment_result
from canonical_profile.repository import get_canonical_profile
from career_alignment.repository import save_alignment_result
from career_alignment.schemas import CareerAlignmentResponse
from holland.repository import get_latest_holland_assessment
from profile_analysis.benchmark import ROLE_BENCHMARKS
from core.config import logger
from guidance.service import generate_alignment_narrative


RULE_VERSION = "career-alignment-v2"
RIASEC_DIMENSIONS = ("R", "I", "A", "S", "E", "C")


def utc_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def normalize_role(value: str | None) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    return " ".join(normalized.casefold().replace("_", " ").replace("-", " ").split())


def resolve_profile_benchmark(profile: dict | None) -> dict | None:
    if not profile:
        return None

    snapshot = profile.get("benchmark_snapshot")
    if isinstance(snapshot, dict):
        scoring_criteria = snapshot.get("scoring_criteria")
        return {
            **(scoring_criteria if isinstance(scoring_criteria, dict) else {}),
            **snapshot,
        }

    benchmark_id = str(profile.get("benchmark_profile_id") or "")
    if benchmark_id in ROLE_BENCHMARKS:
        return ROLE_BENCHMARKS[benchmark_id]

    target_role = normalize_role(profile.get("target_role"))
    if not target_role:
        return None
    for slug, benchmark in ROLE_BENCHMARKS.items():
        aliases = [slug, benchmark.get("label", ""), *benchmark.get("aliases", [])]
        if target_role in {normalize_role(alias) for alias in aliases}:
            return benchmark
    return None


def normalize_distribution(values: dict[str, float]) -> dict[str, float]:
    clean = {dimension: max(float(values.get(dimension, 0.0)), 0.0) for dimension in RIASEC_DIMENSIONS}
    total = sum(clean.values())
    if total <= 0:
        return {dimension: 0.0 for dimension in RIASEC_DIMENSIONS}
    return {dimension: value / total for dimension, value in clean.items()}


def compute_holland_alignment(
    holland_scores: dict[str, float],
    occupation_scores: dict[str, float],
) -> float:
    user_vector = normalize_distribution(holland_scores)
    role_vector = normalize_distribution(occupation_scores)
    distance = sum(abs(user_vector[key] - role_vector[key]) for key in RIASEC_DIMENSIONS)
    return round(max(0.0, min(100.0, 100.0 * (1.0 - distance / 2.0))), 2)


def classify_alignment(cv_readiness: float, holland_alignment: float) -> tuple[str, str]:
    if cv_readiness >= 70 and holland_alignment >= 70:
        return "aligned", "low"
    if cv_readiness >= 70 and holland_alignment < 50:
        return "interest_conflict", "high"
    if cv_readiness < 50 and holland_alignment >= 70:
        return "readiness_gap", "medium"
    if cv_readiness < 50 and holland_alignment < 50:
        return "exploration_advised", "high"
    return "mixed_or_uncertain", "medium"


def build_recommendations(
    state: str,
    target_role: str,
    mi_dimensions: list[str],
) -> list[str]:
    recommendations = {
        "aligned": [f"Tiếp tục tích lũy bằng chứng dự án và kinh nghiệm cho vị trí {target_role}."],
        "interest_conflict": [
            f"Bạn có bằng chứng năng lực cho {target_role} nhưng mức hứng thú nghề nghiệp thấp; nên trải nghiệm một dự án ngắn hoặc phỏng vấn người đang làm nghề trước khi cam kết dài hạn."
        ],
        "readiness_gap": [
            f"Sở thích phù hợp với {target_role}, nhưng CV chưa có đủ bằng chứng; nên ưu tiên project, internship và kỹ năng thiết yếu còn thiếu."
        ],
        "exploration_advised": [
            "Cả bằng chứng CV và mức hứng thú hiện chưa mạnh; nên so sánh thêm 2-3 nghề gần với Holland code trước khi chọn lộ trình."
        ],
        "mixed_or_uncertain": [
            "Kết quả đang ở vùng chưa rõ ràng; nên bổ sung trải nghiệm thực tế và làm lại đánh giá sau một giai đoạn học hoặc thực tập."
        ],
    }[state]
    if mi_dimensions:
        recommendations.append(
            "Dùng kết quả MI để chọn cách học phù hợp, không dùng MI để loại trừ nghề: "
            + ", ".join(mi_dimensions[:3])
            + "."
        )
    return recommendations


async def synthesize_career_alignment(user_id: str) -> CareerAlignmentResponse:
    profile = await get_canonical_profile(user_id)
    holland = await get_latest_holland_assessment(user_id)
    mi_result = await get_latest_assessment_result(user_id, "multiple_intelligences")
    missing = []
    if not profile:
        missing.append("canonical_profile")
    if not holland:
        missing.append("holland_assessment")

    benchmark_id = (profile or {}).get("benchmark_profile_id")
    benchmark = resolve_profile_benchmark(profile)
    if profile and not benchmark:
        missing.append("target_role_benchmark")
    elif profile and not benchmark.get("riasec"):
        missing.append("role_interest_profile")
    cv_readiness = (profile or {}).get("total_score")
    if profile and cv_readiness is None:
        missing.append("cv_readiness_score")

    generated_at = utc_now()
    mi_dimensions = (mi_result or {}).get("top_dimensions", [])
    if missing:
        response = CareerAlignmentResponse(
            status="insufficient_data",
            user_id=user_id,
            target_role=(profile or {}).get("target_role"),
            benchmark_profile_id=benchmark_id,
            benchmark_type=(profile or {}).get("benchmark_type"),
            benchmark_version=(profile or {}).get("benchmark_version"),
            cv_readiness_score=cv_readiness,
            missing_components=missing,
            holland_top_code=(holland or {}).get("top_code"),
            mi_top_dimensions=mi_dimensions,
            recommendations_vi=[
                "Hoàn thành các thành phần còn thiếu trước khi hệ thống kết luận mức độ phù hợp nghề nghiệp."
            ],
            generated_at=generated_at,
        )
        await save_alignment_result(response.model_dump(mode="json"))
        return response

    holland_alignment = compute_holland_alignment(holland["scores"], benchmark["riasec"])
    state, severity = classify_alignment(float(cv_readiness), holland_alignment)
    overall = round(float(cv_readiness) * 0.60 + holland_alignment * 0.40, 2)
    target_role = profile["target_role"]
    deterministic_recommendations = build_recommendations(state, target_role, mi_dimensions)
    narrative, guidance_source = await generate_alignment_narrative(
        profile=profile,
        holland=holland,
        mi_result=mi_result,
        benchmark=benchmark,
        state=state,
        severity=severity,
        cv_score=float(cv_readiness),
        holland_score=holland_alignment,
        recommendations=deterministic_recommendations,
    )
    response = CareerAlignmentResponse(
        status="success",
        user_id=user_id,
        target_role=target_role,
        benchmark_profile_id=benchmark_id,
        benchmark_type=profile.get("benchmark_type"),
        benchmark_version=profile.get("benchmark_version"),
        cv_readiness_score=float(cv_readiness),
        holland_alignment_score=holland_alignment,
        career_alignment_score=overall,
        alignment_state=state,
        conflict_severity=severity,
        holland_top_code=holland.get("top_code"),
        mi_top_dimensions=mi_dimensions,
        evidence_summary_vi=[
            f"CV readiness cho {target_role}: {round(float(cv_readiness), 1)}/100.",
            f"Mức tương đồng Holland với profile nghề: {round(holland_alignment, 1)}/100.",
            "MI chỉ được dùng để đề xuất chiến lược học tập, không tham gia kết luận conflict nghề nghiệp.",
        ],
        recommendations_vi=narrative.action_plan_vi,
        executive_summary_vi=narrative.executive_summary_vi,
        strengths_vi=narrative.strengths_vi,
        watchouts_vi=narrative.watchouts_vi,
        action_plan_vi=narrative.action_plan_vi,
        learning_strategy_vi=narrative.learning_strategy_vi,
        guidance_source=guidance_source,
        rule_version=RULE_VERSION,
        generated_at=generated_at,
    )
    await save_alignment_result(response.model_dump(mode="json"))
    logger.info(
        "Saved career alignment result",
        extra={
            "user_id": user_id,
            "benchmark_profile_id": benchmark_id,
            "alignment_state": state,
            "conflict_severity": severity,
            "rule_version": RULE_VERSION,
            "guidance_source": guidance_source,
        },
    )
    return response
