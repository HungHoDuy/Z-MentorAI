from __future__ import annotations

from datetime import date

from backend.market_scout.schemas.trend_tracker.automation_risk import AutomationRiskLookup


_SOURCE_TITLE = "World Economic Forum: The Future of Jobs Report 2025"
_SOURCE_URL = "https://www.weforum.org/publications/the-future-of-jobs-report-2025/"
_PUBLISHED_AT = date(2025, 1, 7)
_CAVEAT = (
    "This is a curated global task-exposure baseline, not Vietnam-specific measured risk. "
    "Validate it against local tasks and employers before making a high-stakes decision."
)


def default_automation_risk_lookups() -> tuple[AutomationRiskLookup, ...]:
    """Return the reviewed MVP lookup set for common job categories."""

    return (
        _lookup(
            "accounting_audit",
            "medium",
            "Rules-based reconciliation, document checks, and standard reporting can be assisted by automation.",
            ["Audit judgment", "Interpreting accounting standards", "Stakeholder advice"],
            ["Data entry", "Invoice matching", "Standard reconciliations"],
        ),
        _lookup(
            "banking",
            "medium",
            "Routine servicing and document processing are more exposed than advisory and risk decisions.",
            ["Credit judgment", "Relationship management", "Exception handling"],
            ["Form processing", "Basic account servicing", "Document verification"],
        ),
        _lookup(
            "finance_investment",
            "medium",
            "Recurring reporting and initial data analysis can be automated, while investment judgment remains human-led.",
            ["Investment thesis", "Risk judgment", "Client advice"],
            ["Recurring reports", "Data consolidation", "First-pass screening"],
        ),
        _lookup(
            "administration_secretarial",
            "high",
            "Scheduling, document preparation, and routine coordination are highly amenable to digital workflow automation.",
            ["Executive prioritization", "Sensitive stakeholder coordination", "Exception resolution"],
            ["Calendar scheduling", "Document formatting", "Meeting notes"],
        ),
        _lookup(
            "customer_service",
            "medium",
            "Frequently asked questions and ticket triage can be automated; complex and emotionally sensitive cases need people.",
            ["Complex case resolution", "De-escalation", "Customer empathy"],
            ["FAQ responses", "Ticket classification", "Status updates"],
        ),
        _lookup(
            "sales_business",
            "low",
            "Prospecting support and CRM administration are exposed, but negotiation and trust-based selling remain less automatable.",
            ["Negotiation", "Relationship building", "Solution discovery"],
            ["Lead enrichment", "CRM updates", "Follow-up drafting"],
        ),
        _lookup(
            "marketing",
            "medium",
            "Content variants and campaign operations can be accelerated by AI, while strategy and brand accountability remain human work.",
            ["Brand strategy", "Audience insight", "Campaign accountability"],
            ["Content variations", "Basic copy drafts", "Campaign reporting"],
        ),
        _lookup(
            "retail_wholesale",
            "medium",
            "Demand forecasting and transaction administration are automatable; in-person service and commercial judgment are less so.",
            ["Customer advice", "Merchandising judgment", "Supplier negotiation"],
            ["Order entry", "Stock reporting", "Routine pricing updates"],
        ),
        _lookup(
            "ecommerce",
            "medium",
            "Catalog operations and first-line support can be automated, while assortment and channel strategy require judgment.",
            ["Assortment strategy", "Commercial decisions", "Escalated customer cases"],
            ["Product tagging", "Listing drafts", "Order-status replies"],
        ),
        _lookup(
            "logistics",
            "medium",
            "Planning and status tracking can be optimized with software; physical exceptions and partner coordination remain people work.",
            ["Disruption handling", "Partner coordination", "Safety decisions"],
            ["Shipment tracking", "Route planning support", "Proof-of-delivery processing"],
        ),
        _lookup(
            "manufacturing_operations",
            "medium",
            "Monitoring and standardized operational records can be automated, but process improvement and safety response are less exposed.",
            ["Safety response", "Process improvement", "Root-cause investigation"],
            ["Routine inspection records", "Production reporting", "Schedule updates"],
        ),
        _lookup(
            "software_it",
            "medium",
            "Code generation can automate parts of implementation, while architecture, verification, and accountability remain human responsibilities.",
            ["System architecture", "Security review", "Production accountability"],
            ["Boilerplate code", "Test scaffolding", "Documentation drafts"],
        ),
    )


def _lookup(
    job_category_id: str,
    exposure_level: str,
    risk_reason: str,
    protected_tasks: list[str],
    at_risk_tasks: list[str],
) -> AutomationRiskLookup:
    return AutomationRiskLookup(
        job_category_id=job_category_id,
        exposure_level=exposure_level,
        risk_reason=risk_reason,
        protected_tasks=protected_tasks,
        at_risk_tasks=at_risk_tasks,
        source_title=_SOURCE_TITLE,
        source_url=_SOURCE_URL,
        published_at=_PUBLISHED_AT,
        caveat=_CAVEAT,
    )
