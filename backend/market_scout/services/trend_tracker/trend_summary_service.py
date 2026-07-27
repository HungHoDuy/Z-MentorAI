from __future__ import annotations

from typing import Any

from backend.market_scout.flows.trend_tracker_flow import TrendTrackerFlowResult
from backend.market_scout.schemas.trend_tracker.trend_summary import TrendSummaryResult


class TrendSummaryService:
    """Deterministically compose an end-user Vietnamese summary from trend evidence."""

    def summarize(self, result: TrendTrackerFlowResult) -> TrendSummaryResult:
        signal = result.signal
        answer = _compose_answer(signal.signal, signal.data, result)
        return TrendSummaryResult(
            answer=answer,
            confidence=signal.confidence,
            sources=signal.sources,
            limitations=signal.limitations,
        )


def _compose_answer(signal: str, data: dict[str, Any], result: TrendTrackerFlowResult) -> str:
    query = result.query
    subject = _display(query.job_category_id or query.job_family_id)
    location = _display(query.location_id)
    period = result.signal.period or "không rõ kỳ dữ liệu"

    if signal in {"current_demand_high", "current_demand_moderate"}:
        level = "cao" if signal == "current_demand_high" else "trung bình"
        return (
            f"Nhu cầu tuyển dụng hiện tại cho {subject} tại {location} ({period}) ở mức {level}: "
            f"{_integer(data.get('active_job_count'))} JD active từ "
            f"{_integer(data.get('distinct_company_count'))} công ty. "
            "Đây là current-demand baseline, không phải kết luận thị trường đang tăng hoặc giảm."
        )

    if signal == "current_skill_demand":
        skills = data.get("skills") if isinstance(data.get("skills"), list) else []
        sample_size = _integer(data.get("sample_size"))
        if not skills:
            return (
                f"Chưa có đủ skill evidence cho {subject} tại {location} ({period}); "
                f"cohort active hiện có {sample_size} JD."
            )
        skill_text = ", ".join(
            f"{_display(item.get('skill_id'))} ({_integer(item.get('job_count'))}/{sample_size} JD)"
            for item in skills[:5]
            if isinstance(item, dict)
        )
        return (
            f"Các kỹ năng được nhắc nhiều trong JD active của {subject} tại {location} ({period}): "
            f"{skill_text}. Đây là current skill requirements, không phải skill growth trend."
        )

    if signal == "external_outlook":
        claims = data.get("claims") if isinstance(data.get("claims"), list) else []
        claim_lines = [
            f"- {item.get('exact_claim')}"
            for item in claims[:4]
            if isinstance(item, dict) and item.get("exact_claim")
        ]
        source_lines = [
            f"- [{_display(source.get('publisher'))} - {_display(source.get('source_name'))}]({source.get('url')})"
            for source in result.signal.sources[:5]
            if isinstance(source, dict) and source.get("url")
        ]
        body = "\n".join(claim_lines) or "Chua co claim co the hien thi."
        source_text = "\n".join(source_lines)
        suffix = f"\nNguon tham khao:\n{source_text}" if source_text else ""
        return (
            f"Dua tren cac nguon tham khao dang co trong Z-MentorAI, outlook cho {subject} ({period}) co mot so diem chinh:\n"
            f"{body}{suffix}\nDay la external outlook de tham khao, khong phai du bao chac chan hay du lieu current-demand noi bo."
        )

    if signal == "out_of_scope":
        return (
            "Hệ thống chưa thể kết luận demand pressure hoặc thiếu nhân lực từ JD listings. "
            "Cần thêm applicant volume, time-to-fill hoặc vacancy duration."
        )

    active_jobs = data.get("active_job_count")
    companies = data.get("distinct_company_count")
    metric_text = ""
    if active_jobs is not None or companies is not None:
        metric_text = f" Snapshot hiện có {_integer(active_jobs)} JD active từ {_integer(companies)} công ty."
    return f"Chưa đủ evidence để trả lời cho {subject} tại {location}.{metric_text}"


def _display(value: Any) -> str:
    if value is None:
        return "không rõ"
    text = str(value).strip().replace("_", " ").replace("-", " ")
    return " ".join(text.split()) or "không rõ"


def _integer(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _task_text(value: Any) -> str:
    if not isinstance(value, list) or not value:
        return "chưa có mapping"
    return ", ".join(str(item) for item in value[:5])

