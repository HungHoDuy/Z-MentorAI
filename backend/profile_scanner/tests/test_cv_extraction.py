import unittest
import io
import zipfile
from unittest.mock import AsyncMock, patch

from cv_extraction.service import (
    EXTRACTION_VERSION,
    assess_pdf_text_quality,
    extract_cv_text,
    extract_docx_images,
)


class CvExtractionQualityTests(unittest.TestCase):
    def test_image_pdf_without_text_requires_ocr(self):
        quality = assess_pdf_text_quality("", 2)
        self.assertFalse(quality.usable)
        self.assertIn("too_few_characters", quality.reasons)

    def test_garbage_text_does_not_bypass_ocr(self):
        quality = assess_pdf_text_quality("#@$% " * 100, 1)
        self.assertFalse(quality.usable)
        self.assertIn("low_alphanumeric_ratio", quality.reasons)

    def test_normal_cv_text_is_usable(self):
        text = " ".join([
            "Nguyen Van A software engineer experience education projects skills",
            "Developed Python services and REST APIs with measurable project results",
            "Bachelor of Computer Science Git Docker SQL testing collaboration",
        ] * 8)
        quality = assess_pdf_text_quality(text, 2)
        self.assertTrue(quality.usable)

    def test_mixed_pdf_with_scanned_page_requires_ocr(self):
        text = " ".join(["Python machine learning experience education project"] * 80)
        quality = assess_pdf_text_quality(text, 2, page_char_counts=[len(text), 0])

        self.assertFalse(quality.usable)
        self.assertEqual(quality.sparse_page_count, 1)
        self.assertIn("sparse_pdf_pages", quality.reasons)

    def test_mojibake_heavy_pdf_requires_ocr(self):
        text = ("ãƒ—ãƒ­ã‚¸ã‚§ã‚¯ãƒˆ æ¥­å‹™å†…å®¹ Python LangChain " * 80).strip()
        quality = assess_pdf_text_quality(text, 2)

        self.assertFalse(quality.usable)
        self.assertGreater(quality.mojibake_ratio, 0.02)
        self.assertIn("encoding_mojibake", quality.reasons)

    def test_docx_embedded_cv_images_are_detected_for_ocr(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("[Content_Types].xml", "<Types />")
            archive.writestr("word/document.xml", "<document />")
            archive.writestr("word/media/resume.png", b"fake-image")
            archive.writestr("word/media/logo.svg", b"<svg />")

        images = extract_docx_images(buffer.getvalue())

        self.assertEqual(images, [(b"fake-image", "image/png")])


class CvExtractionServiceTests(unittest.IsolatedAsyncioTestCase):
    @patch("cv_extraction.service.update_cv_document", new_callable=AsyncMock)
    @patch(
        "cv_extraction.service.upload_text_artifact",
        side_effect=[
            "gs://cv-bucket/users/user-1/cv_documents/cv-1/parsed_text.txt",
            "gs://cv-bucket/users/user-1/cv_documents/cv-1/parsed_result.json",
        ],
    )
    @patch("cv_extraction.service.extract_pdf_text")
    @patch("cv_extraction.service.storage.Client")
    async def test_successful_pdf_response_includes_extraction_version(
        self,
        storage_client,
        extract_pdf_text_mock,
        _upload_text_artifact,
        update_cv_document_mock,
    ):
        parsed_text = " ".join(
            [
                "Software engineer with Python API cloud project experience education skills",
                "Built production services with measurable results and team collaboration",
            ]
            * 20
        )
        extract_pdf_text_mock.return_value = (
            parsed_text,
            2,
            [len(parsed_text) // 2, len(parsed_text) // 2],
        )
        bucket = storage_client.return_value.bucket.return_value
        bucket.blob.return_value.download_as_bytes.return_value = b"%PDF-test"

        result = await extract_cv_text(
            {
                "cv_document_id": "cv-1",
                "file_kind": "pdf",
                "file_size_bytes": 9,
                "storage_bucket": "cv-bucket",
                "storage_object": "users/user-1/cv_documents/cv-1/original.pdf",
            }
        )

        self.assertEqual(result.extraction_version, EXTRACTION_VERSION)
        self.assertEqual(result.parser_type, "pypdf")
        self.assertEqual(result.text_char_count, len(parsed_text))
        update_cv_document_mock.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
