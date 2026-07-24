import unittest
import io
import zipfile

from cv_extraction.service import assess_pdf_text_quality, extract_docx_images


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


if __name__ == "__main__":
    unittest.main()
