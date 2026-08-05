import io
import zipfile

import pytest
from fastapi import HTTPException

import cv_intake.service as intake_service
from cv_intake.service import deterministic_cv_document_id, validate_file_signature


def build_minimal_docx() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types />")
        archive.writestr("word/document.xml", "<document />")
    return buffer.getvalue()


def test_cv_document_id_is_idempotent_per_user_and_content():
    first = deterministic_cv_document_id("user-1", "hash-1")
    assert first == deterministic_cv_document_id("user-1", "hash-1")
    assert first != deterministic_cv_document_id("user-1", "hash-2")
    assert first != deterministic_cv_document_id("user-2", "hash-1")


def test_pdf_signature_validation_rejects_fake_pdf():
    try:
        validate_file_signature(b"not-a-pdf", "pdf")
    except HTTPException as exc:
        assert exc.status_code == 400
    else:
        raise AssertionError("Expected fake PDF to be rejected")


@pytest.mark.parametrize(
    "prefix",
    [b"\n", b"\r\n", b" \t\n", b"\xef\xbb\xbf\r\n"],
)
def test_pdf_signature_validation_accepts_safe_leading_bytes(prefix):
    validate_file_signature(prefix + b"%PDF-1.7\n%%EOF", "pdf")


def test_pdf_signature_validation_rejects_non_whitespace_preamble():
    with pytest.raises(HTTPException) as error:
        validate_file_signature(b"untrusted-prefix%PDF-1.7\n%%EOF", "pdf")

    assert error.value.status_code == 400


def test_docx_signature_validation_accepts_required_parts():
    validate_file_signature(build_minimal_docx(), "docx")


def test_active_pdf_content_is_rejected():
    try:
        validate_file_signature(b"%PDF-1.7\n/JavaScript", "pdf")
    except HTTPException as exc:
        assert exc.status_code == 400
    else:
        raise AssertionError("Expected active PDF content to be rejected")


def test_docx_archive_expansion_limit_is_enforced(monkeypatch):
    monkeypatch.setattr(intake_service, "MAX_DOCX_UNCOMPRESSED_BYTES", 10)

    with pytest.raises(HTTPException) as error:
        validate_file_signature(build_minimal_docx(), "docx")

    assert error.value.status_code == 400
