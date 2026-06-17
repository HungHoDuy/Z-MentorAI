from dataclasses import asdict, dataclass, field
from typing import Any

from .enums import DataSourceType, SourceType


def _enum_value(value: Any) -> Any:
    return value.value if hasattr(value, "value") else value


@dataclass
class Source:
    title: str
    url: str
    id: str | None = None
    source_type: SourceType = SourceType.OTHER
    data_source: DataSourceType = DataSourceType.WEB_SEARCH
    publisher: str | None = None
    published_date: str | None = None
    reliability_score: float | None = None
    collected_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.title = self.title.strip()
        self.url = self.url.strip()

        if not self.title:
            raise ValueError("Source title must not be empty.")

        if not self.url:
            raise ValueError("Source url must not be empty.")

        if isinstance(self.source_type, str):
            self.source_type = SourceType(self.source_type)

        if isinstance(self.data_source, str):
            self.data_source = DataSourceType(self.data_source)

        if self.reliability_score is not None:
            self.reliability_score = max(0.0, min(1.0, self.reliability_score))

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["source_type"] = _enum_value(self.source_type)
        data["data_source"] = _enum_value(self.data_source)
        return data


@dataclass
class Evidence:
    content: str
    source: Source
    relevance_score: float = 0.0
    extracted_values: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.content = self.content.strip()

        if not self.content:
            raise ValueError("Evidence content must not be empty.")

        self.relevance_score = max(0.0, min(1.0, self.relevance_score))

    def to_dict(self) -> dict[str, Any]:
        return {
            "content": self.content,
            "source": self.source.to_dict(),
            "relevance_score": self.relevance_score,
            "extracted_values": self.extracted_values,
        }