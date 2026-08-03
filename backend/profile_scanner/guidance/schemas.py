from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


GuidanceItem = Annotated[str, Field(min_length=8, max_length=500)]


class MiGuidance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    learning_profile_summary_vi: str = Field(min_length=20, max_length=700)
    learning_strategies_vi: list[GuidanceItem] = Field(min_length=2, max_length=5)
    application_examples_vi: list[GuidanceItem] = Field(default_factory=list, max_length=3)


class CareerAlignmentNarrative(BaseModel):
    model_config = ConfigDict(extra="forbid")

    executive_summary_vi: str = Field(min_length=20, max_length=900)
    strengths_vi: list[GuidanceItem] = Field(default_factory=list, max_length=4)
    watchouts_vi: list[GuidanceItem] = Field(default_factory=list, max_length=4)
    action_plan_vi: list[GuidanceItem] = Field(min_length=2, max_length=5)
    learning_strategy_vi: str = Field(default="", max_length=700)
