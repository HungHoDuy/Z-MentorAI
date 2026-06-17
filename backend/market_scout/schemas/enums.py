from enum import Enum


class MarketScoutIntent(str, Enum):
    SALARY_BENCHMARK = "salary_benchmark"
    TREND_TRACKER = "trend_tracker"
    JOB_DEMAND_FORECAST = "job_demand_forecast"
    INDUSTRY_DECLINE_RISK = "industry_decline_risk"
    MIXED = "mixed"
    CLARIFICATION_NEEDED = "clarification_needed"


class ConfidenceLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class DataSourceType(str, Enum):
    INTERNAL_DB = "internal_db"
    VECTOR_DB = "vector_db"
    WEB_SEARCH = "web_search"
    USER_CONTEXT = "user_context"


class SourceType(str, Enum):
    SALARY_REPORT = "salary_report"
    MARKET_REPORT = "market_report"
    JOB_POSTING = "job_posting"
    ARTICLE = "article"
    GOVERNMENT_DATA = "government_data"
    INTERNAL_RECORD = "internal_record"
    OTHER = "other"


class SeniorityLevel(str, Enum):
    INTERN = "intern"
    FRESHER = "fresher"
    JUNIOR = "junior"
    MIDDLE = "middle"
    SENIOR = "senior"
    LEAD = "lead"
    MANAGER = "manager"
    UNKNOWN = "unknown"


class SalaryPeriod(str, Enum):
    MONTHLY = "monthly"
    YEARLY = "yearly"
    HOURLY = "hourly"
