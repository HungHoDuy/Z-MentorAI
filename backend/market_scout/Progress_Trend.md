# Trend Tracker Progress

## Mục tiêu

Trend Tracker là nhánh Market Scout dùng để trả lời các câu hỏi về nhu cầu tuyển dụng hiện tại, kỹ năng đang được nhắc nhiều trong JD, mức độ automation exposure và external outlook có citation.

Nguyên tắc hiện tại:

- Dữ liệu nội bộ từ `trend_job_facts_v2` và `trend_snapshots_v2` là nguồn chính cho current demand/current skill demand.
- Một snapshot tuần chỉ được xem là current-demand baseline, không được kết luận thị trường đang tăng hoặc giảm.
- External evidence chỉ dùng để bổ sung bối cảnh hoặc outlook, không thay thế số liệu nội bộ.
- Automation exposure là đánh giá task-level exposure, không phải dự báo một nghề sẽ bị đào thải.
- LLM chỉ dùng để hiểu query và diễn đạt lại payload đã có evidence; không được tự tạo metric, citation hoặc trend score.

## Dữ liệu và collection hiện có

| Collection/File | Trạng thái | Vai trò |
| --- | --- | --- |
| `data_for_vectorize` | Có dữ liệu crawl | JD raw/clean từ CareerViet. |
| `trend_job_facts_v2` | Đã build | JD chuẩn hóa theo job category, job family, location, company, ngày cập nhật/hết hạn. |
| `trend_snapshots_v2` | Đã build | Aggregate theo `job_family_id + location_id + week`. |
| `automation_risk_lookup` | Đã seed MVP | Lookup automation exposure theo `job_category_id`. |
| `trend_sources` | Đã có pipeline ingest | Metadata nguồn external report/article. |
| `trend_evidence` | Đã có pipeline ingest | Claim external có citation và source link. |
| `data/vietnam_locations.json` | Đã thêm | Local taxonomy 63 tỉnh/thành Việt Nam để resolve location. |

Snapshot nội bộ hiện dùng là `2026-W25`, giai đoạn `2026-06-15` đến `2026-06-21`. Đây là baseline một tuần, chưa đủ để tính MoM/QoQ.

## Rule evidence

1. Current demand chỉ đủ mẫu khi `active_job_count >= 10` và `distinct_company_count >= 3`.
2. Không trả `increase/decrease` khi mới có một snapshot.
3. `updated_job_count` chỉ phản ánh listing freshness, không phải số job mới được đăng.
4. `job_family_id` dùng để query snapshot ổn định vì snapshot hiện aggregate theo family + location.
5. `job_category_id` dùng để narrow query, automation exposure và lọc fact khi cần.
6. Role tự nhiên như `backend engineer`, `bác sĩ`, `kế toán tổng hợp` chưa có role-level snapshot riêng; cần role resolver/hybrid search để map về category/family.

## Step 1 - Job Category Taxonomy và Fact Normalize v2

**Trạng thái: Hoàn thành**

### Đã triển khai

- `schemas/trend_tracker/job_category_taxonomy.py`
- `services/trend_tracker/job_category_taxonomy_service.py`
- `services/trend_tracker/job_category_trend_job_fact_normalizer.py`
- `pipelines/trend_tracker/profile_job_category_labels_pipeline.py`
- `pipelines/trend_tracker/normalize_job_category_trend_job_facts_pipeline.py`

### Chức năng

- Profile raw `Ngành nghề` từ `data_for_vectorize`.
- Map label ngành nghề raw sang `job_category_id` và `job_family_id`.
- Tạo `trend_job_facts_v2` với các field chính: `raw_job_category_labels`, `job_category_ids`, `job_family_ids`, `location_ids`, `company_key`, `source_updated_at`, `source_expires_at`, `requirements_text`, `description_text`, `taxonomy_version`.

## Step 2 - Build Job Family Trend Snapshots v2

**Trạng thái: Hoàn thành**

### Đã triển khai

- `schemas/trend_tracker/job_family_trend_snapshot.py`
- `services/trend_tracker/job_family_trend_snapshot_builder.py`
- `pipelines/trend_tracker/build_job_family_trend_snapshots_pipeline.py`
- `run_buildJobFamilyTrendSnapshots.py`

### Chức năng

- Build `trend_snapshots_v2` theo `job_family_id + location_id + period`.
- Tính `observed_job_count`, `active_job_count`, `unknown_active_job_count`, `updated_job_count`, `distinct_company_count`, `source_job_counts`.
- Không build snapshot theo từng role tự nhiên để tránh dữ liệu quá phân mảnh.

## Step 3 - Trend Query Contract và Normalizer

**Trạng thái: Hoàn thành**

### Đã triển khai

- `schemas/trend_tracker/trend_query.py`
- `services/trend_tracker/trend_query_normalizer.py`
- `tests/test_trend_query_normalizer.py`

### Chức năng

- Nhận các intent: `current_demand`, `current_skill_demand`, `automation_exposure`, `external_outlook`, `demand_pressure`.
- Normalize `job_category_id`, `job_family_id`, `location_id`.
- Map `job_category_id` sang `job_family_id` qua `JobCategoryTaxonomyService`.
- Reject category/family mâu thuẫn.

## Step 4 - Repository Layer

**Trạng thái: Hoàn thành**

### Đã triển khai

- `repositories/trend_tracker/trend_snapshot_repository.py`
- `repositories/trend_tracker/trend_job_fact_repository.py`
- `repositories/trend_tracker/automation_risk_repository.py`
- `repositories/trend_tracker/trend_evidence_repository.py`

### Chức năng

- `TrendSnapshotRepository`: lấy snapshot mới nhất theo `job_family_id + location_id`.
- `TrendJobFactRepository`: lấy active facts cho một snapshot, có thể lọc thêm `job_category_id`.
- `AutomationRiskRepository`: lookup automation exposure theo category.
- `TrendEvidenceRepository`: query external evidence theo family, location, reliability và published date.

### Lưu ý vận hành

Firestore cần composite index cho snapshot query: `job_family_id ASC`, `location_id ASC`, `period DESC`.

## Step 5 - Current Demand Service

**Trạng thái: Hoàn thành**

### Đã triển khai

- `schemas/trend_tracker/current_demand.py`
- `services/trend_tracker/current_demand_service.py`
- `tests/test_current_demand_service.py`

### Rule hiện tại

| Điều kiện | Output |
| --- | --- |
| Không đủ `active_job_count >= 10` hoặc `distinct_company_count >= 3` | `insufficient_evidence`, confidence `low` |
| Đủ minimum sample nhưng chưa đạt high threshold | `current_demand_moderate` |
| `active_job_count >= 25` và `distinct_company_count >= 10` | `current_demand_high` |

Kết quả là current demand, không phải directional trend.

## Step 6 - Current Skill Demand Service

**Trạng thái: Hoàn thành**

### Đã triển khai

- `schemas/trend_tracker/current_skill_demand.py`
- `services/trend_tracker/skill_frequency_service.py`
- `tests/test_skill_frequency_service.py`

### Chức năng

- Lấy active facts từ `trend_job_facts_v2`.
- Ghép `requirements_text` và `description_text`.
- Match keyword taxonomy theo family.
- Trả top skills với `job_count`, `job_share`, `sample_size`.

### Giới hạn

Đây là `current_skill_demand`, không phải skill growth. Skill taxonomy vẫn còn cần mở rộng theo coverage dữ liệu thực tế.

## Step 7 - Automation Exposure

**Trạng thái: Hoàn thành MVP**

### Đã triển khai

- `schemas/trend_tracker/automation_risk.py`
- `services/trend_tracker/automation_exposure_service.py`
- `services/trend_tracker/automation_risk_seed.py`
- `pipelines/trend_tracker/seed_automation_risk_lookup_pipeline.py`
- `run_seedAutomationRiskLookup.py`

### Chức năng

- Lookup theo `job_category_id`, không lookup theo family chung chung.
- Output gồm `exposure_level`, `risk_reason`, `protected_tasks`, `at_risk_tasks`, source URL/published date/caveat.
- Nếu không có mapping thì trả `insufficient_evidence`.

## Step 8 - External Evidence Ingest

**Trạng thái: Code hoàn thành; dữ liệu phụ thuộc manual ingest**

### Đã triển khai

- `schemas/trend_tracker/trend_external_evidence.py`
- `pipelines/trend_tracker/ingest_trend_evidence_pipeline.py`
- `run_ingestTrendEvidence.py`
- `examples/trend_evidence_input.template.json`
- `tests/test_trend_evidence_repository.py`
- `tests/test_ingest_trend_evidence_pipeline.py`

### Chức năng

- Tách `trend_sources` và `trend_evidence`.
- Mỗi claim có citation, direction, metric optional, confidence và link về source.
- Query external outlook có filter reliability và location scope.

## Step 9 - Hybrid Signal Service

**Trạng thái: Hoàn thành**

### Đã triển khai

- `schemas/trend_tracker/hybrid_signal.py`
- `services/trend_tracker/hybrid_signal_service.py`

### Chức năng

Orchestrate bốn nhóm output:

- `current_demand`
- `current_skill_demand`
- `automation_exposure`
- `external_outlook`

Rule chính:

- Không có snapshot hoặc snapshot thiếu sample -> `insufficient_evidence`.
- Một snapshot -> `directional_trend = false`.
- Có external evidence phù hợp -> confidence có thể `medium`.
- Internal-only -> confidence `low`.
- `demand_pressure` hiện trả `out_of_scope` vì thiếu applicant volume/time-to-fill/vacancy duration.

## Step 10 - Trend Tracker Flow và Agent Integration

**Trạng thái: Hoàn thành MVP**

### Đã triển khai

- `flows/trend_tracker_flow.py`
- `services/trend_tracker/trend_summary_service.py`
- `services/trend_tracker/trend_llm_summary_service.py`
- `prompts/trend_summary_system_prompt.txt`
- `run_trendTracker.py`
- Integration trong `agent.py` và `main.py`.
- `tests/test_trend_tracker_flow.py`
- `tests/test_trend_agent_integration.py`

### Chức năng

- Normalize query.
- Retrieve snapshot/facts/automation/external evidence theo intent.
- Gọi `HybridSignalService`.
- Trả structured result cho summary layer.
- Có structured log từng step trong `TrendTrackerFlow` gồm duration, sub-agent, category/family/location và signal.

## Step 11 - Query Understanding Service

**Trạng thái: Hoàn thành foundation**

### Đã triển khai

- `schemas/market_scout_query_understanding.py`
- `services/market_scout_query_understanding_service.py`
- `prompts/market_scout_query_understanding_system_prompt.txt`
- `local_scripts/trend_tracker/run_queryUnderstanding.py`
- `tests/test_market_scout_query_understanding_service.py`

### Chức năng

- Classify intent cấp Market Scout: `salary_benchmark`, `trend_tracker`, `unclear`.
- Nếu là salary: tận dụng `SalaryQueryNormalizer` để extract `job_title`, `location`, `experience_years`.
- Nếu là trend: dùng LLM structured output để extract `trend_intent`, `role_mention`, `location_text`, `job_category_hint`, `job_family_hint`, `requested_signal`.
- Có fallback heuristic cho trend intent như automation/AI replacement, skill demand, forecast/outlook.

### Local test

```powershell
& F:\Z-MentorAI\venv\Scripts\python.exe backend/market_scout/local_scripts/trend_tracker/run_queryUnderstanding.py `
  --query "Nhu cầu tuyển dụng backend engineer tại Hà Nội có cao không?"
```

## Step 12 - Location Resolver Production Foundation

**Trạng thái: Hoàn thành**

### Đã triển khai

- `data/vietnam_locations.json`
- `schemas/trend_tracker/location_resolution.py`
- `services/trend_tracker/location_resolver_service.py`
- `tests/test_location_resolver_service.py`

### Chức năng

- Resolve location bằng local taxonomy 63 tỉnh/thành Việt Nam.
- Hỗ trợ alias phổ biến như `HN`, `Hà Nội`, `HCM`, `TP Hồ Chí Minh`, `Sài Gòn`.
- Output gồm `location_id`, `canonical_name`, `matched_text`, `confidence`, `resolution_method`.

## Step 13 - Structured Category/Family Mapping

**Trạng thái: Hoàn thành**

### Đã triển khai

- Cập nhật `services/trend_tracker/trend_entity_extractor_service.py`.
- Cập nhật `_TREND_ENTITY_FIELDS` trong `agent.py` để nhận thêm `job_category_hint`, `job_family_hint`.
- Cập nhật tests liên quan trong `tests/test_trend_entity_extractor_service.py`.

### Chức năng

- Nếu query understanding hoặc orchestrator gửi category/family rõ, hệ thống map trực tiếp bằng `JobCategoryTaxonomyService`.
- Hỗ trợ input: `job_category_id`, `job_category`, `job_category_hint`, `job_family_id`, `job_family_hint`.
- Nếu category resolve được, tự suy ra `job_family_id` tương ứng.
- Nếu không có structured hint, vẫn fallback qua text/category alias/legacy `industry`/role alias/location resolver.

### Test đã chạy gần nhất

```powershell
$env:PYTHONPATH='.'
& F:\Z-MentorAI\venv\Scripts\python.exe -m pytest `
  backend/market_scout/tests/test_trend_entity_extractor_service.py `
  backend/market_scout/tests/test_trend_agent_integration.py `
  backend/market_scout/tests/test_trend_query_normalizer.py `
  -q
```

Kết quả: `14 passed`.

## Pending - Role Semantic Lookup từ `trend_job_facts_v2`

**Trạng thái: Chưa triển khai**

Đây là phần quan trọng tiếp theo để xử lý các câu hỏi role tự nhiên, ví dụ:

- `backend engineer tại Hà Nội có đang tuyển nhiều không?`
- `bác sĩ ở Hồ Chí Minh nhu cầu có cao không?`
- `kế toán tổng hợp ở Đà Nẵng có dễ tìm việc không?`

### Hướng làm đề xuất

1. LLM query understanding lấy `role_mention` và `location_text`.
2. Location resolver map `location_text` -> `location_id`.
3. Nếu có `job_category_hint` hoặc `job_family_hint`, map trực tiếp bằng taxonomy.
4. Nếu chỉ có `role_mention`, search hybrid vào `trend_job_facts_v2`:
   - keyword trên `job_title`, `requirements_text`, `description_text`
   - semantic search nếu đã embedding/index fact text
5. Aggregate top-k facts để suy ra category/family có evidence mạnh nhất.
6. Dùng category/family/location đã resolve để query `trend_snapshots_v2`.
7. Trả structured evidence gồm snapshot-level demand và role-level matched facts để summary layer diễn đạt.

### Cần quyết định trước khi code

- Dùng embedding/index nào cho `trend_job_facts_v2`: Firestore vector, Vertex Matching Engine, hoặc index nội bộ hiện có.
- Text embedding nên lấy từ `job_title + raw category + requirements + description`.
- Top-k mặc định user muốn: `5`.
- Cần threshold để tránh map sai role khi top-k quá yếu.

## Các câu hỏi Trend Tracker hiện trả lời tốt nhất

Các câu hỏi có category/family/location rõ hoặc resolve được:

- `Nhu cầu tuyển dụng sales tại Hải Dương có cao không?`
- `Ngành banking tại Hà Nội có nhu cầu tuyển dụng cao không?`
- `Kỹ năng nào đang được nhắc nhiều trong nhóm CNTT tại Hồ Chí Minh?`
- `Công việc kế toán có automation exposure như thế nào?`

Các câu hỏi role tự nhiên hiện còn hạn chế nếu không map được role sang category/family:

- `backend engineer tại Hà Nội có đang tuyển nhiều không?`
- `bác sĩ ở Hà Nội có nhu cầu cao không?`

## Verification hiện tại

Các test đã được thêm/cập nhật quanh những phần chính:

- Query normalizer
- Snapshot repository
- Job fact repository
- Current demand
- Skill frequency
- Automation exposure
- Trend evidence ingest/repository
- Hybrid signal/Trend flow
- Agent integration
- Query understanding
- Location resolver
- Trend entity extractor

Khi sửa tiếp role resolver, cần thêm test cho:

- Role mention -> top-k fact matches
- Aggregate top-k -> category/family winner
- Low-confidence/no-match -> `insufficient_evidence`
- End-to-end trend query role tự nhiên -> snapshot result

## Next Action

Bước tiếp theo nên làm là **Role Semantic Lookup từ `trend_job_facts_v2`**. Mục tiêu là bỏ phụ thuộc vào alias hardcode cho role và cho phép query tự nhiên map về category/family bằng evidence từ JD hiện có.