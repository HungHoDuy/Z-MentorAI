from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SkillFrequency:
    skill_id: str
    job_count: int
    job_share: float


@dataclass(frozen=True)
class CurrentSkillDemandSignal:
    signal: str
    job_family_id: str
    location_id: str
    period: str
    sample_size: int
    skills: list[SkillFrequency]
    confidence: str
    limitations: list[str]

    def to_dict(self) -> dict[str, object]:
        return {
            "signal": self.signal,
            "job_family_id": self.job_family_id,
            "location_id": self.location_id,
            "period": self.period,
            "sample_size": self.sample_size,
            "skills": [
                {
                    "skill_id": skill.skill_id,
                    "job_count": skill.job_count,
                    "job_share": skill.job_share,
                }
                for skill in self.skills
            ],
            "confidence": self.confidence,
            "limitations": list(self.limitations),
        }
