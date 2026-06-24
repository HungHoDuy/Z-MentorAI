# Trend Tracker MVP Progress

## Mục đích

Tài liệu này ghi nhận tiến độ Trend Tracker MVP theo mô hình **Hybrid Market Intelligence**:

- Internal data trả lời current demand và current skill requirements.
- External evidence chỉ enrich external outlook hoặc automation exposure.
- Một snapshot tuần không được dùng để khẳng định thị trường tăng hoặc giảm.
- LLM chỉ diễn đạt evidence đã được dịch vụ deterministic chuẩn bị; không tự tạo trend score hay citation.

Trạng thái hiện tại: **đã hoàn thành step 1-7 ở mức code foundation; step 7 chưa có claim external đã xác minh để ghi Firestore.**

## Nền tảng dữ liệu đã có

| Collection | Trạng thái | Vai trò |
| --- | --- | --- |
| `data_for_vectorize` | Có dữ liệu crawl | JD raw đã clean từ CareerViet. |
| `trend_job_facts_v2` | Đã build | JD chuẩn hóa theo `job_category_id` và `job_family_id`. |
| `trend_snapshots_v2` | Đã build | Aggregate theo `job_family_id + location_id + week`. |
| `automation_risk_lookup` | Có seed MVP 12 category | Task-level automation exposure baseline có source metadata và caveat. |
| `trend_sources` | Chưa ingest | Metadata cho report/article đã review. |
| `trend_evidence` | Chưa ingest | Claim external đã review, liên kết tới `trend_sources`. |

Snapshot nội bộ đang có là `2026-W25`, từ `2026-06-15` đến `2026-06-21`. Đây là current-demand baseline, không phải directional trend.

## Quy tắc evidence xuyên suốt

1. Internal demand chỉ có ý nghĩa khi `active_job_count >= 10` và `distinct_company_count >= 3`.
2. Một snapshot chỉ trả current demand, không trả tăng/giảm.
3. `updated_job_count` chỉ là listing freshness; không phải số job mới hoặc hiring velocity đã xác minh.
4. External evidence phải khớp `job_family_id`, `location_id`, thời gian công bố và reliability threshold.
5. Automation exposure nói về task exposure; không phải dự báo role bị đào thải.
6. Category/family snapshot là membership metric: không cộng các family để suy ra tổng số JD thị trường.

## Step 1 - Trend Query Contract và Normalizer

**Trạng thái: Hoàn thành**

### Mục tiêu

Chuẩn hóa input của người dùng thành query xác định, chỉ cho phép các intent và entity mà MVP có dữ liệu trả lời.

### Đã triển khai

- `schemas/trend_query.py`
- `services/trend_query_normalizer.py`
- `tests/test_trend_query_normalizer.py`

### Chức năng

- Nhận các intent: `current_demand`, `current_skill_demand`, `automation_exposure`, `external_outlook`, `demand_pressure`.
- Normalize `job_category_id`, `job_family_id`, `location_id`.
- Map `job_category_id` sang `job_family_id` qua `JobCategoryTaxonomyService`.
- Reject trường hợp category và family mâu thuẫn.
- Chưa nhận role-level query vì chưa có Role Taxonomy.

### Output

`TrendQuery` có canonical `job_family_id`, optional `job_category_id`, `location_id` và intent.

## Step 2 - Trend Snapshot Repository

**Trạng thái: Hoàn thành**

### Mục tiêu

Đọc snapshot v2 mới nhất theo cohort `job_family_id + location_id`.

### Đã triển khai

- `schemas/trend_snapshot_read.py`
- `repositories/trend_snapshot_repository.py`
- `tests/test_trend_snapshot_repository.py`

### Chức năng

- Query `trend_snapshots_v2` theo family và location, lấy `period` mới nhất.
- Parse snapshot đúng schema v2.
- Tính freshness theo `period_end`: `fresh`, `aging`, `stale`.
- Tính sample status: `sufficient` hoặc `insufficient_evidence` theo threshold nội bộ.

### Lưu ý vận hành

Firestore cần composite index: `job_family_id ASC`, `location_id ASC`, `period DESC`.

## Step 3 - Trend Job Fact Repository

**Trạng thái: Hoàn thành**

### Mục tiêu

Lấy cohort JD active tương ứng với một snapshot để phục vụ skill frequency hoặc các signal dựa trên raw fact.

### Đã triển khai

- `repositories/trend_job_fact_repository.py`
- `tests/test_trend_job_fact_repository.py`

### Chức năng

- Query `trend_job_facts_v2` qua `job_family_ids array_contains`.
- Filter tiếp theo location, optional `job_category_id` và `source_expires_at >= snapshot.period_end`.
- Dedupe theo `job_key`, ưu tiên fact mới nhất.
- Không dựa vào trường `is_active` cũ; active được quyết định bằng expiry date tại mốc snapshot.

## Step 4 - Current Demand Service

**Trạng thái: Hoàn thành**

### Mục tiêu

Biến một snapshot đủ mẫu thành current-demand signal có thể giải thích.

### Đã triển khai

- `schemas/current_demand.py`
- `services/current_demand_service.py`
- `tests/test_current_demand_service.py`

### Rule

| Điều kiện | Output |
| --- | --- |
| `active_job_count < 10` hoặc `distinct_company_count < 3` | `insufficient_evidence`, `limited`, confidence `low` |
| Đạt minimum sample nhưng chưa đạt high threshold | `current_demand_moderate` |
| `active_job_count >= 25` và `distinct_company_count >= 10` | `current_demand_high` |

### Output

Signal luôn có active jobs, distinct companies, period, confidence và limitations. Không trả `increase`, `decrease` hoặc gọi kết quả là trend.

## Step 5 - Skill Frequency Service

**Trạng thái: Hoàn thành**

### Mục tiêu

Trả các skill được nhắc nhiều trong cohort JD active hiện tại.

### Đã triển khai

- `schemas/current_skill_demand.py`
- `services/skill_frequency_service.py`
- `tests/test_skill_frequency_service.py`

### Chức năng

- Đọc active facts qua `TrendJobFactRepository`.
- Ghép `requirements_text` và `description_text`.
- Normalize tiếng Việt không dấu, sau đó match keyword taxonomy theo job family.
- Mỗi skill tối đa được đếm một lần trên một JD.
- Trả `skill_id`, `job_count`, `job_share`, sample size và top-k skills.

### Taxonomy hiện có

- Common: Excel, English, Office productivity.
- `finance_legal`: IFRS, tax, SAP, Power BI, ACCA, CPA, CFA.
- `digital_telecom`: Python, Java, JavaScript, React, SQL, AWS, Docker, Kubernetes, Git.
- `operations`: ISO, HACCP, Lean, Six Sigma, ERP, SAP, WMS, TMS.
- `commercial`: CRM, sales, digital marketing, SEO, Google Ads.

### Giới hạn

Đây là `current_skill_demand`, không phải skill growth. Taxonomy còn cần mở rộng dần theo coverage thực tế của JD.

## Step 6 - Automation Risk Repository và Lookup MVP

**Trạng thái: Hoàn thành ở mức MVP**

### Mục tiêu

Trả task-level automation exposure theo `job_category_id`, có source và caveat rõ ràng.

### Đã triển khai

- `schemas/automation_risk.py`
- `repositories/automation_risk_repository.py`
- `services/automation_exposure_service.py`
- `services/automation_risk_seed.py`
- `pipelines/seed_automation_risk_lookup_pipeline.py`
- `run_seedAutomationRiskLookup.py`
- Tests automation lookup/service.

### Dữ liệu hiện có

- Seed 12 category phổ biến, ví dụ `accounting_audit`, `banking`, `administration_secretarial`, `customer_service`, `sales_business`, `marketing`, `logistics`, `software_it`.
- Mỗi record gồm `exposure_level`, `risk_reason`, `protected_tasks`, `at_risk_tasks`, source URL, published date và caveat.

### Output

- Có mapping: `automation_exposure`, confidence `medium`.
- Không có mapping: `insufficient_evidence`, confidence `low`.

### Giới hạn

Lookup hiện là curated global baseline, không phải Vietnam-specific measured risk. Không dùng để kết luận role sẽ bị thay thế. Coverage 12/70 category là intentional MVP scope; category còn lại cần evidence review trước khi được assess.

## Step 7 - Trend Evidence Repository và Manual Ingest

**Trạng thái: Code hoàn thành; dữ liệu external chưa ingest**

### Mục tiêu

Lưu report/article metadata riêng với từng claim để dùng cho `external_outlook`, không thay thế internal snapshot.

### Đã triển khai

- `schemas/trend_external_evidence.py`
- `repositories/trend_evidence_repository.py`
- `pipelines/ingest_trend_evidence_pipeline.py`
- `run_ingestTrendEvidence.py`
- `examples/trend_evidence_input.template.json`
- `tests/test_trend_evidence_repository.py`
- `tests/test_ingest_trend_evidence_pipeline.py`

### `trend_sources`

Một document/source gồm:

- `source_id`, title, publisher, `source_type`, URL.
- `published_at`, `fetched_at`, optional content hash.
- `reliability_score` từ 0 đến 1.
- `scope_location_ids` và `scope_period`.
- Notes về methodology, sample hoặc giới hạn nguồn.

### `trend_evidence`

Một document/claim gồm:

- `evidence_id`, `source_id`.
- `job_family_ids`, optional `job_category_ids`, `location_ids`, period.
- Direction, exact claim, optional metric value/unit.
- Citation cụ thể: trang, section, bảng hoặc stable anchor.
- Confidence của claim.

### Query rule

`TrendEvidenceRepository.list_for_external_outlook()` chỉ trả evidence khi:

1. Family khớp query.
2. Location khớp cả `trend_evidence.location_ids` và `trend_sources.scope_location_ids`.
3. Source đạt `min_reliability_score`.
4. Source không cũ hơn `published_after` nếu query có mốc này.

Kết quả được sort theo ngày công bố mới nhất và reliability cao hơn.

### Việc dữ liệu còn thiếu

Chưa có 8-12 claim external được verify để ghi vào Firestore. Không dùng các claim ví dụ trong solution document làm dữ liệu thật. Khi có report/PDF/URL đã kiểm tra, điền JSON template và chạy:

```powershell
python backend/market_scout/run_ingestTrendEvidence.py `
  --input backend/market_scout/examples/trend_evidence_input.template.json `
  --dry-run
```

Sau khi review output, bỏ `--dry-run` để ghi `trend_sources` và `trend_evidence`.

## Step 8 - Signal Synthesizer

**Trạng thái: Chưa bắt đầu**

### Mục tiêu

Orchestrate các service đã có theo intent và trả một evidence payload thống nhất cho response composer.

### Cần triển khai

- `current_demand`: snapshot repository -> `CurrentDemandService`.
- `current_skill_demand`: snapshot -> fact repository -> `SkillFrequencyService`.
- `automation_exposure`: normalized category -> `AutomationExposureService`.
- `external_outlook`: `TrendEvidenceRepository` với scope matching strict.
- `demand_pressure`: trả `out_of_scope` vì chưa có applicant volume, time-to-fill hoặc vacancy duration.
- Đảm bảo external evidence chỉ enrich context, không ghi đè internal metrics.

## Step 9 - Response Composer và LLM Summary Contract

**Trạng thái: Chưa bắt đầu**

### Mục tiêu

Biến deterministic signal payload thành response chatbot rõ ràng, có nguồn và limitations.

### Cần triển khai

- Template cho `current_demand`, `current_skill_demand`, `automation_exposure`, `external_outlook` và out-of-scope redirect.
- Render active job count, company count, period, sample/confidence và citation links.
- Bắt buộc nêu: một snapshot là current baseline, không phải trend.
- LLM chỉ viết summary dựa trên payload; không tự thêm metric, claim hay citation.

## Step 10 - Trend Tracker Flow, Agent Integration và QA

**Trạng thái: Chưa bắt đầu**

### Mục tiêu

Kết nối toàn bộ MVP vào `MarketScoutAgent` và kiểm thử end-to-end.

### Cần triển khai

- Tạo `flows/trend_tracker_flow.py` để orchestrate step 1-9.
- Inject repositories/services để test không cần Firestore thật.
- Route intent trend từ `agent.py` vào flow.
- Dry-run bộ câu hỏi gồm: đủ mẫu, thiếu mẫu, không có snapshot, không có category mapping, không có automation mapping, external evidence scope mismatch, supply-gap redirect.
- Kiểm tra source links, limitations và confidence trên mọi response.

## Kiểm thử hiện tại

Focused test suite cho các phần đã code đã chạy thành công: **23 passed**.

Pytest có warning quyền ghi `.pytest_cache`; warning này không ảnh hưởng kết quả test.

## Next Action

Step tiếp theo là **Step 8 - Signal Synthesizer**. Tuy nhiên, trước khi demo `external_outlook`, cần curate và verify 8-12 external claim thật ở Step 7 để collection có evidence hợp lệ.
