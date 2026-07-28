from holland.schemas import HollandQuestion


HOLLAND_ASSESSMENT_VERSION = "holland-v2"


HOLLAND_SCALE = {
    "1": "Rất không giống tôi",
    "2": "Không giống tôi",
    "3": "Trung lập / chưa chắc",
    "4": "Giống tôi",
    "5": "Rất giống tôi",
}

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
