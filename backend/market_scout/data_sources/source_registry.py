from __future__ import annotations

import json
from pathlib import Path

from backend.market_scout.schemas import CrawlTarget


class SourceRegistry:
    def __init__(self, registry_path: str | Path | None = None) -> None:
        self.registry_path = Path(registry_path) if registry_path else Path(__file__).with_name("sources.json")

    def load(self, *, include_disabled: bool = False) -> list[CrawlTarget]:
        with self.registry_path.open("r", encoding="utf-8") as file:
            raw_sources = json.load(file)

        targets = [CrawlTarget(**item) for item in raw_sources]
        if include_disabled:
            return targets
        return [target for target in targets if target.enabled]
