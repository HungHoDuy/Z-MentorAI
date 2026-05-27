import asyncio
import sys
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.market_scout.pipelines.ingest_sources_pipeline import IngestSourcesPipeline

result = asyncio.run(IngestSourcesPipeline().run())
summary = {
    key: value
    for key, value in result.items()
    if key not in {"documents"}
}
summary["documents"] = [
    {
        "title": document["source"]["title"],
        "url": document["source"]["url"],
        "document_type": document["document_type"],
        "cleaned_text_preview": document["cleaned_text"][:500],
    }
    for document in result["documents"]
]
print(json.dumps(summary, indent=2))
