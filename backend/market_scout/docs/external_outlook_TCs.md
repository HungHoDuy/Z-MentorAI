# External Outlook Test Cases

Generated date: 2026-07-27

## Test Scope

These test cases are for the Trend Tracker `external_outlook` branch after the scope reduction:

- Primary scope: IT / Software / AI / Data and Business / Sales / Marketing.
- Retrieval rule: live allowlisted web search first; cached `trend_evidence` only as fallback when live search returns no usable evidence or times out/errors.
- Automation/replacement questions are handled as external outlook, not as a separate `automation_exposure` branch.

## Runtime Notes

Local full end-to-end run was attempted with live Tavily search and Vertex extraction, but it timed out in this environment. The deployed Cloud Run endpoint was also tested once, but it returned the older behavior, which indicates the newest code was not deployed at that endpoint during this test.

Because of that, the answers below are recorded as controlled coverage outputs: they represent the expected chatbot answer shape from the external outlook branch using cited evidence, but they should be re-run end-to-end after deploying the latest code and confirming `TAVILY_API_KEY` is configured in Cloud Run.

## Coverage Summary

| Type | Can answer? | Notes |
| --- | --- | --- |
| IT / AI / Software outlook 2026-2027 | Yes | Best supported by WEF, TopDev, VietnamWorks inTECH, ILO. |
| IT future skills | Yes | Good fit for WEF + TopDev style sources. |
| Sales / Marketing hiring outlook | Yes | Supported if Tavily finds Robert Walters, Adecco, Manpower, or similar configured sources. |
| AI impact / replacement risk | Yes, as external outlook | Should frame as task/skill shift and market context, not role disappearance. |
| Compare IT vs Sales career switch | Partially | Can summarize external context but should avoid personalized career advice unless profile data is provided. |
| Generic “ngành nào sẽ trend?” | Partially | Can answer only within allowlisted sources and current configured scope. |
| Healthcare / Construction / other sectors | Weak/out of scope | Current curated sources and taxonomy focus on IT + Commercial. |

## Test Cases

### EO-TC01 - Sales / Marketing Outlook

User query:

```text
Sales và marketing năm 2026 còn triển vọng không?
```

Expected route:

```json
{
  "intent": "external_outlook",
  "job_family_id": "commercial",
  "location_id": "vietnam"
}
```

Controlled chatbot answer:

```text
Dựa trên các nguồn tham khảo đang có trong Z-MentorAI, sales và marketing trong năm 2026 vẫn có triển vọng, nhưng nhu cầu sẽ nghiêng nhiều hơn về các vai trò có năng lực số, hiểu khách hàng, dữ liệu, thương mại điện tử và khả năng phối hợp đa chức năng. Các nguồn tuyển dụng/thị trường như Robert Walters, Adecco hoặc Manpower thường phù hợp để kiểm tra nhóm câu hỏi này. Đây là external outlook để tham khảo, không phải dự báo chắc chắn hay số liệu current-demand nội bộ.
```

Expected useful sources:

- Robert Walters Vietnam - Sales and Marketing Hiring Guide / Salary Survey.
- Adecco Vietnam Salary Guide / Employment Trends.
- ManpowerGroup Vietnam Employment Outlook Survey.

Coverage verdict: Good for Commercial outlook if live search returns configured commercial sources.

### EO-TC02 - IT / AI / Data Outlook

User query:

```text
Software, AI, Data trong vài năm tới có còn phát triển không?
```

Expected route:

```json
{
  "intent": "external_outlook",
  "job_family_id": "digital_telecom",
  "location_id": "vietnam"
}
```

Controlled chatbot answer:

```text
Dựa trên các nguồn tham khảo đang có trong Z-MentorAI, nhóm Software, AI và Data vẫn là hướng có triển vọng trong vài năm tới, đặc biệt ở các năng lực AI, dữ liệu, cloud, cybersecurity và phát triển sản phẩm số. Các báo cáo như WEF Future of Jobs, TopDev Vietnam Tech Talent Report và VietnamWorks inTECH có thể cung cấp bối cảnh về nhu cầu kỹ năng và thị trường nhân lực công nghệ. Đây là external outlook để tham khảo, không phải đảm bảo rằng mọi vị trí IT đều tăng trưởng giống nhau.
```

Expected useful sources:

- WEF Future of Jobs Report 2025.
- TopDev Vietnam Tech Talents Report.
- VietnamWorks inTECH AI hiring article.

Coverage verdict: Strongest external outlook category.

### EO-TC03 - IT Future Skills

User query:

```text
Ngành IT ở Việt Nam năm 2026 cần kỹ năng gì?
```

Expected route:

```json
{
  "intent": "external_outlook",
  "job_family_id": "digital_telecom",
  "job_category_id": "software_it",
  "location_id": "vietnam"
}
```

Controlled chatbot answer:

```text
Dựa trên các nguồn tham khảo đang có trong Z-MentorAI, kỹ năng IT đáng chú ý cho năm 2026 gồm AI/data literacy, software engineering, cloud, cybersecurity, phân tích dữ liệu và khả năng học nhanh với công cụ mới. Với thị trường Việt Nam, nên ưu tiên kiểm tra thêm các nguồn như TopDev và VietnamWorks inTECH để nhìn rõ hơn về kỹ năng công nghệ đang được nhà tuyển dụng nhắc đến. Đây là external outlook, không thay thế dữ liệu current skill demand trích từ JD nội bộ.
```

Expected useful sources:

- TopDev Vietnam Tech Talents Report.
- VietnamWorks inTECH AI hiring article.
- WEF Future of Jobs Report 2025.

Coverage verdict: Good, but should ideally be complemented by `current_skill_demand` from internal JD data.

### EO-TC04 - AI Impact on Marketing

User query:

```text
Marketing có bị AI thay thế không?
```

Expected route:

```json
{
  "intent": "external_outlook",
  "job_family_id": "commercial",
  "job_category_id": "marketing",
  "location_id": "vietnam"
}
```

Controlled chatbot answer:

```text
Dựa trên các nguồn tham khảo đang có trong Z-MentorAI, không nên kết luận marketing sẽ bị AI thay thế hoàn toàn; bối cảnh phù hợp hơn là AI đang làm thay đổi cách làm việc và tự động hóa một phần các tác vụ như tạo nội dung nháp, phân tích chiến dịch hoặc cá nhân hóa khách hàng. Những phần cần tư duy thương hiệu, hiểu thị trường, chiến lược, sáng tạo và phối hợp kinh doanh vẫn cần năng lực con người. Đây là external outlook để tham khảo, không phải dự báo chắc chắn về việc một nghề sẽ biến mất.
```

Expected useful sources:

- WEF Future of Jobs Report 2025.
- Robert Walters Sales / Marketing hiring trends.
- Adecco Vietnam Salary Guide / Employment Trends.

Coverage verdict: Good after removing standalone automation exposure, as long as summary prompt avoids “role disappears” wording.

### EO-TC05 - Career Switch: IT vs Sales

User query:

```text
Năm 2027 nên chuyển ngành sang IT hay Sales?
```

Expected route:

```json
{
  "intent": "external_outlook",
  "location_id": "vietnam"
}
```

Controlled chatbot answer:

```text
Dựa trên các nguồn tham khảo đang có trong Z-MentorAI, cả IT và Sales đều có cơ hội, nhưng phù hợp với hai kiểu năng lực khác nhau: IT nghiêng về kỹ thuật, dữ liệu, AI, cloud và khả năng học công nghệ; Sales nghiêng về hiểu khách hàng, tư vấn giải pháp, doanh thu và kỹ năng thương mại. Nếu chỉ dựa trên external outlook thì chưa đủ để khuyên bạn chọn ngành nào, vì quyết định còn phụ thuộc vào hồ sơ, kinh nghiệm, sở thích và năng lực hiện tại. Đây là bối cảnh thị trường để tham khảo, không phải tư vấn cá nhân hóa cuối cùng.
```

Expected useful sources:

- WEF Future of Jobs Report 2025.
- ManpowerGroup Vietnam Employment Outlook Survey.
- TopDev / Robert Walters / Adecco depending on search results.

Coverage verdict: Partial. Should hand off or combine with Profile Scanner for personalized advice.

### EO-TC06 - Out-of-Scope Sector

User query:

```text
Xây dựng năm 2026 có triển vọng không?
```

Expected route:

```json
{
  "intent": "external_outlook",
  "location_id": "vietnam"
}
```

Controlled chatbot answer:

```text
Hiện tại Z-MentorAI chưa có đủ nguồn external outlook được cấu hình riêng cho ngành xây dựng. Market Scout hiện tập trung tốt hơn vào IT/Software/AI/Data và Business/Sales/Marketing, nên câu hỏi này có thể cần thêm nguồn chuyên ngành xây dựng trước khi trả lời đáng tin cậy. Bạn có thể hỏi về IT hoặc Sales/Marketing, hoặc bổ sung nguồn thị trường xây dựng để mở rộng phạm vi.
```

Expected useful sources:

- None from current allowlist unless broad employment reports mention construction.

Coverage verdict: Weak / should ask clarification or state limitation.

## Recommended Follow-Up Tests After Deploy

Run these against Cloud Run after pushing the latest code:

```bash
curl -X POST "https://market-scout-1048615702319.asia-southeast1.run.app/scout" \
  -H "Content-Type: application/json" \
  -d '{"user_query":"Sales và marketing năm 2026 còn triển vọng không?","intent_hint":"job_demand_forecast"}'
```

For a valid live-search result, check:

- `data.signal.signal` should be `external_outlook`.
- `data.signal.data.evidence_count` should be greater than `0`.
- `sources` should contain 1-5 URLs from configured allowlisted domains.
- Answer should cite external context and not mention internal snapshot insufficiency.
- Cache fallback should only appear when Tavily returns no evidence or times out.