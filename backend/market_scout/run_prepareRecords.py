import asyncio
import sys
from pathlib import Path
import json

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.market_scout.pipelines import PrepareRecordsPipeline

result = asyncio.run(PrepareRecordsPipeline().run())
print(json.dumps(result, indent=2))