from __future__ import annotations

from backend.market_scout.schemas import MarketScoutEntities, SeniorityLevel


class NormalizationService:
    JOB_TITLE_ALIASES = {
        "ba": "Business Analyst",
        "business analyst": "Business Analyst",
        "ai engineer": "AI Engineer",
        "ml engineer": "Machine Learning Engineer",
        "machine learning engineer": "Machine Learning Engineer",
        "data analyst": "Data Analyst",
        "data engineer": "Data Engineer",
        "devops": "DevOps Engineer",
    }
    LOCATION_ALIASES = {
        "viet nam": "Vietnam",
        "vietnam": "Vietnam",
        "việt nam": "Vietnam",
        "hcm": "Ho Chi Minh City",
        "tp.hcm": "Ho Chi Minh City",
        "ho chi minh": "Ho Chi Minh City",
        "ha noi": "Hanoi",
        "hà nội": "Hanoi",
    }

    def normalize_entities(self, entities: MarketScoutEntities) -> MarketScoutEntities:
        entities.job_title = self.normalize_job_title(entities.job_title)
        entities.location = self.normalize_location(entities.location)
        entities.currency = self.normalize_currency(entities.currency)

        if entities.seniority is None and entities.experience_years is not None:
            entities.seniority = self.infer_seniority(entities.experience_years)

        return entities

    def normalize_job_title(self, job_title: str | None) -> str | None:
        if not job_title:
            return None
        key = job_title.strip().lower()
        return self.JOB_TITLE_ALIASES.get(key, job_title.strip())

    def normalize_location(self, location: str | None) -> str | None:
        if not location:
            return None
        key = location.strip().lower()
        return self.LOCATION_ALIASES.get(key, location.strip())

    @staticmethod
    def normalize_currency(currency: str | None) -> str:
        return (currency or "VND").strip().upper()

    @staticmethod
    def infer_seniority(experience_years: int) -> SeniorityLevel:
        if experience_years <= 0:
            return SeniorityLevel.FRESHER
        if experience_years <= 2:
            return SeniorityLevel.JUNIOR
        if experience_years <= 5:
            return SeniorityLevel.MIDDLE
        if experience_years <= 8:
            return SeniorityLevel.SENIOR
        return SeniorityLevel.LEAD
