import datetime
import io
import json
import re
from dataclasses import dataclass
from typing import Any

from docx import Document
from fastapi import HTTPException
from google.api_core.client_options import ClientOptions
from google.cloud import documentai
from google.cloud import storage
from pypdf import PdfReader

from core.config import logger, settings
from cv_intake.repository import update_cv_document
from cv_extraction.schemas import CvExtractionResult


MIN_EXTRACTED_TEXT_CHARS = 80


@dataclass(frozen=True)
class TextQuality:
    usable: bool
    char_count: int
    word_count: int
    alphanumeric_ratio: float
    words_per_page: float
    reasons: list[str]


def assess_pdf_text_quality(text: str, page_count: int | None) -> TextQuality:
    stripped = (text or "").strip()
    non_space = re.sub(r"\s", "", stripped)
    alphanumeric = sum(char.isalnum() for char in non_space)
    words = re.findall(r"\b\w{2,}\b", stripped, flags=re.UNICODE)
    pages = max(page_count or 1, 1)
    ratio = alphanumeric / max(len(non_space), 1)
    words_per_page = len(words) / pages
    reasons = []
    if len(stripped) < MIN_EXTRACTED_TEXT_CHARS:
        reasons.append("too_few_characters")
    if len(words) < max(15, pages * 12):
        reasons.append("too_few_words")
    if words_per_page < 12:
        reasons.append("low_words_per_page")
    if ratio < 0.65:
        reasons.append("low_alphanumeric_ratio")
    return TextQuality(
        usable=not reasons,
        char_count=len(stripped),
        word_count=len(words),
        alphanumeric_ratio=round(ratio, 3),
        words_per_page=round(words_per_page, 2),
        reasons=reasons,
    )


def utc_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def extract_pdf_text(content: bytes) -> tuple[str, int]:
    reader = PdfReader(io.BytesIO(content))
    page_texts = []
    for page in reader.pages:
        page_texts.append(page.extract_text() or "")
    text = "\n\n".join(part.strip() for part in page_texts if part.strip()).strip()
    return text, len(reader.pages)


def get_document_ai_processor_name() -> str | None:
    if settings.document_ai_processor_name:
        return settings.document_ai_processor_name
    if not settings.document_ai_processor_id:
        return None

    client = documentai.DocumentProcessorServiceClient(
        client_options=ClientOptions(
            api_endpoint=f"{settings.document_ai_location}-documentai.googleapis.com",
        )
    )
    return client.processor_path(
        settings.google_cloud_project,
        settings.document_ai_location,
        settings.document_ai_processor_id,
    )


def extract_pdf_text_with_document_ai(content: bytes) -> str:
    processor_name = get_document_ai_processor_name()
    if not processor_name:
        raise RuntimeError("Document AI processor is not configured.")

    client = documentai.DocumentProcessorServiceClient(
        client_options=ClientOptions(
            api_endpoint=f"{settings.document_ai_location}-documentai.googleapis.com",
        )
    )
    request = documentai.ProcessRequest(
        name=processor_name,
        raw_document=documentai.RawDocument(
            content=content,
            mime_type="application/pdf",
        ),
    )
    result = client.process_document(request=request)
    return (result.document.text or "").strip()


def extract_docx_text(content: bytes) -> str:
    document = Document(io.BytesIO(content))
    blocks = []

    for paragraph in document.paragraphs:
        text = paragraph.text.strip()
        if text:
            blocks.append(text)

    for table in document.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if cells:
                blocks.append(" | ".join(cells))

    return "\n".join(blocks).strip()


def build_artifact_object_name(original_object: str, filename: str) -> str:
    prefix = original_object.rsplit("/", 1)[0]
    return f"{prefix}/{filename}"


def upload_text_artifact(bucket: Any, object_name: str, content: str, content_type: str) -> str:
    blob = bucket.blob(object_name)
    blob.upload_from_string(content.encode("utf-8"), content_type=content_type)
    return f"gs://{bucket.name}/{object_name}"


async def extract_cv_text(document: dict) -> CvExtractionResult:
    cv_document_id = document["cv_document_id"]
    file_kind = document.get("file_kind")
    bucket_name = document.get("storage_bucket")
    object_name = document.get("storage_object")

    if file_kind not in {"pdf", "docx"}:
        raise HTTPException(status_code=400, detail="Only PDF and DOCX CV extraction is supported.")
    if not bucket_name or not object_name:
        raise HTTPException(status_code=400, detail="CV document storage metadata is incomplete.")

    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(object_name)

    try:
        content = blob.download_as_bytes()
    except Exception as exc:
        logger.exception(
            "Failed to download CV from GCS",
            extra={
                "cv_document_id": cv_document_id,
                "bucket": bucket_name,
                "object_name": object_name,
                "error_type": type(exc).__name__,
            },
        )
        raise HTTPException(status_code=503, detail="Unable to download CV from GCS.") from exc

    page_count = None
    parser_type = "pypdf" if file_kind == "pdf" else "python_docx"
    extraction_quality = None
    try:
        if file_kind == "pdf":
            try:
                parsed_text, page_count = extract_pdf_text(content)
            except Exception as parser_exc:
                if not get_document_ai_processor_name():
                    raise
                logger.warning(
                    "PyPDF extraction failed; using Document AI OCR",
                    extra={
                        "cv_document_id": cv_document_id,
                        "error_type": type(parser_exc).__name__,
                    },
                )
                parser_type = "document_ai_ocr"
                parsed_text = extract_pdf_text_with_document_ai(content)
            else:
                extraction_quality = assess_pdf_text_quality(parsed_text, page_count)
                logger.info(
                    "Evaluated PDF text quality",
                    extra={
                        "cv_document_id": cv_document_id,
                        "usable": extraction_quality.usable,
                        "char_count": extraction_quality.char_count,
                        "word_count": extraction_quality.word_count,
                        "words_per_page": extraction_quality.words_per_page,
                        "alphanumeric_ratio": extraction_quality.alphanumeric_ratio,
                        "reasons": extraction_quality.reasons,
                    },
                )
                if not extraction_quality.usable:
                    if get_document_ai_processor_name():
                        parser_type = "document_ai_ocr"
                        parsed_text = extract_pdf_text_with_document_ai(content)
        else:
            parsed_text = extract_docx_text(content)
    except Exception as exc:
        await update_cv_document(cv_document_id, {
            "extraction_status": "failed",
            "extraction_error": str(exc),
            "extracted_at": utc_now(),
        })
        logger.exception(
            "Failed to extract CV text",
            extra={
                "cv_document_id": cv_document_id,
                "file_kind": file_kind,
                "parser_type": parser_type,
                "error_type": type(exc).__name__,
            },
        )
        raise HTTPException(status_code=422, detail="Unable to extract text from this CV.") from exc

    final_quality = assess_pdf_text_quality(parsed_text, page_count) if file_kind == "pdf" else None
    if len(parsed_text) < MIN_EXTRACTED_TEXT_CHARS or (final_quality and not final_quality.usable):
        await update_cv_document(cv_document_id, {
            "extraction_status": "needs_ocr",
            "parser_type": parser_type,
            "text_char_count": len(parsed_text),
            "page_count": page_count,
            "extracted_at": utc_now(),
            "extraction_error": "Extracted text is too short and OCR fallback is not configured or returned too little text.",
            "extraction_quality": final_quality.__dict__ if final_quality else None,
        })
        raise HTTPException(
            status_code=422,
            detail="Extracted text is too short. OCR fallback is not configured or returned too little text.",
        )

    extracted_at = utc_now()
    parsed_text_object = build_artifact_object_name(object_name, "parsed_text.txt")
    parsed_result_object = build_artifact_object_name(object_name, "parsed_result.json")
    parsed_result = {
        "cv_document_id": cv_document_id,
        "parser_type": parser_type,
        "ocr_fallback_used": parser_type == "document_ai_ocr",
        "text_char_count": len(parsed_text),
        "page_count": page_count,
        "extraction_quality": final_quality.__dict__ if final_quality else None,
        "extracted_at": extracted_at,
    }

    try:
        parsed_text_uri = upload_text_artifact(
            bucket,
            parsed_text_object,
            parsed_text,
            "text/plain; charset=utf-8",
        )
        parsed_result_uri = upload_text_artifact(
            bucket,
            parsed_result_object,
            json.dumps(parsed_result, ensure_ascii=False, indent=2),
            "application/json; charset=utf-8",
        )
    except Exception as exc:
        logger.exception(
            "Failed to upload parsed CV artifacts",
            extra={
                "cv_document_id": cv_document_id,
                "bucket": bucket_name,
                "error_type": type(exc).__name__,
            },
        )
        raise HTTPException(status_code=503, detail="Unable to store parsed CV artifacts.") from exc

    await update_cv_document(cv_document_id, {
        "extraction_status": "completed",
        "parser_type": parser_type,
        "ocr_fallback_used": parser_type == "document_ai_ocr",
        "text_char_count": len(parsed_text),
        "page_count": page_count,
        "extraction_quality": final_quality.__dict__ if final_quality else None,
        "parsed_text_gcs_uri": parsed_text_uri,
        "parsed_result_gcs_uri": parsed_result_uri,
        "parsed_text_object": parsed_text_object,
        "parsed_result_object": parsed_result_object,
        "extracted_at": extracted_at,
        "next_status": "pending_profile_extraction",
        "extraction_error": None,
    })

    return CvExtractionResult(
        cv_document_id=cv_document_id,
        parser_type=parser_type,
        ocr_fallback_used=parser_type == "document_ai_ocr",
        text_char_count=len(parsed_text),
        page_count=page_count,
        parsed_text_gcs_uri=parsed_text_uri,
        parsed_result_gcs_uri=parsed_result_uri,
        extracted_at=extracted_at,
        message_vi=(
            "Profile Scanner đã trích xuất nội dung CV thành công. "
            "Bước tiếp theo là chuẩn hóa kỹ năng, học vấn, kinh nghiệm và đánh giá benchmark theo target role."
        ),
    )
