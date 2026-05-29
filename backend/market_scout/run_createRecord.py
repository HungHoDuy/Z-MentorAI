import asyncio
import sys
from pathlib import Path
import json

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
    
from backend.market_scout.pipelines import ExtractTrendPipeline, ExtractSalaryPipeline

trend_result = asyncio.run(ExtractTrendPipeline().run())
salary_result = asyncio.run(ExtractSalaryPipeline().run())

print(json.dumps(trend_result, indent=2))
print(json.dumps(salary_result, indent=2))