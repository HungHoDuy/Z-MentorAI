from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone

from backend.market_scout.schemas import CleanedDocument, RawDocument


class TextCleaningService:
    BOILERPLATE_PATTERNS = [
        r"accept all cookies",
        r"accept cookies",
        r"cookie policy",
        r"privacy policy",
        r"terms of use",
        r"sign in",
        r"log in",
        r"subscribe",
        r"newsletter",
        r"advertisement",
        r"skip to content",
        r"all rights reserved",
    ]

    def clean(self, raw_document: RawDocument) -> CleanedDocument | None:
        text = raw_document.cleaned_text or raw_document.raw_text
        text = self.normalize_whitespace(text)
        lines = self._deduplicate_lines(text.splitlines())
        lines = self._remove_boilerplate_lines(lines)
        cleaned_text = "\n".join(lines).strip()

        if not cleaned_text:
            return None

        sections = self.split_sections(cleaned_text)
        content_hash = self.content_hash(cleaned_text)

        return CleanedDocument(
            source=raw_document.source,
            cleaned_text=cleaned_text,
            sections=sections,
            language=self.detect_language(cleaned_text),
            document_type=raw_document.document_type,
            content_hash=content_hash,
            word_count=self.word_count(cleaned_text),
            crawled_at=raw_document.crawled_at,
            cleaned_at=datetime.now(timezone.utc).isoformat(),
            metadata={
                **raw_document.metadata,
                "cleaning_version": "v1",
                "section_count": len(sections),
            },
        )

    @staticmethod
    def normalize_whitespace(text: str) -> str:
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return "\n".join(line.strip() for line in text.splitlines() if line.strip())

    def split_sections(self, text: str, max_words_per_section: int = 220) -> list[str]:
        paragraphs = [paragraph.strip() for paragraph in re.split(r"\n{2,}", text) if paragraph.strip()]
        if not paragraphs:
            paragraphs = [text]

        sections: list[str] = []
        current: list[str] = []
        current_words = 0

        for paragraph in paragraphs:
            paragraph_words = self.word_count(paragraph)
            if current and current_words + paragraph_words > max_words_per_section:
                sections.append("\n\n".join(current))
                current = []
                current_words = 0

            current.append(paragraph)
            current_words += paragraph_words

        if current:
            sections.append("\n\n".join(current))

        return sections

    @staticmethod
    def content_hash(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    @staticmethod
    def word_count(text: str) -> int:
        return len(re.findall(r"\b[\wÀ-ỹ]+\b", text, flags=re.UNICODE))

    @staticmethod
    def detect_language(text: str) -> str:
        vietnamese_markers = set("ăâđêôơưáàảãạấầẩẫậắằẳẵặéèẻẽẹếềểễệíìỉĩịóòỏõọốồổỗộớờởỡợúùủũụứừửữựýỳỷỹỵ")
        lowered = text.lower()
        if any(char in vietnamese_markers for char in lowered):
            return "vi"
        return "en"

    def _remove_boilerplate_lines(self, lines: list[str]) -> list[str]:
        cleaned: list[str] = []
        for line in lines:
            normalized = line.lower().strip()
            if len(normalized) < 3:
                continue
            if any(re.search(pattern, normalized) for pattern in self.BOILERPLATE_PATTERNS):
                continue
            cleaned.append(line)
        return cleaned

    @staticmethod
    def _deduplicate_lines(lines: list[str]) -> list[str]:
        seen: set[str] = set()
        deduped: list[str] = []

        for line in lines:
            normalized = re.sub(r"\s+", " ", line).strip().lower()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            deduped.append(line.strip())

        return deduped
