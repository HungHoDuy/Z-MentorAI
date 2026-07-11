from dataclasses import dataclass

from assessments.schemas import AssessmentQuestion


COMMON_SCALE = {
    "1": "Rất không giống tôi",
    "2": "Không giống tôi",
    "3": "Trung lập / chưa chắc",
    "4": "Giống tôi",
    "5": "Rất giống tôi",
}


@dataclass(frozen=True)
class AssessmentDefinition:
    assessment_type: str
    version: str
    title: str
    eyebrow_vi: str
    description_vi: str
    result_label_vi: str
    scale: dict[str, str]
    dimension_labels: dict[str, str]
    interpretation_by_dimension: dict[str, str]
    recommendations_by_dimension: dict[str, list[str]]
    questions: list[AssessmentQuestion]


MI_DIMENSION_LABELS = {
    "linguistic": "Ngôn ngữ",
    "logical_math": "Logic / Toán học",
    "spatial": "Không gian / Hình ảnh",
    "bodily_kinesthetic": "Vận động / Thực hành",
    "musical": "Âm nhạc / Nhịp điệu",
    "interpersonal": "Giao tiếp / Thấu hiểu người khác",
    "intrapersonal": "Tự nhận thức",
    "naturalistic": "Thiên nhiên / Phân loại hệ thống",
}

MI_INTERPRETATIONS = {
    "linguistic": "Bạn có xu hướng học và thể hiện năng lực tốt qua ngôn ngữ, đọc, viết, kể chuyện và diễn đạt ý tưởng rõ ràng.",
    "logical_math": "Bạn có xu hướng mạnh ở tư duy logic, phân tích dữ liệu, cấu trúc vấn đề và tìm quy luật.",
    "spatial": "Bạn tiếp nhận thông tin tốt qua hình ảnh, sơ đồ, bố cục, bản đồ tư duy và mô hình trực quan.",
    "bodily_kinesthetic": "Bạn học tốt khi được thực hành, thao tác trực tiếp, thử nghiệm và biến ý tưởng thành sản phẩm cụ thể.",
    "musical": "Bạn nhạy với nhịp điệu, âm thanh, pattern và có thể ghi nhớ tốt qua cấu trúc lặp hoặc cảm giác tiết tấu.",
    "interpersonal": "Bạn phát triển tốt qua trao đổi, hợp tác, mentoring, phản hồi và quan sát nhu cầu của người khác.",
    "intrapersonal": "Bạn có năng lực tự quan sát, đặt mục tiêu cá nhân, phản tư và tự điều chỉnh cách học của mình.",
    "naturalistic": "Bạn có xu hướng nhận diện nhóm, hệ thống, đặc điểm khác biệt và phân loại thông tin thành cấu trúc dễ hiểu.",
}

MI_RECOMMENDATIONS = {
    "linguistic": [
        "Tóm tắt kiến thức bằng bài viết ngắn, checklist hoặc script thuyết trình.",
        "Dùng kỹ thuật teach-back: giải thích lại chủ đề cho người khác để kiểm tra độ hiểu.",
    ],
    "logical_math": [
        "Biến mục tiêu học thành bài toán đo được: input, output, metric và tiêu chí hoàn thành.",
        "Ưu tiên project có dữ liệu, benchmark, bảng so sánh hoặc logic rõ ràng.",
    ],
    "spatial": [
        "Dùng sơ đồ, mind map, wireframe hoặc flowchart khi học khái niệm mới.",
        "Tạo portfolio có hình ảnh trước/sau, dashboard hoặc kiến trúc hệ thống trực quan.",
    ],
    "bodily_kinesthetic": [
        "Học theo project nhỏ, demo nhanh và vòng lặp thử-sai ngắn.",
        "Ghi lại thao tác thực hành thành checklist để tăng độ ổn định.",
    ],
    "musical": [
        "Chia nội dung học thành nhịp lặp, flashcard hoặc routine cố định.",
        "Dùng pattern recognition để nhớ command, cấu trúc code hoặc quy trình.",
    ],
    "interpersonal": [
        "Tham gia nhóm học, review chéo hoặc pair work để tăng tốc phản hồi.",
        "Chọn project có người dùng thật hoặc stakeholder thật để luyện giao tiếp sản phẩm.",
    ],
    "intrapersonal": [
        "Dùng learning journal để theo dõi tiến độ, cảm xúc học và nguyên nhân bị kẹt.",
        "Đặt mục tiêu cá nhân theo tuần với tiêu chí hoàn thành rõ ràng.",
    ],
    "naturalistic": [
        "Phân loại kiến thức thành taxonomy: nhóm kỹ năng, nhóm lỗi, nhóm use case.",
        "Dùng bảng so sánh để nhận ra điểm giống/khác giữa công cụ, framework hoặc vai trò.",
    ],
}


MULTIPLE_INTELLIGENCES = AssessmentDefinition(
    assessment_type="multiple_intelligences",
    version="mi-v1",
    title="Multiple Intelligences",
    eyebrow_vi="Bài đánh giá trí thông minh đa dạng",
    description_vi=(
        "Chọn mức độ giống bạn từ 1 đến 5. Kết quả dùng để tham khảo kiểu năng lực "
        "và cách học phù hợp, không phải chẩn đoán tính cách."
    ),
    result_label_vi="Top nhóm năng lực",
    scale=COMMON_SCALE,
    dimension_labels=MI_DIMENSION_LABELS,
    interpretation_by_dimension=MI_INTERPRETATIONS,
    recommendations_by_dimension=MI_RECOMMENDATIONS,
    questions=[
        AssessmentQuestion(id="L1", dimension="linguistic", text_vi="Tôi dễ hiểu vấn đề hơn khi được đọc, viết hoặc diễn đạt lại bằng lời của mình."),
        AssessmentQuestion(id="L2", dimension="linguistic", text_vi="Tôi thích ghi chú, tóm tắt, viết tài liệu hoặc trình bày ý tưởng bằng câu chữ rõ ràng."),
        AssessmentQuestion(id="L3", dimension="linguistic", text_vi="Tôi thường nhớ tốt các khái niệm khi có ví dụ, câu chuyện hoặc cách giải thích mạch lạc."),
        AssessmentQuestion(id="L4", dimension="linguistic", text_vi="Tôi thấy tự tin khi phải thuyết trình, viết nội dung hoặc phản biện bằng lập luận ngôn ngữ."),
        AssessmentQuestion(id="L5", dimension="linguistic", text_vi="Tôi thích biến thông tin phức tạp thành đoạn giải thích dễ hiểu cho người khác."),
        AssessmentQuestion(id="M1", dimension="logical_math", text_vi="Tôi thích phân tích dữ liệu, con số, logic hoặc nguyên nhân phía sau một hiện tượng."),
        AssessmentQuestion(id="M2", dimension="logical_math", text_vi="Tôi thường muốn biết quy luật, công thức hoặc cấu trúc vận hành của một vấn đề."),
        AssessmentQuestion(id="M3", dimension="logical_math", text_vi="Tôi thích giải bài toán có tiêu chí đúng sai hoặc có cách kiểm chứng rõ ràng."),
        AssessmentQuestion(id="M4", dimension="logical_math", text_vi="Tôi thấy hứng thú khi so sánh phương án bằng metric, bảng điểm hoặc bằng chứng."),
        AssessmentQuestion(id="M5", dimension="logical_math", text_vi="Tôi dễ tập trung khi nhiệm vụ cần suy luận từng bước và loại bỏ giả thuyết sai."),
        AssessmentQuestion(id="S1", dimension="spatial", text_vi="Tôi hiểu nhanh hơn khi thông tin được trình bày bằng sơ đồ, hình ảnh, bản đồ hoặc bố cục trực quan."),
        AssessmentQuestion(id="S2", dimension="spatial", text_vi="Tôi thích thiết kế layout, vẽ flow, dựng wireframe hoặc tưởng tượng cấu trúc trong đầu."),
        AssessmentQuestion(id="S3", dimension="spatial", text_vi="Tôi thường ghi nhớ vị trí, màu sắc, hình dạng hoặc quan hệ không gian tốt hơn chữ thuần túy."),
        AssessmentQuestion(id="S4", dimension="spatial", text_vi="Tôi thấy dễ học khi có diagram, mockup, dashboard hoặc bản demo trực quan."),
        AssessmentQuestion(id="S5", dimension="spatial", text_vi="Tôi hay sắp xếp ý tưởng thành khối, nhánh, timeline hoặc mind map."),
        AssessmentQuestion(id="B1", dimension="bodily_kinesthetic", text_vi="Tôi học nhanh hơn khi được thực hành trực tiếp thay vì chỉ đọc lý thuyết."),
        AssessmentQuestion(id="B2", dimension="bodily_kinesthetic", text_vi="Tôi thích thử nghiệm, sửa lỗi, thao tác với công cụ hoặc tạo ra sản phẩm cụ thể."),
        AssessmentQuestion(id="B3", dimension="bodily_kinesthetic", text_vi="Tôi thường hiểu sâu hơn sau khi tự tay làm một project nhỏ."),
        AssessmentQuestion(id="B4", dimension="bodily_kinesthetic", text_vi="Tôi có xu hướng vừa làm vừa điều chỉnh thay vì chờ có kế hoạch hoàn hảo."),
        AssessmentQuestion(id="B5", dimension="bodily_kinesthetic", text_vi="Tôi thích các nhiệm vụ có hoạt động, thao tác, prototype hoặc trải nghiệm thực tế."),
        AssessmentQuestion(id="MU1", dimension="musical", text_vi="Tôi nhạy với nhịp điệu, âm thanh, giai điệu hoặc pattern lặp lại."),
        AssessmentQuestion(id="MU2", dimension="musical", text_vi="Tôi dễ nhớ thông tin hơn khi nó có cấu trúc nhịp, vần, chuỗi hoặc routine rõ."),
        AssessmentQuestion(id="MU3", dimension="musical", text_vi="Tôi thường nhận ra pattern trong âm thanh, ngôn ngữ, code hoặc hành vi lặp lại."),
        AssessmentQuestion(id="MU4", dimension="musical", text_vi="Tôi thích dùng playlist, nhịp làm việc hoặc time-block để giữ trạng thái tập trung."),
        AssessmentQuestion(id="MU5", dimension="musical", text_vi="Tôi cảm nhận tốt sự hài hòa, tiết tấu hoặc độ 'mượt' của một sản phẩm/trải nghiệm."),
        AssessmentQuestion(id="P1", dimension="interpersonal", text_vi="Tôi học tốt hơn khi được trao đổi, hỏi đáp hoặc làm việc cùng người khác."),
        AssessmentQuestion(id="P2", dimension="interpersonal", text_vi="Tôi dễ nhận ra cảm xúc, nhu cầu hoặc góc nhìn của người đối diện."),
        AssessmentQuestion(id="P3", dimension="interpersonal", text_vi="Tôi thích hỗ trợ, hướng dẫn, mentoring hoặc giúp nhóm hiểu nhau hơn."),
        AssessmentQuestion(id="P4", dimension="interpersonal", text_vi="Tôi có năng lượng khi tham gia thảo luận, workshop hoặc hoạt động nhóm."),
        AssessmentQuestion(id="P5", dimension="interpersonal", text_vi="Tôi thường quan tâm công việc của mình tạo tác động thế nào tới người dùng hoặc cộng đồng."),
        AssessmentQuestion(id="IN1", dimension="intrapersonal", text_vi="Tôi thường tự suy nghĩ về điểm mạnh, điểm yếu, mục tiêu và động lực của bản thân."),
        AssessmentQuestion(id="IN2", dimension="intrapersonal", text_vi="Tôi thích có thời gian một mình để xử lý thông tin và ra quyết định."),
        AssessmentQuestion(id="IN3", dimension="intrapersonal", text_vi="Tôi hay tự đặt mục tiêu, theo dõi tiến độ và điều chỉnh cách học của mình."),
        AssessmentQuestion(id="IN4", dimension="intrapersonal", text_vi="Tôi hiểu khá rõ môi trường nào giúp mình tập trung và môi trường nào làm mình xuống năng lượng."),
        AssessmentQuestion(id="IN5", dimension="intrapersonal", text_vi="Tôi thường học được nhiều sau khi nhìn lại trải nghiệm, sai lầm hoặc phản hồi đã nhận."),
        AssessmentQuestion(id="N1", dimension="naturalistic", text_vi="Tôi thích phân loại thông tin thành nhóm, hệ thống hoặc danh mục rõ ràng."),
        AssessmentQuestion(id="N2", dimension="naturalistic", text_vi="Tôi dễ nhận ra điểm giống, khác và mối quan hệ giữa các nhóm sự vật/khái niệm."),
        AssessmentQuestion(id="N3", dimension="naturalistic", text_vi="Tôi thích quan sát dữ kiện thực tế trước khi kết luận."),
        AssessmentQuestion(id="N4", dimension="naturalistic", text_vi="Tôi thấy thoải mái khi tổ chức kiến thức thành taxonomy, checklist hoặc thư viện tài nguyên."),
        AssessmentQuestion(id="N5", dimension="naturalistic", text_vi="Tôi quan tâm tới hệ sinh thái, bối cảnh và cách các thành phần ảnh hưởng lẫn nhau."),
    ],
)


ASSESSMENT_DEFINITIONS = {
    MULTIPLE_INTELLIGENCES.assessment_type: MULTIPLE_INTELLIGENCES,
    "mi": MULTIPLE_INTELLIGENCES,
    "multiple_intelligence": MULTIPLE_INTELLIGENCES,
}
