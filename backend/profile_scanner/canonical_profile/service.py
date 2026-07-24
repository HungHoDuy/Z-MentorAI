import datetime
import re
import unicodedata

from fastapi import HTTPException

from canonical_profile.repository import (
    get_canonical_profile,
    mark_profile_decision,
    save_profile_version,
)
from canonical_profile.schemas import ProfileDecisionRequest, ProfileDecisionResponse
from cv_intake.repository import get_cv_document
from core.config import logger


IDENTITY_MATCH_VERSION = "identity-match-v1"


def utc_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def normalize_name(value: str | None) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    return " ".join(re.sub(r"[^a-zA-Z0-9 ]", " ", normalized).lower().split())


def normalize_email(value: str | None) -> str:
    return (value or "").strip().lower()


def normalize_phone(value: str | None) -> str:
    digits = re.sub(r"\D", "", value or "")
    return digits[-10:] if len(digits) >= 10 else digits


def identity_match_score(existing: dict, candidate: dict) -> tuple[float, list[str]]:
    existing_identity = existing.get("identity", existing)
    score = 0.0
    signals = []

    pairs = {
        "email": (normalize_email(existing_identity.get("email")), normalize_email(candidate.get("email"))),
        "phone": (normalize_phone(existing_identity.get("phone")), normalize_phone(candidate.get("phone"))),
        "full_name": (normalize_name(existing_identity.get("full_name")), normalize_name(candidate.get("full_name"))),
    }
    if pairs["email"][0] and pairs["email"][1]:
        if pairs["email"][0] == pairs["email"][1]:
            score += 0.55
            signals.append("email_match")
        else:
            score -= 0.35
            signals.append("email_mismatch")
    if pairs["phone"][0] and pairs["phone"][1]:
        if pairs["phone"][0] == pairs["phone"][1]:
            score += 0.45
            signals.append("phone_match")
        else:
            score -= 0.25
            signals.append("phone_mismatch")
    if pairs["full_name"][0] and pairs["full_name"][1]:
        if pairs["full_name"][0] == pairs["full_name"][1]:
            score += 0.35
            signals.append("full_name_match")
        else:
            signals.append("full_name_mismatch")

    existing_education = " ".join(existing.get("education_records", []))
    candidate_education = " ".join(candidate.get("education_records", []))
    if existing_education and candidate_education:
        existing_words = set(normalize_name(existing_education).split())
        candidate_words = set(normalize_name(candidate_education).split())
        if len(existing_words & candidate_words) >= 2:
            score += 0.15
            signals.append("education_overlap")

    existing_work = " ".join(existing.get("work_experiences", []))
    candidate_work = " ".join(candidate.get("work_experiences", []))
    if existing_work and candidate_work:
        existing_words = set(normalize_name(existing_work).split())
        candidate_words = set(normalize_name(candidate_work).split())
        if len(existing_words & candidate_words) >= 2:
            score += 0.15
            signals.append("work_overlap")

    return round(max(0.0, min(1.0, score)), 2), signals


def build_profile_action(
    *,
    existing_profile: dict | None,
    candidate_identity: dict,
    cv_document_id: str,
    candidate_profile: dict | None = None,
) -> dict:
    display_name = candidate_identity.get("full_name") or "chưa xác định được tên"
    if not existing_profile:
        return {
            "action_required": "confirm_profile_creation",
            "cv_document_id": cv_document_id,
            "candidate_identity": candidate_identity,
            "identity_match_score": None,
            "identity_match_version": IDENTITY_MATCH_VERSION,
            "message_vi": f"CV này đang có tên {display_name}. Bạn có muốn lưu thông tin thành hồ sơ cá nhân không?",
            "options": [
                {"decision": "accept", "label_vi": "Có, lưu hồ sơ"},
                {"decision": "reject", "label_vi": "Không"},
            ],
        }

    comparison_candidate = {
        **(candidate_profile or {}),
        **candidate_identity,
    }
    match_score, signals = identity_match_score(existing_profile, comparison_candidate)
    if match_score >= 0.80:
        action_required = "auto_update_profile"
        message = f"Đã xác nhận CV thuộc {display_name} và cập nhật hồ sơ bằng dữ liệu mới nhất."
        options = []
    elif match_score >= 0.50:
        action_required = "confirm_profile_update"
        message = f"CV mới có nhiều thông tin trùng với hồ sơ {display_name}. Bạn có muốn cập nhật hồ sơ không?"
        options = [
            {"decision": "update", "label_vi": "Cập nhật"},
            {"decision": "reject", "label_vi": "Giữ hồ sơ cũ"},
        ]
    else:
        action_required = "confirm_profile_overwrite"
        message = f"Thông tin người trong CV mới không khớp rõ với hồ sơ hiện tại. Bạn có muốn ghi đè bằng hồ sơ {display_name} không?"
        options = [
            {"decision": "overwrite", "label_vi": "Ghi đè hồ sơ"},
            {"decision": "reject", "label_vi": "Không"},
        ]

    return {
        "action_required": action_required,
        "cv_document_id": cv_document_id,
        "candidate_identity": candidate_identity,
        "identity_match_score": match_score,
        "identity_match_signals": signals,
        "identity_match_version": IDENTITY_MATCH_VERSION,
        "message_vi": message,
        "options": options,
    }


def build_canonical_payload(
    *,
    user_id: str,
    cv_document_id: str,
    analysis: dict,
    previous_profile: dict | None,
) -> dict:
    now = utc_now()
    source_document_ids = list((previous_profile or {}).get("source_document_ids", []))
    if cv_document_id not in source_document_ids:
        source_document_ids.append(cv_document_id)
    return {
        "user_id": user_id,
        "identity": analysis.get("candidate_identity", {}),
        "headline": (analysis.get("structured_profile") or {}).get("headline", ""),
        "summary": (analysis.get("structured_profile") or {}).get("summary", ""),
        "skills": analysis.get("extracted_skills", []),
        "normalized_skills": analysis.get("normalized_skills", []),
        "skill_normalization_version": analysis.get("skill_normalization_version"),
        "work_experiences": analysis.get("work_experiences", []),
        "education_records": analysis.get("education_records", []),
        "projects": analysis.get("projects", []),
        "target_role": analysis.get("target_role"),
        "benchmark_profile_id": analysis.get("benchmark_profile_id"),
        "benchmark_version": analysis.get("benchmark_version"),
        "grade": analysis.get("grade"),
        "total_score": analysis.get("total_score"),
        "active_cv_document_id": cv_document_id,
        "source_document_ids": source_document_ids,
        "profile_version": int((previous_profile or {}).get("profile_version", 0)) + 1,
        "created_at": (previous_profile or {}).get("created_at", now),
        "updated_at": now,
    }


async def prepare_profile_action(document: dict, analysis: dict) -> dict:
    user_id = document["user_id"]
    existing_profile = await get_canonical_profile(user_id)
    if (
        existing_profile
        and existing_profile.get("active_cv_document_id") == document["cv_document_id"]
        and document.get("profile_link_status") == "active"
    ):
        return {
            "action_required": "profile_current",
            "cv_document_id": document["cv_document_id"],
            "candidate_identity": analysis.get("candidate_identity", {}),
            "profile_version": existing_profile.get("profile_version"),
            "profile_status": "unchanged",
            "message_vi": "CV này đang là nguồn dữ liệu hiện hành của hồ sơ cá nhân.",
            "options": [],
        }
    candidate_identity = analysis.get("candidate_identity", {})
    candidate_profile = {
        "education_records": analysis.get("education_records", []),
        "work_experiences": analysis.get("work_experiences", []),
    }
    action = build_profile_action(
        existing_profile=existing_profile,
        candidate_identity=candidate_identity,
        cv_document_id=document["cv_document_id"],
        candidate_profile=candidate_profile,
    )
    await mark_profile_decision(document["cv_document_id"], {
        "profile_action": action,
        "profile_link_status": "pending_confirmation",
    })
    logger.info(
        "Prepared canonical profile action",
        extra={
            "user_id": user_id,
            "cv_document_id": document["cv_document_id"],
            "action_required": action["action_required"],
            "identity_match_score": action.get("identity_match_score"),
        },
    )

    if action["action_required"] == "auto_update_profile":
        profile = build_canonical_payload(
            user_id=user_id,
            cv_document_id=document["cv_document_id"],
            analysis=analysis,
            previous_profile=existing_profile,
        )
        saved_profile = await save_profile_version(
            profile=profile,
            previous_profile=existing_profile,
            cv_document_id=document["cv_document_id"],
        )
        action["profile_version"] = saved_profile["profile_version"]
        action["profile_status"] = "updated"
    return action


async def confirm_profile_decision(request: ProfileDecisionRequest) -> ProfileDecisionResponse:
    document = await get_cv_document(request.cv_document_id)
    if not document or document.get("user_id") != request.user_id:
        raise HTTPException(status_code=404, detail="CV document not found for this user.")

    analysis = document.get("profile_analysis")
    if not analysis:
        raise HTTPException(status_code=409, detail="CV analysis must complete before profile confirmation.")

    existing_profile = await get_canonical_profile(request.user_id)
    if (
        existing_profile
        and existing_profile.get("active_cv_document_id") == request.cv_document_id
        and document.get("profile_link_status") == "active"
    ):
        return ProfileDecisionResponse(
            user_id=request.user_id,
            cv_document_id=request.cv_document_id,
            decision=request.decision,
            profile_status="unchanged",
            profile_version=existing_profile.get("profile_version"),
            active_cv_document_id=request.cv_document_id,
            message_vi="CV này đã là nguồn dữ liệu hiện hành của hồ sơ cá nhân.",
        )
    action = build_profile_action(
        existing_profile=existing_profile,
        candidate_identity=analysis.get("candidate_identity", {}),
        cv_document_id=request.cv_document_id,
        candidate_profile={
            "education_records": analysis.get("education_records", []),
            "work_experiences": analysis.get("work_experiences", []),
        },
    )

    if request.decision == "reject":
        await mark_profile_decision(request.cv_document_id, {
            "profile_link_status": "rejected",
            "profile_decided_at": utc_now(),
        })
        return ProfileDecisionResponse(
            user_id=request.user_id,
            cv_document_id=request.cv_document_id,
            decision=request.decision,
            profile_status="unchanged",
            profile_version=(existing_profile or {}).get("profile_version"),
            active_cv_document_id=(existing_profile or {}).get("active_cv_document_id"),
            message_vi="Đã giữ nguyên hồ sơ cá nhân hiện tại. CV mới không được dùng làm hồ sơ chính.",
        )

    expected_decisions = {
        "confirm_profile_creation": {"accept"},
        "confirm_profile_update": {"update", "accept"},
        "confirm_profile_overwrite": {"overwrite"},
        "auto_update_profile": {"update", "accept"},
    }
    allowed = expected_decisions[action["action_required"]]
    if request.decision not in allowed:
        raise HTTPException(
            status_code=409,
            detail=f"Decision {request.decision} is invalid for {action['action_required']}.",
        )

    profile = build_canonical_payload(
        user_id=request.user_id,
        cv_document_id=request.cv_document_id,
        analysis=analysis,
        previous_profile=existing_profile,
    )
    saved_profile = await save_profile_version(
        profile=profile,
        previous_profile=existing_profile,
        cv_document_id=request.cv_document_id,
    )
    logger.info(
        "Saved canonical profile version",
        extra={
            "user_id": request.user_id,
            "cv_document_id": request.cv_document_id,
            "profile_version": saved_profile["profile_version"],
            "decision": request.decision,
        },
    )
    return ProfileDecisionResponse(
        user_id=request.user_id,
        cv_document_id=request.cv_document_id,
        decision=request.decision,
        profile_status="created" if not existing_profile else "updated",
        profile_version=saved_profile["profile_version"],
        active_cv_document_id=request.cv_document_id,
        message_vi=(
            "Đã tạo hồ sơ cá nhân từ CV và lưu phiên bản đầu tiên."
            if not existing_profile
            else "Đã cập nhật hồ sơ cá nhân bằng CV mới và lưu lại lịch sử phiên bản."
        ),
    )
