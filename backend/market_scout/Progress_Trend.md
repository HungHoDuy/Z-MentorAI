# Trend Tracker Progress

## Current Scope

Trend Tracker is now scoped to two product outputs:

- `current_demand`: answer whether a specific role/job has active hiring demand now.
- `external_outlook`: answer future-oriented market questions from curated evidence and allowlisted live web search.

Removed from runtime scope:

- `automation_exposure`: deleted as a standalone branch. AI replacement / automation / decline-risk questions are now routed to `external_outlook` instead.

## Data Collections

| Collection/File | Role |
| --- | --- |
| `trend_job_facts_v2` | Normalized job facts from JD data, including job title, company, locations, active status, category/family tags, requirements and description text. |
| `trend_snapshots_v2` | Broad aggregate snapshots by `job_family_id + location_id + period`; retained for broad context, but role-level current demand is based on matching job facts. |
| `job_mapping_embedding` | Embeddings for job mapping and role-level search. |
| `trend_sources` | Metadata for curated external reports/articles. |
| `trend_evidence` | Extracted external outlook claims with source/citation metadata. |
| `data/vietnam_locations.json` | Local taxonomy for Vietnam location resolution. |

## Runtime Flow

1. `MarketScoutQueryUnderstandingService` classifies the user question.
2. If the question is salary-related, route to Salary Benchmark.
3. If the question is trend-related, extract `trend_intent`, `role_mention`, `location_text`, `job_category_hint`, and `job_family_hint`.
4. `LocationResolverService` normalizes location text to `location_id` when present.
5. If a clear category/family exists, `JobCategoryTaxonomyService` maps it to the internal taxonomy.
6. If only a natural role exists, `RoleFactSearchService` searches `trend_job_facts_v2` and `job_mapping_embedding`, then resolves the most likely category/family with confidence gates.
7. For role-level `current_demand`, the service counts matched active JDs and distinct companies from role-level matches, not just broad family snapshots.
8. For `external_outlook`, the service uses allowlisted Tavily web search first. Cached `trend_evidence` is used only as fallback when live search returns no evidence or times out/errors.
9. `HybridSignalService` builds a structured signal.
10. `TrendSummaryService` / `TrendLLMSummaryService` writes the final user-facing answer from evidence only.

## Implemented Components

- `schemas/trend_tracker/trend_query.py`
- `schemas/trend_tracker/current_demand.py`
- `schemas/trend_tracker/current_skill_demand.py`
- `schemas/trend_tracker/hybrid_signal.py`
- `schemas/trend_tracker/role_fact_match.py`
- `schemas/trend_tracker/role_resolution.py`
- `services/trend_tracker/current_demand_service.py`
- `services/trend_tracker/skill_frequency_service.py`
- `services/trend_tracker/job_category_taxonomy_service.py`
- `services/trend_tracker/location_resolver_service.py`
- `services/trend_tracker/role_fact_search_service.py`
- `services/trend_tracker/hybrid_signal_service.py`
- `services/trend_tracker/allowlisted_web_search_service.py`
- `services/trend_tracker/external_outlook_live_search_service.py`
- `flows/trend_tracker_flow.py`

## Current Demand Rules

Role-level current demand is based on matched active job facts:

- Enough evidence requires a meaningful number of matched active JDs and distinct companies.
- Demand level is a current market signal only.
- The answer must not claim the market is increasing or decreasing unless future trend evidence explicitly supports it.

## External Outlook Rules

External outlook uses evidence from configured sources and live allowlisted search:

- Live allowlisted search is used first for external outlook questions.
- Live search is restricted to configured trusted domains.
- Cached evidence is fallback only when live search has no usable result or errors. External claims are context, not a replacement for internal job facts.
- AI replacement / automation questions are handled here, without predicting that a role will disappear.

## Local Test Commands

Current demand:

```powershell
& F:\Z-MentorAI\venv\Scripts\python.exe backend/market_scout/local_scripts/trend_tracker/run_currentDemandQuestion.py
```

Trend tracker CLI:

```powershell
& F:\Z-MentorAI\venv\Scripts\python.exe backend/market_scout/run_trendTracker.py `
  --query "business analyst tai Ha Noi co dang tuyen nhieu khong?"
```

External outlook ingest:

```powershell
& F:\Z-MentorAI\venv\Scripts\python.exe backend/market_scout/run_ingestExternalOutlook.py `
  --verbose
```

