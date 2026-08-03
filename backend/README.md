# Z-MentorAI Backend

Z-MentorAI là hệ thống cố vấn nghề nghiệp dùng AI để hỗ trợ người dùng hiểu hồ sơ cá nhân, khảo sát thị trường việc làm và xây dựng lộ trình học tập phù hợp. Backend được tổ chức theo kiến trúc nhiều agent: mỗi agent phụ trách một nhóm nghiệp vụ riêng, còn Orchestrator và MCP Server đóng vai trò điều phối.

Mục tiêu chính của backend:

- Phân tích CV, hồ sơ cá nhân và tín hiệu Holland/RIASEC.
- Khảo sát mức lương, nhu cầu tuyển dụng và xu hướng nghề nghiệp.
- Gợi ý khóa học/lộ trình học dựa trên mục tiêu nghề nghiệp và kỹ năng hiện tại.
- Cung cấp API cho frontend/chatbot và điều phối các agent nghiệp vụ.

## Kiến Trúc Tổng Quan

```text
Frontend / Chat UI
        |
        v
Orchestrator
        |
        v
MCP Server
   |          |             |
   v          v             v
Profile    Market       Academic
Scanner    Scout        Architect
```

Luồng xử lý chính:

1. Người dùng gửi câu hỏi, CV hoặc yêu cầu tư vấn từ frontend.
2. `orchestrator` nhận request, quản lý auth, session, lịch sử chat và streaming response.
3. `mcp_server` expose các tool agent cho Orchestrator gọi.
4. Các domain agent xử lý nghiệp vụ riêng:
   - `profile_scanner`: đọc CV, phân tích hồ sơ, Holland/RIASEC.
   - `market_scout`: khảo sát thị trường, lương, nhu cầu tuyển dụng, xu hướng nghề nghiệp.
   - `academic_architect`: tìm khóa học và xây dựng lộ trình học.
5. Kết quả được tổng hợp và trả về frontend.

## Các Thành Phần Backend

| Service | Folder | Vai trò |
| --- | --- | --- |
| Orchestrator | `backend/orchestrator` | API gateway/chat coordinator, quản lý user/session/history và gọi MCP tools. |
| MCP Server | `backend/mcp_server` | Lớp tool server để Orchestrator gọi các agent nghiệp vụ. |
| Profile Scanner | `backend/profile_scanner` | Phân tích CV, hồ sơ cá nhân, Holland/RIASEC và profile synthesis. |
| Market Scout | `backend/market_scout` | Salary benchmark, current demand và external outlook. |
| Academic Architect | `backend/academic_architect` | Search khóa học và tạo lộ trình học tập/career roadmap. |


## Orchestrator

Folder:

```text
backend/orchestrator
```

Nhiệm vụ:

- Là service chính frontend gọi khi chat.
- Xử lý Google login/token verification.
- Quản lý user, avatar, session và chat history.
- Hỗ trợ streaming chat response.
- Kết nối tới MCP Server để dùng các tool agent.
- Có fallback local JSON database khi chưa bật Firestore.

Endpoint chính:

| Endpoint | Mục đích |
| --- | --- |
| `POST /auth/login` | Đăng nhập bằng Google token. |
| `POST /profile-scanner/cv/upload` | Upload CV qua Orchestrator. |
| `GET /sessions` | Lấy danh sách chat sessions. |
| `POST /sessions` | Tạo session mới. |
| `GET /sessions/{session_id}` | Lấy chi tiết session. |
| `DELETE /sessions/{session_id}` | Xóa session. |
| `POST /chat/stream` | Chat streaming. |
| `POST /chat` | Chat non-streaming. |
| `GET /health` | Health check. |

## MCP Server

Folder:

```text
backend/mcp_server
```

Nhiệm vụ:

- Đóng vai trò tool layer giữa Orchestrator và các domain agent.
- Chuẩn hóa request trước khi gọi từng agent.
- Ghi log agent/sub-agent, user query, duration và response preview.
- Giúp Orchestrator không cần biết chi tiết endpoint nội bộ của từng agent.

Các tool chính:

| Tool | Gọi tới service | Nhiệm vụ |
| --- | --- | --- |
| `profile_scanner` | Profile Scanner | Scan CV, bắt đầu/chấm Holland test. |
| `market_scout` | Market Scout | Hỏi thị trường việc làm, nhu cầu tuyển dụng, external outlook hoặc salary khi cần. |
| `salary_benchmark` | Market Scout | Hỏi mức lương thị trường theo job/location/experience. |
| `academic_architect` | Academic Architect | Tạo lộ trình học và gợi ý khóa học. |

## Profile Scanner Agent

Folder:

```text
backend/profile_scanner
```

Nhiệm vụ:

- Nhận và validate file CV.
- Lưu CV vào storage/Firestore hoặc fallback local tùy môi trường.
- Trích xuất text từ CV bằng OCR/Document AI/parser.
- Chuẩn hóa thông tin hồ sơ.
- Phân tích kỹ năng, kinh nghiệm, học vấn, dự án và tín hiệu seniority.
- Chạy Holland/RIASEC test và lưu kết quả.
- Tổng hợp profile snapshot để các agent khác sử dụng.

Các module quan trọng:

| Module | Vai trò |
| --- | --- |
| `cv_intake` | Validate/upload/lưu metadata CV. |
| `cv_extraction` | Parse/OCR CV và lấy text. |
| `profile_ai_extraction` | Dùng AI để extract profile facts từ CV text. |
| `profile_analysis` | Chấm điểm, benchmark và phân tích profile. |
| `profile_scan` | Flow scan profile tổng hợp. |
| `holland` | Câu hỏi, scoring và lưu kết quả Holland/RIASEC. |

Endpoint chính:

| Endpoint group | Mục đích |
| --- | --- |
| `/scan` | Scan profile từ CV đã upload. |
| `/cv/*` | CV intake/upload. |
| `/holland/*` | Start/score Holland test. |
| `/health` | Health check. |

## Market Scout Agent

Folder:

```text
backend/market_scout
```

Nhiệm vụ:

- Trả lời câu hỏi về mức lương thị trường.
- Trả lời nhu cầu tuyển dụng hiện tại theo role cụ thể.
- Trả lời kỹ năng đang được yêu cầu trên thị trường.
- Trả lời external outlook/xu hướng nghề nghiệp bằng Tavily allowlisted web search.
- Duy trì pipeline cập nhật dữ liệu CareerViet hằng tuần.

Endpoint chính:

| Endpoint | Mục đích |
| --- | --- |
| `POST /scout` | Endpoint tổng cho Orchestrator/MCP. |
| `POST /salary-benchmark` | Chạy riêng Salary Benchmark. |
| `POST /trend-tracker` | Chạy riêng Trend Tracker. |
| `GET /health` | Health check. |

### Salary Benchmark

Nhiệm vụ:

- Extract `job_title`, `location`, `experience_years` từ user query.
- Search collection `data_vector_embeddings`.
- Lọc record có lương hợp lệ.
- Loại midpoint outlier bằng IQR.
- Aggregate salary range bằng percentile:

```text
salary_range.min = P25(salary_min_vnd)
salary_range.max = P75(salary_max_vnd)
```

- Trả lời mức lương kèm 3-5 JD/source links liên quan.

### Trend Tracker

Các intent hiện tại:

| Intent | Mục đích |
| --- | --- |
| `current_demand` | Đánh giá role cụ thể có đang tuyển nhiều không. |
| `current_skill_demand` | Thống kê kỹ năng đang xuất hiện nhiều trong JD. |
| `external_outlook` | Trả lời triển vọng nghề nghiệp, xu hướng 2026/2027, tác động AI từ nguồn web allowlisted. |

Runtime data chính:

| Collection | Vai trò |
| --- | --- |
| `data_vector_embeddings` | Vector search cho salary benchmark. |
| `trend_job_facts_v2` | Job facts chuẩn hóa phục vụ trend/current demand. |
| `job_mapping_embedding` | Embedding để map role tự nhiên sang job facts. |
| `trend_evidence` | Evidence đã ingest/extract từ nguồn ngoài. |

Weekly data pipeline:

```text
CareerViet crawl
-> preprocess salary/job fields
-> embed salary records
-> normalize trend job facts
-> embed job mapping
```

Workflow GCP:

```text
backend/market_scout/workflows/weekly_market_scout_pipeline.yaml
```

## Academic Architect Agent

Folder:

```text
backend/academic_architect
```

Nhiệm vụ:

- Tìm khóa học phù hợp với mục tiêu nghề nghiệp.
- Search khóa học bằng Firestore vector search trong collection `learning_material`.
- Tạo lộ trình học tập dựa trên `career_goal` và `current_skills`.
- Phân tích skill gap và đề xuất khóa học chính/phụ.

Endpoint chính:

| Endpoint | Mục đích |
| --- | --- |
| `POST /search` | Search khóa học theo tên hoặc description embedding. |
| `POST /architect` | Tạo academic/career learning plan. |
| `GET /health` | Health check. |

Data chính:

```text
learning_material
```

Các vector field:

| Field | Mục đích |
| --- | --- |
| `name_embedding` | Search theo tên khóa học. |
| `description_embedding` | Search theo mô tả/nội dung khóa học. |

## Dữ Liệu Và Hạ Tầng

Backend có thể chạy local hoặc trên Google Cloud.

Các dịch vụ GCP đang dùng/tích hợp:

- Cloud Run: deploy các service agent.
- Cloud Run Jobs: chạy pipeline crawl/preprocess/embedding theo batch.
- Cloud Workflows: điều phối các job tuần tự.
- Cloud Scheduler: trigger workflow hằng tuần.
- Firestore: lưu user/session, CV metadata, salary embeddings, job facts, learning materials.
- Cloud Storage: lưu CV hoặc artifact.
- Vertex AI/Gemini: LLM reasoning, summary, extraction và embedding.
- Document AI: OCR/parse CV khi được cấu hình.
- Secret Manager: lưu secret như Tavily API key nếu deploy production.

## Local Development

Chạy toàn bộ backend bằng Docker Compose:

```powershell
cd backend
docker compose up --build
```

Service ports local:

| Service | Port |
| --- | --- |
| Orchestrator | `8000` |
| Profile Scanner | `8001` |
| Market Scout | `8002` |
| Academic Architect | `8003` |
| MCP Server | `8004` |

## Environment Variables Quan Trọng

| Variable | Mục đích |
| --- | --- |
| `GOOGLE_CLOUD_PROJECT` | GCP project id. |
| `USE_FIRESTORE` | Bật/tắt Firestore cho Orchestrator/Profile Scanner. |
| `USE_VERTEX_AI` | Dùng Vertex AI thay vì API key Gemini. |
| `FIRESTORE_DATABASE` | Firestore database name. |
| `MCP_SERVER_URL` | URL MCP Server cho Orchestrator. |
| `PROFILE_SCANNER_URL` | URL Profile Scanner. |
| `MARKET_SCOUT_URL` | URL Market Scout. |
| `ACADEMIC_ARCHITECT_URL` | URL Academic Architect. |
| `CV_STORAGE_BUCKET` | Bucket lưu CV. |
| `DOCUMENT_AI_PROCESSOR_ID` | Processor ID cho Document AI. |
| `TAVILY_API_KEY` | API key cho external outlook web search. |

## Tóm Tắt Vai Trò Từng Agent

| Agent | Câu hỏi giải quyết |
| --- | --- |
| Profile Scanner | “CV của tôi mạnh/yếu ở đâu?”, “Tôi phù hợp nhóm nghề nào?”, “Kết quả Holland của tôi là gì?” |
| Market Scout | “Role này lương bao nhiêu?”, “Vị trí này có đang tuyển nhiều không?”, “Ngành này còn triển vọng không?” |
| Academic Architect | “Tôi cần học gì để đạt mục tiêu nghề nghiệp?”, “Khóa học nào phù hợp với skill gap của tôi?” |
| Orchestrator | “Điều phối toàn bộ cuộc trò chuyện và chọn agent phù hợp.” |
| MCP Server | “Chuẩn hóa tool calls để Orchestrator gọi các agent.” |

## Ghi Chú Thiết Kế

- Mỗi agent nên giữ trách nhiệm độc lập, tránh trộn logic nghiệp vụ giữa các service.
- Orchestrator chỉ điều phối và tổng hợp, không nên chứa logic domain sâu.
- MCP Server chỉ làm tool adapter, không nên tính toán nghiệp vụ.
- Các pipeline dữ liệu nên chạy theo batch để dễ debug và rollback.
- Các câu trả lời liên quan thị trường cần có evidence/source khi có thể.
