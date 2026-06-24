from __future__ import annotations

import re
import unicodedata
from collections import Counter
from collections.abc import Mapping

from backend.market_scout.repositories.trend_job_fact_repository import TrendJobFactRepository
from backend.market_scout.schemas.current_skill_demand import (
    CurrentSkillDemandSignal,
    SkillFrequency,
)
from backend.market_scout.schemas.job_family_trend_snapshot import JobFamilyTrendSnapshot


DEFAULT_MIN_SAMPLE_SIZE = 10
COMMON_SKILL_ALIASES: dict[str, tuple[str, ...]] = {
    "excel": ("excel", "microsoft excel"),
    "english": ("tieng anh", "anh ngu", "english"),
    "office_productivity": ("tin hoc van phong", "microsoft office"),
}
DEFAULT_SKILL_ALIASES_BY_FAMILY: dict[str, dict[str, tuple[str, ...]]] = {
    "finance_legal": {
        "ifrs": ("ifrs",),
        "tax": ("tax", "thue"),
        "sap": ("sap",),
        "power_bi": ("power bi", "powerbi"),
        "acca": ("acca",),
        "cpa": ("cpa",),
        "cfa": ("cfa",),
    },
    "digital_telecom": {
        "python": ("python",),
        "java": ("java",),
        "javascript": ("javascript", "java script"),
        "react": ("react", "reactjs"),
        "sql": ("sql",),
        "aws": ("aws", "amazon web services"),
        "docker": ("docker",),
        "kubernetes": ("kubernetes", "k8s"),
        "git": ("git",),
    },
    "operations": {
        "iso": ("iso",),
        "haccp": ("haccp",),
        "lean": ("lean",),
        "six_sigma": ("six sigma", "6 sigma", "6sigma"),
        "erp": ("erp",),
        "sap": ("sap",),
        "wms": ("wms",),
        "tms": ("tms",),
    },
    "commercial": {
        "crm": ("crm",),
        "sales": ("sales", "ban hang", "kinh doanh"),
        "digital_marketing": ("digital marketing", "marketing online"),
        "seo": ("seo",),
        "google_ads": ("google ads", "google adwords"),
    },
}


class SkillFrequencyService:
    """Compute current skill demand from active facts in one snapshot cohort."""

    def __init__(
        self,
        *,
        fact_repository: TrendJobFactRepository,
        skill_aliases_by_family: Mapping[str, Mapping[str, tuple[str, ...]]] | None = None,
        common_skill_aliases: Mapping[str, tuple[str, ...]] | None = None,
        min_sample_size: int = DEFAULT_MIN_SAMPLE_SIZE,
    ) -> None:
        if min_sample_size <= 0:
            raise ValueError("min_sample_size must be positive.")
        self.fact_repository = fact_repository
        self.skill_aliases_by_family = skill_aliases_by_family or DEFAULT_SKILL_ALIASES_BY_FAMILY
        self.common_skill_aliases = common_skill_aliases or COMMON_SKILL_ALIASES
        self.min_sample_size = min_sample_size

    def evaluate(
        self,
        snapshot: JobFamilyTrendSnapshot,
        *,
        job_category_id: str | None = None,
        top_k: int = 10,
    ) -> CurrentSkillDemandSignal:
        if top_k <= 0:
            raise ValueError("top_k must be positive.")

        facts = self.fact_repository.list_active_for_snapshot(
            snapshot,
            job_category_id=job_category_id,
        )
        sample_size = len(facts)
        if sample_size < self.min_sample_size:
            return CurrentSkillDemandSignal(
                signal="insufficient_evidence",
                job_family_id=snapshot.job_family_id,
                location_id=snapshot.location_id,
                period=snapshot.period,
                sample_size=sample_size,
                skills=[],
                confidence="low",
                limitations=[
                    "The active-job cohort is below the minimum skill-sample threshold.",
                    "Skill frequency is a current requirement signal, not skill growth.",
                ],
            )

        aliases = self._skill_aliases(snapshot.job_family_id)
        counts: Counter[str] = Counter()
        for fact in facts:
            text = _normalize_text(" ".join(filter(None, (fact.requirements_text, fact.description_text))))
            for skill_id, phrases in aliases.items():
                if any(_contains_phrase(text, phrase) for phrase in phrases):
                    counts[skill_id] += 1

        skills = [
            SkillFrequency(
                skill_id=skill_id,
                job_count=count,
                job_share=round(count / sample_size, 4),
            )
            for skill_id, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:top_k]
        ]
        return CurrentSkillDemandSignal(
            signal="current_skill_demand",
            job_family_id=snapshot.job_family_id,
            location_id=snapshot.location_id,
            period=snapshot.period,
            sample_size=sample_size,
            skills=skills,
            confidence="low",
            limitations=[
                "Skill frequency is extracted by keyword taxonomy from current active job text.",
                "This is a current requirement signal, not a skill growth trend.",
            ],
        )

    def _skill_aliases(self, job_family_id: str) -> dict[str, tuple[str, ...]]:
        aliases = dict(self.common_skill_aliases)
        aliases.update(self.skill_aliases_by_family.get(job_family_id, {}))
        return {
            skill_id: tuple(_normalize_text(phrase) for phrase in phrases if _normalize_text(phrase))
            for skill_id, phrases in aliases.items()
        }


def _normalize_text(value: str | None) -> str:
    if not value:
        return ""
    text = str(value).replace("đ", "d").replace("Đ", "D")
    text = unicodedata.normalize("NFD", text)
    text = "".join(character for character in text if unicodedata.category(character) != "Mn")
    text = text.casefold()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _contains_phrase(text: str, phrase: str) -> bool:
    return re.search(rf"(?<![a-z0-9]){re.escape(phrase)}(?![a-z0-9])", text) is not None
