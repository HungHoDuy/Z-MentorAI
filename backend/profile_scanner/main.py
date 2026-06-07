import datetime
import json
import os
import uuid
from collections import defaultdict
from typing import Literal, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field


app = FastAPI(title="Profile Scanner Agent")

RIASECDimension = Literal["R", "I", "A", "S", "E", "C"]

USE_FIRESTORE = os.getenv("USE_FIRESTORE", "false").lower() == "true"
FIRESTORE_DATABASE = os.getenv("FIRESTORE_DATABASE")
HOLLAND_COLLECTION_NAME = os.getenv("HOLLAND_COLLECTION_NAME", "profile_scanner_holland_assessments")
LOCAL_RESULTS_PATH = os.getenv(
    "HOLLAND_RESULTS_PATH",
    os.path.join(os.path.dirname(__file__), "holland_results_db.json"),
)

firestore_client = None
if USE_FIRESTORE:
    from google.cloud import firestore

    if FIRESTORE_DATABASE and FIRESTORE_DATABASE != "(default)":
        firestore_client = firestore.Client(database=FIRESTORE_DATABASE)
    else:
        firestore_client = firestore.Client()


class ProfileRequest(BaseModel):
    user_id: str
    background_info: str


class ProfileResponse(BaseModel):
    status: str
    analysis: str


class HollandQuestion(BaseModel):
    id: str
    dimension: RIASECDimension
    text_vi: str


class HollandQuestionsResponse(BaseModel):
    status: str
    scale: dict
    questions: list[HollandQuestion]


class HollandStartResponse(HollandQuestionsResponse):
    latest_result: Optional[dict] = None


class HollandAnswer(BaseModel):
    question_id: str
    score: int = Field(ge=1, le=5)


class HollandScoreRequest(BaseModel):
    user_id: str
    answers: list[HollandAnswer]
    source: str = "chat"


class HollandScoreResponse(BaseModel):
    status: str
    assessment_id: str
    user_id: str
    scores: dict[str, float]
    raw_scores: dict[str, int]
    top_code: str
    interpretation_vi: str
    answered_count: int
    missing_question_ids: list[str]
    created_at: str


HOLLAND_QUESTIONS: list[HollandQuestion] = [
    HollandQuestion(id="R1", dimension="R", text_vi="Tôi thích sửa chữa, lắp ráp hoặc thao tác trực tiếp với thiết bị."),
    HollandQuestion(id="R2", dimension="R", text_vi="Tôi thích công việc có sản phẩm hữu hình, đo được bằng kết quả thực tế."),
    HollandQuestion(id="R3", dimension="R", text_vi="Tôi thấy hứng thú với công cụ, máy móc, phần cứng hoặc hệ thống vận hành."),
    HollandQuestion(id="R4", dimension="R", text_vi="Tôi thích thử nghiệm bằng tay hơn là chỉ đọc mô tả lý thuyết."),
    HollandQuestion(id="R5", dimension="R", text_vi="Tôi làm tốt khi nhiệm vụ có quy trình thao tác rõ ràng và cụ thể."),
    HollandQuestion(id="R6", dimension="R", text_vi="Tôi thích xây dựng nguyên mẫu, mô hình hoặc giải pháp kỹ thuật thực tế."),
    HollandQuestion(id="I1", dimension="I", text_vi="Tôi thích phân tích dữ liệu, bằng chứng và tìm nguyên nhân gốc rễ."),
    HollandQuestion(id="I2", dimension="I", text_vi="Tôi thích nghiên cứu một vấn đề phức tạp cho đến khi hiểu bản chất."),
    HollandQuestion(id="I3", dimension="I", text_vi="Tôi hứng thú với toán, khoa học, công nghệ hoặc tư duy logic."),
    HollandQuestion(id="I4", dimension="I", text_vi="Tôi thích đọc tài liệu chuyên môn để tự tìm lời giải."),
    HollandQuestion(id="I5", dimension="I", text_vi="Tôi thường đặt câu hỏi vì sao và kiểm chứng giả thuyết trước khi kết luận."),
    HollandQuestion(id="I6", dimension="I", text_vi="Tôi thích phát hiện pattern, insight hoặc quy luật ẩn trong thông tin."),
    HollandQuestion(id="A1", dimension="A", text_vi="Tôi thích thiết kế, viết, kể chuyện hoặc tạo ra sản phẩm mang dấu ấn cá nhân."),
    HollandQuestion(id="A2", dimension="A", text_vi="Tôi thích các công việc cho phép tự do thử nhiều cách thể hiện khác nhau."),
    HollandQuestion(id="A3", dimension="A", text_vi="Tôi có xu hướng chú ý đến màu sắc, bố cục, ngôn từ hoặc trải nghiệm người dùng."),
    HollandQuestion(id="A4", dimension="A", text_vi="Tôi thích biến ý tưởng mơ hồ thành nội dung, hình ảnh hoặc concept rõ ràng."),
    HollandQuestion(id="A5", dimension="A", text_vi="Tôi thấy năng lượng khi phải nghĩ ra hướng tiếp cận mới, không quá rập khuôn."),
    HollandQuestion(id="A6", dimension="A", text_vi="Tôi thích trình bày ý tưởng theo cách cuốn hút và có cá tính."),
    HollandQuestion(id="S1", dimension="S", text_vi="Tôi thích lắng nghe, hỗ trợ và giúp người khác giải quyết vấn đề."),
    HollandQuestion(id="S2", dimension="S", text_vi="Tôi thấy phù hợp với vai trò hướng dẫn, mentoring hoặc giảng giải cho người khác."),
    HollandQuestion(id="S3", dimension="S", text_vi="Tôi thích làm việc trong môi trường có nhiều tương tác con người."),
    HollandQuestion(id="S4", dimension="S", text_vi="Tôi quan tâm đến tác động của công việc lên người dùng, học viên hoặc cộng đồng."),
    HollandQuestion(id="S5", dimension="S", text_vi="Tôi thường là người kết nối, điều phối hoặc giúp nhóm hiểu nhau hơn."),
    HollandQuestion(id="S6", dimension="S", text_vi="Tôi kiên nhẫn khi phải giải thích lại để người khác tiến bộ."),
    HollandQuestion(id="E1", dimension="E", text_vi="Tôi thích thuyết phục, trình bày hoặc bảo vệ một ý tưởng trước người khác."),
    HollandQuestion(id="E2", dimension="E", text_vi="Tôi hứng thú với kinh doanh, tăng trưởng, sản phẩm hoặc chiến lược thị trường."),
    HollandQuestion(id="E3", dimension="E", text_vi="Tôi sẵn sàng ra quyết định khi có thông tin chưa hoàn hảo."),
    HollandQuestion(id="E4", dimension="E", text_vi="Tôi thích dẫn dắt nhóm hoặc chịu trách nhiệm cho kết quả chung."),
    HollandQuestion(id="E5", dimension="E", text_vi="Tôi thấy hào hứng khi phải đàm phán, pitching hoặc tạo ảnh hưởng."),
    HollandQuestion(id="E6", dimension="E", text_vi="Tôi thích đặt mục tiêu tham vọng và tìm cách biến nó thành kết quả."),
    HollandQuestion(id="C1", dimension="C", text_vi="Tôi thích sắp xếp dữ liệu, tài liệu, kế hoạch hoặc quy trình cho gọn gàng."),
    HollandQuestion(id="C2", dimension="C", text_vi="Tôi làm tốt với checklist, tiêu chuẩn chất lượng và deadline rõ ràng."),
    HollandQuestion(id="C3", dimension="C", text_vi="Tôi thích kiểm tra chi tiết để giảm sai sót trước khi bàn giao."),
    HollandQuestion(id="C4", dimension="C", text_vi="Tôi thấy thoải mái với báo cáo, bảng tính, tracking hoặc quản lý hồ sơ."),
    HollandQuestion(id="C5", dimension="C", text_vi="Tôi thích hệ thống có cấu trúc, vai trò rõ và quy tắc ổn định."),
    HollandQuestion(id="C6", dimension="C", text_vi="Tôi kiên trì với các nhiệm vụ cần độ chính xác và tính nhất quán cao."),
]

QUESTION_BY_ID = {question.id: question for question in HOLLAND_QUESTIONS}
DIMENSION_LABELS = {
    "R": "Realistic - thực tế, thao tác, kỹ thuật",
    "I": "Investigative - phân tích, nghiên cứu, logic",
    "A": "Artistic - sáng tạo, thiết kế, biểu đạt",
    "S": "Social - hỗ trợ, giảng giải, con người",
    "E": "Enterprising - dẫn dắt, thuyết phục, kinh doanh",
    "C": "Conventional - tổ chức, quy trình, chi tiết",
}
INTERPRETATION_BY_TOP = {
    "R": "Bạn có thiên hướng giải quyết vấn đề bằng thao tác thực tế, công cụ và kết quả hữu hình.",
    "I": "Bạn có thiên hướng phân tích, nghiên cứu, xử lý thông tin và tìm bản chất vấn đề.",
    "A": "Bạn có thiên hướng sáng tạo, biểu đạt ý tưởng và tạo trải nghiệm/nội dung có cá tính.",
    "S": "Bạn có thiên hướng làm việc với con người, hỗ trợ, hướng dẫn và tạo tác động xã hội.",
    "E": "Bạn có thiên hướng dẫn dắt, thuyết phục, ra quyết định và tạo ảnh hưởng lên kết quả.",
    "C": "Bạn có thiên hướng tổ chức, quản lý quy trình, chuẩn hóa dữ liệu và đảm bảo độ chính xác.",
}


def utc_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def read_local_results() -> dict:
    if not os.path.exists(LOCAL_RESULTS_PATH):
        return {"assessments": {}}
    try:
        with open(LOCAL_RESULTS_PATH, "r", encoding="utf-8") as file:
            return json.load(file)
    except Exception:
        return {"assessments": {}}


def write_local_results(data: dict) -> None:
    with open(LOCAL_RESULTS_PATH, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


async def save_holland_assessment(result: dict) -> None:
    if USE_FIRESTORE:
        firestore_client.collection(HOLLAND_COLLECTION_NAME).document(result["assessment_id"]).set(result)
        return

    data = read_local_results()
    data["assessments"][result["assessment_id"]] = result
    write_local_results(data)


async def get_latest_holland_assessment(user_id: str) -> Optional[dict]:
    if USE_FIRESTORE:
        docs = (
            firestore_client.collection(HOLLAND_COLLECTION_NAME)
            .where("user_id", "==", user_id)
            .order_by("created_at", direction="DESCENDING")
            .limit(1)
            .stream()
        )
        for doc in docs:
            return doc.to_dict()
        return None

    data = read_local_results()
    assessments = [
        item for item in data.get("assessments", {}).values()
        if item.get("user_id") == user_id
    ]
    assessments.sort(key=lambda item: item.get("created_at", ""), reverse=True)
    return assessments[0] if assessments else None


def score_holland_answers(request: HollandScoreRequest) -> HollandScoreResponse:
    answered_by_id = {answer.question_id: answer for answer in request.answers}
    unknown_ids = sorted(set(answered_by_id) - set(QUESTION_BY_ID))
    if unknown_ids:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown Holland question ids: {', '.join(unknown_ids)}",
        )

    raw_scores = {dimension: 0 for dimension in DIMENSION_LABELS}
    counts = defaultdict(int)
    for answer in request.answers:
        question = QUESTION_BY_ID[answer.question_id]
        raw_scores[question.dimension] += answer.score
        counts[question.dimension] += 1

    scores = {}
    for dimension in DIMENSION_LABELS:
        max_score = max(counts[dimension] * 5, 1)
        scores[dimension] = round(raw_scores[dimension] / max_score, 2)

    sorted_dimensions = sorted(
        DIMENSION_LABELS.keys(),
        key=lambda dimension: (scores[dimension], raw_scores[dimension]),
        reverse=True,
    )
    top_code = "-".join(sorted_dimensions[:3])
    top_dimension = sorted_dimensions[0]
    missing_question_ids = [
        question.id for question in HOLLAND_QUESTIONS
        if question.id not in answered_by_id
    ]
    created_at = utc_now()

    return HollandScoreResponse(
        status="success",
        assessment_id=str(uuid.uuid4()),
        user_id=request.user_id,
        scores=scores,
        raw_scores=raw_scores,
        top_code=top_code,
        interpretation_vi=INTERPRETATION_BY_TOP[top_dimension],
        answered_count=len(request.answers),
        missing_question_ids=missing_question_ids,
        created_at=created_at,
    )


@app.post("/scan", response_model=ProfileResponse)
async def scan_profile(request: ProfileRequest):
    analysis_result = (
        f"Mocked profile analysis for user {request.user_id} with background: "
        f"{request.background_info}. Found key strengths in technical skills. "
        "If the user needs career-interest alignment, run the Holland/RIASEC assessment."
    )

    return ProfileResponse(
        status="success",
        analysis=analysis_result,
    )


@app.get("/holland/questions", response_model=HollandQuestionsResponse)
async def get_holland_questions():
    return HollandQuestionsResponse(
        status="success",
        scale={
            "1": "Rất không giống tôi",
            "2": "Không giống tôi",
            "3": "Trung lập / chưa chắc",
            "4": "Giống tôi",
            "5": "Rất giống tôi",
        },
        questions=HOLLAND_QUESTIONS,
    )


@app.get("/holland/start/{user_id}", response_model=HollandStartResponse)
async def start_holland_test(user_id: str):
    latest_result = await get_latest_holland_assessment(user_id)
    return HollandStartResponse(
        status="success",
        latest_result=latest_result,
        scale={
            "1": "Rất không giống tôi",
            "2": "Không giống tôi",
            "3": "Trung lập / chưa chắc",
            "4": "Giống tôi",
            "5": "Rất giống tôi",
        },
        questions=HOLLAND_QUESTIONS,
    )


@app.post("/holland/score", response_model=HollandScoreResponse)
async def score_holland_test(request: HollandScoreRequest):
    result = score_holland_answers(request)
    result_payload = result.model_dump() if hasattr(result, "model_dump") else result.dict()
    await save_holland_assessment(result_payload)
    return result


@app.get("/holland/latest/{user_id}")
async def get_latest_holland_result(user_id: str):
    result = await get_latest_holland_assessment(user_id)
    if not result:
        raise HTTPException(status_code=404, detail="No Holland assessment found for this user.")
    return result


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "profile_scanner"}
