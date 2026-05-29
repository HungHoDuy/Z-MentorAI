from dataclasses import asdict, dataclass, field
from typing import Any

from .entities import MarketScoutEntities


@dataclass
class MarketScoutRequest:
    user_query: str
    user_id: str | None = None
    session_id: str | None = None
    user_context: dict[str, Any] = field(default_factory=dict)
    entities_hint: MarketScoutEntities | None = None
    preferred_language: str = "vi"
    include_sources: bool = True
    max_sources: int = 5

    def __post_init__(self) -> None:
        self.user_query = self.user_query.strip()
        self.preferred_language = self.preferred_language.strip().lower()

        if not self.user_query:
            raise ValueError("User query must not be empty.")

        if self.max_sources < 0:
            raise ValueError("Max sources must be greater than or equal to 0.")

        if isinstance(self.entities_hint, dict):
            self.entities_hint = MarketScoutEntities(**self.entities_hint)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        if self.entities_hint:
            data["entities_hint"] = self.entities_hint.to_dict()
        return data