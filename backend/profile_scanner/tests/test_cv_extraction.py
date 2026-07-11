import unittest

from cv_extraction.service import assess_pdf_text_quality


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


if __name__ == "__main__":
    unittest.main()
