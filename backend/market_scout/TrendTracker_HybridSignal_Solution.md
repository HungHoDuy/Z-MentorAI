# TrendTracker — Hybrid Signal Solution
**Dành cho:** Demo trong 1 tuần với chỉ 1 tuần snapshot data
**Phiên bản:** v2.0 — 2026-06-23 (revised per review)

---

## 1. Bối Cảnh & Vấn Đề

### Tình trạng hiện tại
- Pipeline đã chạy: `data_for_vectorize` → `trend_job_facts_v2` → `trend_snapshots_v2` ✅
- Số tuần snapshot: **1 tuần** (current week only)
- Demo deadline: **1 tuần**
- Output cần: **Chatbot / conversational agent** trả lời câu hỏi về thị trường lao động

### Vấn đề cốt lõi
Theo Evidence Rules trong spec:

> *1 snapshot → Current demand baseline, không gọi là trend.*
> *Không tạo directional signal nếu không đạt minimum sample.*

Nếu chỉ dùng internal data, chatbot **không được phép** đưa ra directional signal (tăng/giảm). Demo sẽ không đủ thuyết phục.

### Định vị đúng cho demo
**Hybrid Market Intelligence** — không phải "Trend Tracker xác nhận tăng/giảm từ dữ liệu nội bộ". Contract với người dùng là:

> *"Internal current demand + External market outlook/exposure — với limitations rõ ràng."*

---

## 2. Architecture Tổng Quan

```
┌─────────────────────────────┐    ┌──────────────────────────────────┐
│   INTERNAL DATA (1 tuần)    │    │   EXTERNAL EVIDENCE (curated)    │
│                             │    │                                  │
│  trend_snapshots_v2         │    │  trend_sources (metadata)        │
│  - active_job_count         │    │  - publisher, source_type        │
│  - distinct_company_count   │    │  - published_at, reliability     │
│  - observed_job_count       │    │  - scope (geography, period)     │
│  - updated_job_count        │    │                                  │
│    (secondary signal only)  │    │  trend_evidence (per-claim)      │
│                             │    │  - exact_claim, metric_value     │
│  trend_job_facts_v2         │    │  - entity, geography, period     │
│  - requirements_text        │    │  - direction, citation           │
│  - job_category_ids         │    │                                  │
│  - job_family_ids           │    │  automation_exposure_lookup      │
└──────────────┬──────────────┘    │  - task-level mapping            │
               │                   │  - occupation → category         │
               │                   │  - citation per task             │
               │                   └──────────────┬───────────────────┘
               └──────────────┬───────────────────┘
                              ▼
               ┌──────────────────────────────┐
               │     Signal Synthesizer       │
               │  (deterministic rules-based) │
               │                              │
               │  3 intents (MVP):            │
               │  - current_demand            │
               │  - skill_frequency           │
               │  - automation_exposure       │
               │                              │
               │  Output: signal              │
               │          confidence          │
               │          sources[]           │
               │          limitations[]       │
               └──────────────┬───────────────┘
                              ▼
               ┌──────────────────────────────┐
               │       LLM Summarizer         │
               │   (chatbot response layer)   │
               │                              │
               │  - Tổng hợp evidence         │
               │  - Trình bày limitations     │
               │  - KHÔNG tự chấm score       │
               └──────────────────────────────┘
```

---

## 3. MVP Scope — 3 Intents

**Supply gap bị loại khỏi MVP.** `listing_refresh_rate` và `distinct_company_count` chỉ đo demand-side; không chứng minh được "thiếu người". Supply gap chỉ khả thi khi có applicant volume, time-to-fill, offer acceptance rate, vacancy duration, hoặc survey shortage có scope tương ứng — tất cả đều chưa có.

| Intent | Tên hiển thị | Data source chính | Khả dụng ngay |
|---|---|---|---|
| `current_demand` | Current Demand Baseline | Internal snapshot | ✅ |
| `skill_frequency` | Current Skill Requirements | Internal facts (requirements_text) | ✅ |
| `automation_exposure` | Automation Exposure | External lookup (task-level, có citation) | ✅ (coverage ~10–15 category) |
| ~~`supply_gap`~~ | ~~Supply Gap~~ | Cần applicant data | ❌ Hoãn |

---

## 4. External Evidence — Schema & Nguồn

### 4.1 Tách hai collection: `trend_sources` và `trend_evidence`

**Lý do tách:** Nếu gộp chung, LLM rất dễ dùng một report quốc gia để corroborate một family/location không cùng scope. Phải tách metadata nguồn (ai viết, khi nào, phạm vi gì) khỏi từng claim cụ thể (nói về gì, ở đâu, chiều nào).

**`trend_sources` — metadata nguồn:**

```json
{
  "source_id": "navigos-q2-2026",
  "source_name": "Navigos Group Market Report Q2/2026",
  "publisher": "Navigos Group",
  "source_type": "labor_market_report",
  "published_at": "2026-04-15",
  "fetched_at": "2026-06-20",
  "content_hash": "sha256:abc123...",
  "reliability_score": 0.8,
  "scope_geography": ["ho-chi-minh", "ha-noi"],
  "scope_period": "2026-Q2",
  "url": "https://navigos.com/...",
  "notes": "Báo cáo quý, phủ HCM và HN, sample ~5000 JD"
}
```

**`trend_evidence` — từng claim cụ thể:**

```json
{
  "evidence_id": "navigos-q2-2026-ev001",
  "source_id": "navigos-q2-2026",
  "job_family_ids": ["finance_legal"],
  "job_category_ids": ["accounting_audit"],
  "location_ids": ["ho-chi-minh"],
  "period": "2026-Q2",
  "direction": "increase",
  "exact_claim": "Nhu cầu tuyển dụng Kế toán - Tài chính tại HCM tăng 18% so với Q1/2026.",
  "metric_value": 18,
  "metric_unit": "percent_qoq",
  "citation": "Navigos Q2/2026, trang 12, mục 'Finance & Accounting'",
  "confidence": "medium"
}
```

> **Rule:** LLM chỉ được dùng evidence khi `scope_geography` và `job_family_ids` khớp với query. Không dùng report quốc gia để corroborate tín hiệu địa phương cụ thể.

### 4.2 Nguồn nên curate cho demo

| Nguồn | source_type | Scope | Ưu tiên |
|---|---|---|---|
| Navigos Group Market Report Q2/2026 | labor_market_report | HCM + HN | 🔴 Cao |
| CareerViet Insight Report Q2/2026 | platform_insight | Toàn quốc | 🔴 Cao |
| Manpower Vietnam Employment Outlook Q3/2026 | employment_outlook | Toàn quốc | 🟠 Trung bình |
| VietnamWorks InSight | platform_insight | Toàn quốc | 🟠 Trung bình |
| GSO Labor Force Survey 2025 | government_survey | Toàn quốc | 🟡 Thấp (macro) |

**Target cho MVP:** 2–3 nguồn, mỗi nguồn 3–5 evidence claims có `exact_claim` và `citation` cụ thể. Không cần 20 snippets mơ hồ — cần 10 claims chính xác có thể cite.

---

## 5. Automation Exposure Lookup

### 5.1 Thiết kế lại: task-level mapping, không phải category-level score

**Vấn đề của v1:** Gán `risk_score: 0.78` cho toàn bộ `accounting_audit` là false precision — OECD/McKinsey đánh giá theo occupation và task, không phải CareerViet job category. Các ID như `legal_compliance`, `data_ai`, `logistics_supply_chain` cũng không phải job_category_id v2 thực tế.

**Cách đúng:** Map occupation/task từ research → job_category_id v2 thực tế → liệt kê task cụ thể có citation, không gán numeric score tổng.

**Schema `automation_exposure_lookup`:**

```json
{
  "lookup_id": "accounting_audit__data-entry",
  "job_category_id": "accounting_audit",
  "job_family_id": "finance_legal",
  "task_name": "Data entry và basic reconciliation",
  "exposure_level": "HIGH",
  "exposure_reason": "Rule-based, repetitive, fully codifiable — phù hợp RPA/AI.",
  "source_occupation": "Bookkeepers and Accounting Clerks (SOC 43-3031)",
  "citation": "McKinsey Global Institute, 'Jobs Lost, Jobs Gained', 2023, Exhibit 4",
  "mapping_note": "Mapped từ SOC occupation → CareerViet category accounting_audit (v1 taxonomy)",
  "last_updated": "2026-06-01"
}
```

Mỗi category có thể có **nhiều task rows** — task nào HIGH, task nào PROTECTED. Không gán một score duy nhất cho cả category.

### 5.2 Category nên cover cho demo (~10–15 category có citation rõ)

Chỉ map những category có occupation tương đương trong OECD/McKinsey research. Để trống còn hơn gán sai.

| `job_category_id` (v2 taxonomy) | Task mẫu có citation | Exposure |
|---|---|---|
| `accounting_audit` | Data entry, standard reconciliation | HIGH |
| `accounting_audit` | Tax strategy, M&A audit judgment | PROTECTED |
| `software_it` | Boilerplate code generation | MEDIUM |
| `software_it` | System architecture, novel problem solving | PROTECTED |
| `quality_assurance` | Visual inspection (image-based) | MEDIUM-HIGH |
| `quality_assurance` | Process design, root cause analysis | PROTECTED |

> **Lưu ý bắt buộc:** Mọi mapping phải kèm `citation` chỉ đến trang/exhibit cụ thể. Nếu không có citation → không thêm vào lookup.

### 5.3 Fallback khi không có mapping

```python
def get_automation_exposure(job_category_id: str) -> dict:
    tasks = lookup_tasks(job_category_id)
    if not tasks:
        return {
            "signal": "insufficient_evidence",
            "reason": f"Chưa có automation exposure mapping cho '{job_category_id}' với citation đã kiểm chứng.",
            "confidence": None
        }
    return {
        "signal": "automation_exposure_available",
        "tasks": tasks,
        "confidence": "medium"
    }
```

---

## 6. Cross-Sectional Signal từ Internal Snapshot

### 6.1 Demand Breadth (signal hợp lệ)

```python
# Đo mức độ demand rải rộng trên nhiều employer
# Cao → market-wide demand; Thấp → demand tập trung vào ít công ty

demand_breadth = distinct_company_count / active_job_count
# Ví dụ: 46 công ty / 92 JD = 0.5 → demand khá phân tán
```

### 6.2 Relative Demand Ranking (cross-sectional, không phải trend)

```python
# So sánh active_job_count giữa các job_family trong cùng location
# Đây là current state ranking — không suy ra tăng/giảm

# Ví dụ HCM W25:
# software_it:    450 active JD, 180 companies → Rank 1
# finance_legal:   92 active JD,  46 companies → Rank 2
# operations:      78 active JD,  35 companies → Rank 3
```

**Caveat bắt buộc:** Một JD nhiều category có thể đóng góp vào nhiều family. Các family cũng có độ rộng định nghĩa khác nhau. Không dùng ranking như market share. Chỉ trả số tuyệt đối (JD count, company count) kèm caveat membership bias.

### 6.3 Listing Refresh Rate (secondary signal — dùng thận trọng)

```python
# KHÔNG gọi là "listing momentum" hay "market heat"
# updated_job_count có thể là platform auto-refresh, không phải employer tăng hiring

listing_refresh_rate = updated_job_count / observed_job_count
```

**Quy tắc sử dụng:**
- Chỉ dùng như secondary signal, không dùng để corroborate supply shortage hoặc automation risk
- Luôn kèm caveat: *"updated_job_count phản ánh listing freshness, không xác nhận là JD mới đăng"*
- Không dùng metric này để kết luận market đang "sôi động"

---

## 7. Signal Synthesizer — Logic Chi Tiết

### 7.1 Query Intent Mapping (MVP — 3 intents)

| Câu hỏi người dùng | Intent | Primary Source |
|---|---|---|
| "Job nào đang có nhu cầu cao?" | `current_demand` | Internal snapshot |
| "Ngành nào đang tuyển nhiều?" | `current_demand` | Internal snapshot |
| "Job [X] có bị AI thay thế không?" | `automation_exposure` | External lookup (task-level) |
| "Ngành nào đang thiếu người?" | → Redirect | Giải thích chưa đủ data supply-side |

### 7.2 Synthesizer Rules

```python
def build_signal(job_family_id: str, location_id: str, intent: str) -> dict:
    snapshot = get_snapshot(job_family_id, location_id, "latest")

    # Minimum sample check — giữ nguyên từ Evidence Rules
    if snapshot["active_job_count"] < 10 or snapshot["distinct_company_count"] < 3:
        return {
            "signal": "insufficient_evidence",
            "confidence": None,
            "reason": "Không đủ minimum sample (active_job_count < 10 hoặc distinct_company_count < 3)."
        }

    if intent == "current_demand":
        # Tìm evidence có scope khớp với family + location
        evidence = get_evidence(
            job_family_ids=[job_family_id],
            location_ids=[location_id]
        )
        return {
            "signal": "current_demand_baseline",
            "confidence": "medium" if evidence else "low",
            "internal_basis": {
                "active_job_count": snapshot["active_job_count"],
                "distinct_company_count": snapshot["distinct_company_count"],
                "demand_breadth": snapshot["distinct_company_count"] / snapshot["active_job_count"],
                "period": snapshot["period"]
            },
            "external_corroboration": evidence or None,
            "limitations": [
                "1 tuần snapshot — đây là current demand baseline, không phải directional trend.",
                "Ranking có membership bias: một JD nhiều category có thể xuất hiện ở nhiều family.",
                "Cần ít nhất 2 tuần để có WoW preliminary signal."
            ]
        }

    if intent == "skill_frequency":
        skills = extract_skill_frequency(job_family_id, location_id)
        return {
            "signal": "current_skill_requirements",
            "confidence": "medium",
            "skill_counts": skills,
            "jd_count": snapshot["active_job_count"],
            "limitations": [
                "Dựa trên keyword matching từ requirements_text — có thể bỏ sót skill viết khác từ.",
                "Đây là current requirement snapshot, không phải skill growth trend."
            ]
        }

    if intent == "automation_exposure":
        exposure = get_automation_exposure(job_family_id)
        if exposure["signal"] == "insufficient_evidence":
            return exposure  # Trả insufficient, không ép kết luận
        return {
            "signal": "automation_exposure_available",
            "confidence": "medium",
            "tasks": exposure["tasks"],
            "internal_context": {
                "active_job_count": snapshot["active_job_count"],
                "period": snapshot["period"],
                "note": "Demand hiện tại không đồng nghĩa với không có nguy cơ displacement dài hạn."
            },
            "limitations": [
                "Automation exposure dựa trên global research (OECD/McKinsey) — chưa có Vietnam-specific study.",
                "Đánh giá theo task, không phải toàn bộ job role.",
                "Displacement là dự báo dài hạn (5–10 năm), không phản ánh thị trường tuyển dụng hiện tại."
            ]
        }

    # Supply gap redirect
    if intent == "supply_gap":
        return {
            "signal": "out_of_scope",
            "confidence": None,
            "reason": (
                "Hệ thống hiện chỉ có demand-side data (JD listings). "
                "Xác nhận supply gap cần applicant volume, time-to-fill, "
                "hoặc vacancy duration — chưa có trong pipeline hiện tại."
            )
        }
```

### 7.3 Confidence Level Matrix

| Internal Data | External Evidence (scope khớp) | Confidence |
|---|---|---|
| ✅ Đủ sample | ✅ Có evidence khớp family + location | `medium` |
| ✅ Đủ sample | ❌ Không có evidence khớp scope | `low` |
| ❌ Thiếu sample | bất kỳ | `insufficient_evidence` |
| Automation lookup có citation | — | `medium` (external-based) |
| Automation lookup không có mapping | — | `insufficient_evidence` |

> Không dùng `confidence: high` khi chỉ có 1 tuần internal data.

---

## 8. Chatbot Response Templates

### Template: Current Demand Baseline

```
Dựa trên snapshot tuần {period} tại {location}:

📊 Current demand — {job_family}:
- {active_job_count} JD active từ {distinct_company_count} công ty
- Demand breadth: {demand_breadth:.2f} (tỷ lệ công ty / JD — càng cao càng phân tán)

{nếu có external evidence khớp scope}
📋 External outlook: [{source_name}, {citation}]
"{exact_claim}"

⚠️ Limitations:
- Đây là current demand baseline (1 tuần snapshot), không phải directional trend.
- Ranking giữa các ngành có membership bias — một JD nhiều category
  có thể xuất hiện trong nhiều family.
- Cần thêm ít nhất 1 tuần data để có WoW signal.

Confidence: {confidence}
```

### Template: Current Skill Requirements

```
Kỹ năng được đề cập nhiều nhất trong {job_family} tại {location} ({period}):

🔧 Phân tích từ {jd_count} JD active:

1. {skill_name}: xuất hiện trong {count} JD ({pct:.0f}%)
2. ...

💡 Ghi chú:
- Skill xuất hiện ≥ 50% JD → yêu cầu nền tảng phổ biến.
- Skill xuất hiện < 20% JD → có thể tập trung ở role chuyên biệt hoặc senior.

⚠️ Limitations:
- Dựa trên keyword matching từ requirements_text — có thể bỏ sót skill
  được diễn đạt theo cách khác.
- Đây là current requirement snapshot, không phải skill growth trend.

Confidence: medium
```

### Template: Automation Exposure

```
Về mức độ phơi nhiễm tự động hóa cho {job_category} tại {location}:

🤖 Task-level exposure [{citation}]:

Task có nguy cơ cao:
- {task_name}: {exposure_reason}

Task được bảo vệ:
- {task_name}: {exposure_reason}

📊 Market context hiện tại ({period}):
- {active_job_count} JD active từ {distinct_company_count} công ty
  → Employer vẫn đang tuyển; displacement chưa xảy ra trên thị trường VN hiện tại.

⚠️ Limitations:
- Dựa trên global research (OECD/McKinsey), chưa có Vietnam-specific validation.
- Đánh giá theo task — không đồng nghĩa toàn bộ role sẽ biến mất.
- Là dự báo dài hạn (5–10 năm), không phản ánh nhu cầu tuyển dụng ngắn hạn.
- listing_refresh_rate KHÔNG được dùng để phủ nhận hoặc xác nhận exposure.

Source: {citation}
Confidence: medium (external task mapping)
```

### Template: Supply Gap Redirect

```
Về câu hỏi "ngành nào đang thiếu nhân lực":

Hệ thống hiện tại chỉ có demand-side data từ job listings.
Để xác nhận supply gap cần thêm:
- Số lượng ứng viên / applicant volume
- Thời gian lấp đầy vị trí (time-to-fill)
- Tỷ lệ chấp nhận offer (offer acceptance rate)
- Thời gian JD còn mở (vacancy duration)

Những gì hệ thống có thể trả lời hiện tại:
→ "Ngành nào đang có active demand cao?" (current_demand)
→ "Skill nào đang được tìm kiếm nhiều?" (skill_frequency)

Bạn muốn xem thông tin theo hướng nào?
```

---

## 9. Kế Hoạch Thực Hiện 1 Tuần

### Timeline (đã thu hẹp MVP)

| Ngày | Task | Output | Priority |
|---|---|---|---|
| **T2 sáng** | Curate 2–3 nguồn, mỗi nguồn 3–5 claims vào `trend_sources` + `trend_evidence` với schema đầy đủ | Collections ready | 🔴 Critical |
| **T2 chiều** | Build `automation_exposure_lookup` cho 10–15 category có citation cụ thể | JSON / Firestore | 🔴 Critical |
| **T3** | Viết Skill Extractor: keyword frequency từ `requirements_text` | Top-10 skills per job_family/location | 🟠 High |
| **T4 sáng** | Build Signal Synthesizer: 3 intents + supply_gap redirect + fallback handler | `get_signal()` module | 🔴 Critical |
| **T4 chiều** | Viết 4 response templates, test với sample queries | Template library | 🟠 High |
| **T5** | Kết nối Synthesizer với chatbot / agent flow | End-to-end working demo | 🔴 Critical |
| **T6 sáng** | Dry-run 10 sample queries, cover edge cases (no mapping, no evidence, low sample) | Bug list + fixes | 🟠 High |
| **T6 chiều** | Verify evidence scope matching (không dùng sai scope) | QA checklist | 🟠 High |
| **T7** | Buffer: polish UX, chuẩn bị demo script | Demo-ready | 🟡 Medium |

### MVP (3 output đáng tin)

| Output | Mô tả | Confidence tối đa |
|---|---|---|
| `current_demand` | Active JD count, company count, demand breadth, relative rank | `medium` (nếu có external evidence khớp scope) |
| `skill_frequency` | Top skill keywords từ active JD text | `medium` |
| `automation_exposure` | Task-level exposure với citation rõ ràng, ~10–15 category | `medium` |

### Hoãn sau demo

- `supply_gap` — cần supply-side data
- Automation lookup đầy đủ 70 category — chỉ coverage ~10–15 có citation trong 1 tuần
- Location-specific evidence ngoài HCM + HN

---

## 10. Lưu Ý Quan Trọng Cho Demo

### Limitations là điểm mạnh

Chatbot nói rõ limitations thể hiện **độ tin cậy và tính chuyên nghiệp**. Reviewer sẽ tin hơn một hệ thống biết giới hạn của mình so với chatbot tự bịa trend từ 1 tuần data.

**Ví dụ response mẫu cho demo:**

> *"Dựa trên snapshot tuần W25 tại TP.HCM, Finance & Legal có 92 JD active từ 46 công ty — demand breadth 0.5, tương đối phân tán. Báo cáo Navigos Q2/2026 (trang 12) ghi nhận nhu cầu Kế toán - Tài chính tăng 18% so với Q1. Về automation exposure, task data entry và basic reconciliation trong accounting_audit có nguy cơ cao theo McKinsey 2023; trong khi tax strategy và audit judgment được xếp protected. Hệ thống hiện có 1 tuần internal data — đây là demand baseline, chưa phải trend. Để có WoW signal cần thêm ít nhất 1 tuần crawl nữa."*

### Không được làm

- ❌ Tự kết luận "ngành X đang tăng/giảm" từ 1 tuần snapshot
- ❌ Dùng `listing_refresh_rate` để kết luận thị trường đang sôi động hay thiếu người
- ❌ Gán automation risk score tổng cho cả category mà không có task-level citation
- ❌ Dùng evidence không cùng scope (report toàn quốc để corroborate một location cụ thể)
- ❌ Kết luận supply gap từ demand-side data
- ❌ Cộng tổng các family snapshot để suy ra tổng JD thị trường
- ❌ Dùng collection legacy `trend_job_facts` hoặc `trend_snapshots` v1
- ❌ Trả `automation_exposure` khi không có mapping hợp lệ và citation

### Được làm

- ✅ Trả current demand baseline với số tuyệt đối (JD count, company count)
- ✅ Tính demand breadth (company/JD ratio) như signal phụ
- ✅ Cross-sectional ranking giữa job_family trong cùng location + caveat membership bias
- ✅ Skill frequency từ `requirements_text` — gọi là "current requirements", không phải "skill trend"
- ✅ Automation exposure theo task, chỉ khi có citation rõ ràng
- ✅ Dùng `listing_refresh_rate` như secondary signal có caveat
- ✅ Redirect supply gap về đúng giới hạn hệ thống
- ✅ Nói rõ confidence level và limitations trong mọi response

---

## 11. Roadmap Sau Demo

| Phase | Trigger | Capability Unlock |
|---|---|---|
| **2 tuần snapshot** | Crawl tuần tiếp theo | WoW preliminary signal (`confidence: low`) |
| **4 tuần snapshot** | 1 tháng | Monthly baseline, so sánh đầu/cuối tháng |
| **8 tuần snapshot** | 2 tháng | Rolling 4-week window, MoM signal |
| **Supply-side data** | Partnership hoặc survey | True demand pressure = listings vs applicants |
| **Role taxonomy** | Sau snapshot mature | Drill down job_family → role → skill |
| **Vietnam automation study** | Research phase | Replace global index với VN-specific occupation data |

---

*Document này là solution guide cho TrendTracker v2 demo. Contract với người dùng: "internal current demand + external market outlook/exposure". Mọi signal phải đi kèm sources, scope và limitations theo Evidence Rules trong TrendTracker.md.*
