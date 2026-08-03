import asyncio

from fastapi import HTTPException
from google.cloud import storage

from cv_draft.repository import create_cv_draft, get_cv_draft
from profile_ai_extraction.schemas import StructuredExperience, StructuredProfile
from profile_ai_extraction.service import (
    extract_structured_profile_with_ai,
    revise_structured_profile_with_ai,
)
from profile_analysis.service import extract_matching_skills, split_lines


def _load_parsed_text(document: dict) -> str:
    bucket_name = document.get("storage_bucket")
    parsed_text_object = document.get("parsed_text_object")
    if not bucket_name or not parsed_text_object:
        raise HTTPException(status_code=400, detail="Parsed CV text metadata is incomplete.")
    try:
        return storage.Client().bucket(bucket_name).blob(parsed_text_object).download_as_text(
            encoding="utf-8"
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Unable to load parsed CV text from GCS.") from exc


def _heuristic_profile(parsed_text: str) -> StructuredProfile:
    lines = split_lines(parsed_text)
    return StructuredProfile(
        extraction_source="heuristic",
        full_name=lines[0][:120] if lines else "",
        skills=extract_matching_skills(parsed_text),
        work_experiences=[
            StructuredExperience(summary=line)
            for line in lines
            if any(token in line.lower() for token in ("experience", "developer", "engineer"))
        ][:8],
        missing_or_unclear=["Một số trường cần được người dùng kiểm tra lại do AI extraction không khả dụng."],
        confidence=0.35,
    )


async def get_or_create_cv_draft(document: dict) -> dict:
    current_extraction_id = document.get("current_extraction_id")
    if current_extraction_id:
        current = await get_cv_draft(current_extraction_id)
        if current and current.get("cv_document_id") == document.get("cv_document_id"):
            return current

    parsed_text = await asyncio.to_thread(_load_parsed_text, document)
    structured_profile = await asyncio.to_thread(
        extract_structured_profile_with_ai,
        parsed_text=parsed_text,
        target_role=document.get("requested_target_role"),
        message=document.get("message"),
    )
    if structured_profile is None:
        structured_profile = _heuristic_profile(parsed_text)
    return await create_cv_draft(
        user_id=document["user_id"],
        cv_document_id=document["cv_document_id"],
        structured_profile=structured_profile.as_firestore_payload(),
        source=structured_profile.extraction_source,
    )


async def revise_cv_draft(draft: dict, instruction: str) -> dict:
    if not instruction.strip():
        raise HTTPException(status_code=400, detail="Edit instruction is required.")
    revised_profile = await asyncio.to_thread(
        revise_structured_profile_with_ai,
        current_profile=StructuredProfile(**draft["structured_profile"]),
        instruction=instruction,
    )
    if revised_profile is None:
        raise HTTPException(status_code=503, detail="CV draft editing is temporarily unavailable.")
    return await create_cv_draft(
        user_id=draft["user_id"],
        cv_document_id=draft["cv_document_id"],
        structured_profile=revised_profile.as_firestore_payload(),
        source="user_correction_ai_mapped",
        parent_extraction_id=draft["extraction_id"],
        edit_instruction=instruction.strip(),
    )
