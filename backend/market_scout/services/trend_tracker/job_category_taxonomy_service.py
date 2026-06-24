from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping
from typing import Any

from backend.market_scout.schemas.trend_tracker.job_category_taxonomy import (
    JobCategoryDefinition,
    JobCategoryTaxonomyMatch,
)


TAXONOMY_VERSION = "job-category-taxonomy-v1"
JOB_CATEGORY_FIELD_NAMES = (
    "job_category",
    "job_categories",
    "industry",
    "industries",
    "Ngành nghề",
)

# The 72 observed raw values include two invalid location labels, which are kept
# in DEFAULT_INVALID_JOB_CATEGORY_LABELS instead of becoming job categories.
DEFAULT_JOB_CATEGORIES = (
    JobCategoryDefinition("electrical_electronics", "Điện / Điện tử / Điện lạnh / Điện công nghiệp", "industrial_technical"),
    JobCategoryDefinition("chemistry", "Hóa học", "science_laboratory"),
    JobCategoryDefinition("other", "Ngành khác", "other", trend_eligible=False),
    JobCategoryDefinition("executive_management", "Quản lý điều hành", "business_support", cross_cutting=True),
    JobCategoryDefinition("accounting_audit", "Kế toán / Kiểm toán", "finance_legal"),
    JobCategoryDefinition("construction", "Xây dựng", "industrial_technical"),
    JobCategoryDefinition("real_estate", "Bất động sản", "property_consumer"),
    JobCategoryDefinition("manufacturing_operations", "Sản xuất / Vận hành sản xuất", "operations"),
    JobCategoryDefinition("retail_wholesale", "Bán lẻ / Bán sỉ", "commercial"),
    JobCategoryDefinition("sales_business", "Bán hàng / Kinh doanh", "commercial"),
    JobCategoryDefinition("consumer_goods_personal_care", "Hàng gia dụng / Chăm sóc cá nhân", "property_consumer"),
    JobCategoryDefinition("textile_fashion", "Dệt may / Da giày / Thời trang", "property_consumer"),
    JobCategoryDefinition("procurement_materials", "Thu mua / Vật tư", "supply_chain"),
    JobCategoryDefinition("marketing", "Tiếp thị / Marketing", "commercial"),
    JobCategoryDefinition("architecture", "Kiến trúc", "industrial_technical"),
    JobCategoryDefinition("software_it", "CNTT - Phần mềm", "digital_telecom"),
    JobCategoryDefinition("hardware_network_it", "CNTT - Phần cứng / Mạng", "digital_telecom"),
    JobCategoryDefinition("postal_telecommunications", "Bưu chính viễn thông", "digital_telecom"),
    JobCategoryDefinition("import_export", "Xuất nhập khẩu", "supply_chain"),
    JobCategoryDefinition("consulting", "Tư vấn", "business_support"),
    JobCategoryDefinition("customer_service", "Dịch vụ khách hàng", "commercial"),
    JobCategoryDefinition("interior_exterior", "Nội ngoại thất", "property_consumer"),
    JobCategoryDefinition("finance_investment", "Tài chính / Đầu tư", "finance_legal"),
    JobCategoryDefinition("graduate_internship", "Mới tốt nghiệp / Thực tập", "career_stage", trend_eligible=False, cross_cutting=True),
    JobCategoryDefinition("food_beverage", "Thực phẩm & Đồ uống", "people_services"),
    JobCategoryDefinition("hospitality", "Nhà hàng / Khách sạn", "people_services"),
    JobCategoryDefinition("education_training", "Giáo dục / Đào tạo", "people_services"),
    JobCategoryDefinition("healthcare_beauty", "Y tế / Chăm sóc sức khỏe / Thẩm mỹ / Làm đẹp", "people_services"),
    JobCategoryDefinition("pharmaceuticals_cosmetics", "Dược phẩm/ Hóa Mỹ Phẩm", "science_laboratory"),
    JobCategoryDefinition("administration_secretarial", "Hành chính / Thư ký", "business_support"),
    JobCategoryDefinition("mechanical_automotive_automation", "Cơ khí / Ô tô / Tự động hóa", "industrial_technical"),
    JobCategoryDefinition("translation_interpretation", "Biên phiên dịch", "creative_media"),
    JobCategoryDefinition("human_resources", "Nhân sự", "business_support"),
    JobCategoryDefinition("maintenance_repair", "Bảo trì / Sửa chữa", "industrial_technical"),
    JobCategoryDefinition("banking", "Ngân hàng", "finance_legal"),
    JobCategoryDefinition("logistics", "Vận chuyển / Giao nhận / Kho vận", "supply_chain"),
    JobCategoryDefinition("surveying_geology", "Trắc địa / Địa Chất", "industrial_technical"),
    JobCategoryDefinition("quality_assurance", "Quản lý chất lượng (QA/QC)", "operations"),
    JobCategoryDefinition("security", "An Ninh / Bảo Vệ", "operations"),
    JobCategoryDefinition("legal", "Luật / Pháp lý", "finance_legal"),
    JobCategoryDefinition("art_design", "Mỹ thuật / Nghệ thuật / Thiết kế", "creative_media"),
    JobCategoryDefinition("tourism", "Du lịch", "people_services"),
    JobCategoryDefinition("veterinary", "Chăn nuôi / Thú y", "agriculture_environment"),
    JobCategoryDefinition("wood_products", "Đồ gỗ", "industrial_technical"),
    JobCategoryDefinition("mining", "Khoáng sản", "industrial_technical"),
    JobCategoryDefinition("agriculture", "Nông nghiệp", "agriculture_environment"),
    JobCategoryDefinition("oil_gas", "Dầu khí", "industrial_technical"),
    JobCategoryDefinition("ecommerce", "Thương mại điện tử", "commercial"),
    JobCategoryDefinition("technical_sales", "Bán Hàng Kỹ Thuật", "commercial"),
    JobCategoryDefinition("maritime", "Hàng hải", "supply_chain"),
    JobCategoryDefinition("insurance", "Bảo hiểm", "finance_legal"),
    JobCategoryDefinition("statistics", "Thống kê", "business_support"),
    JobCategoryDefinition("securities", "Chứng khoán", "finance_legal"),
    JobCategoryDefinition("occupational_safety", "An toàn lao động", "industrial_technical"),
    JobCategoryDefinition("environment", "Môi trường", "agriculture_environment"),
    JobCategoryDefinition("food_technology_nutrition", "Công nghệ thực phẩm / Dinh dưỡng", "science_laboratory"),
    JobCategoryDefinition("biotechnology", "Công nghệ sinh học", "science_laboratory"),
    JobCategoryDefinition("journalism_editing", "Truyền hình / Báo chí / Biên tập", "creative_media"),
    JobCategoryDefinition("advertising_public_relations", "Quảng cáo / Đối ngoại / Truyền Thông", "creative_media"),
    JobCategoryDefinition("event_management", "Tổ chức sự kiện", "creative_media"),
    JobCategoryDefinition("printing_publishing", "In ấn / Xuất bản", "creative_media"),
    JobCategoryDefinition("forestry", "Lâm Nghiệp", "agriculture_environment"),
    JobCategoryDefinition("general_labor", "Lao động phổ thông", "career_stage", trend_eligible=False, cross_cutting=True),
    JobCategoryDefinition("digital_marketing", "Tiếp thị trực tuyến", "commercial"),
    JobCategoryDefinition("entertainment", "Giải trí", "creative_media"),
    JobCategoryDefinition("irrigation", "Thủy lợi", "industrial_technical"),
    JobCategoryDefinition("aquaculture", "Thủy sản / Hải sản", "agriculture_environment"),
    JobCategoryDefinition("aviation", "Hàng không", "supply_chain"),
    JobCategoryDefinition("library", "Thư viện", "people_services"),
    JobCategoryDefinition("nonprofit", "Phi chính phủ / Phi lợi nhuận", "people_services"),
)

DEFAULT_INVALID_JOB_CATEGORY_LABELS = ("Tỉnh", "Thành Phố")


class JobCategoryTaxonomyService:
    """Classify raw CareerViet job categories without creating fallback categories."""

    def __init__(
        self,
        *,
        definitions: tuple[JobCategoryDefinition, ...] = DEFAULT_JOB_CATEGORIES,
        invalid_labels: tuple[str, ...] = DEFAULT_INVALID_JOB_CATEGORY_LABELS,
        taxonomy_version: str = TAXONOMY_VERSION,
    ) -> None:
        self.taxonomy_version = taxonomy_version
        self.definitions_by_id = {definition.job_category_id: definition for definition in definitions}
        self.label_to_definition = {
            normalize_job_category_label(definition.label): definition
            for definition in definitions
        }
        self.invalid_label_keys = {
            normalize_job_category_label(label)
            for label in invalid_labels
            if normalize_job_category_label(label)
        }

    def classify(self, raw_labels: list[str]) -> JobCategoryTaxonomyMatch:
        job_category_ids: list[str] = []
        job_family_ids: list[str] = []
        unmatched_labels: list[str] = []
        invalid_labels: list[str] = []

        for raw_label in raw_labels:
            normalized = normalize_job_category_label(raw_label)
            if normalized in self.invalid_label_keys:
                invalid_labels.append(raw_label)
                continue

            definition = self.label_to_definition.get(normalized)
            if definition is None:
                unmatched_labels.append(raw_label)
                continue
            if definition.job_category_id not in job_category_ids:
                job_category_ids.append(definition.job_category_id)
            if definition.job_family_id not in job_family_ids:
                job_family_ids.append(definition.job_family_id)

        return JobCategoryTaxonomyMatch(
            raw_labels=list(raw_labels),
            job_category_ids=job_category_ids,
            job_family_ids=job_family_ids,
            unmatched_labels=unmatched_labels,
            invalid_labels=invalid_labels,
            taxonomy_version=self.taxonomy_version,
        )

    def extract_raw_labels(self, data: Mapping[str, Any]) -> list[str]:
        return split_job_category_labels(_first_field_value(data, JOB_CATEGORY_FIELD_NAMES))

    def definition_for_label(self, raw_label: str) -> JobCategoryDefinition | None:
        return self.label_to_definition.get(normalize_job_category_label(raw_label))


def split_job_category_labels(value: Any) -> list[str]:
    if value is None:
        return []

    values = value if isinstance(value, (list, tuple, set)) else [value]
    labels: list[str] = []
    seen: set[str] = set()
    for raw_value in values:
        for label in re.split(r"[,;]", str(raw_value)):
            cleaned = " ".join(label.split())
            normalized = normalize_job_category_label(cleaned)
            if not cleaned or not normalized or normalized in seen:
                continue
            seen.add(normalized)
            labels.append(cleaned)
    return labels


def normalize_job_category_label(value: str | None) -> str:
    if not value:
        return ""
    text = str(value).replace("đ", "d").replace("Đ", "D")
    text = unicodedata.normalize("NFD", text)
    text = "".join(character for character in text if unicodedata.category(character) != "Mn")
    text = text.casefold()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _first_field_value(data: Mapping[str, Any], field_names: tuple[str, ...]) -> Any:
    for field_name in field_names:
        value = data.get(field_name)
        if value not in (None, ""):
            return value

    normalized_fields = {normalize_job_category_label(name) for name in field_names}
    for field_name, value in data.items():
        if (
            normalize_job_category_label(str(field_name)) in normalized_fields
            and value not in (None, "")
        ):
            return value
    return None
