from __future__ import annotations

import re
import unicodedata
from collections import Counter
from collections.abc import Sequence
from typing import Protocol

from backend.market_scout.repositories.trend_tracker.trend_job_fact_repository import TrendJobFactRepository
from backend.market_scout.schemas.trend_tracker.job_category_trend import JobCategoryTrendJobFact
from backend.market_scout.schemas.trend_tracker.role_fact_match import RoleFactMatch
from backend.market_scout.schemas.trend_tracker.role_resolution import RoleResolutionResult


DEFAULT_TOP_K = 5
DEFAULT_MAX_SCAN = 2000
MIN_ROLE_MATCH_SCORE = 0.25
MIN_ACCEPT_TOP_SCORE = 0.65
MIN_ACCEPT_AVG_TOP3_SCORE = 0.55
MIN_ACCEPT_CATEGORY_SHARE = 0.55
MIN_ACCEPT_LOCATION_MATCH_SHARE = 0.5
SINGLE_MATCH_STRONG_SCORE = 0.85
TITLE_CONTAINS_BONUS = 0.25
LOCATION_BOOST = 0.1
ACTIVE_BOOST = 0.05


class SemanticRoleFactSearcher(Protocol):
    def search(
        self,
        *,
        role_query: str,
        location_id: str | None = None,
        top_k: int = DEFAULT_TOP_K,
    ) -> Sequence[RoleFactMatch]:
        ...


class RoleFactSearchService:
    """Resolve natural-language role mentions against trend job facts."""

    def __init__(
        self,
        *,
        fact_repository: TrendJobFactRepository | None = None,
        semantic_searcher: SemanticRoleFactSearcher | None = None,
        max_scan: int = DEFAULT_MAX_SCAN,
        min_score: float = MIN_ROLE_MATCH_SCORE,
        min_accept_top_score: float = MIN_ACCEPT_TOP_SCORE,
        min_accept_avg_top3_score: float = MIN_ACCEPT_AVG_TOP3_SCORE,
        min_accept_category_share: float = MIN_ACCEPT_CATEGORY_SHARE,
        min_accept_location_match_share: float = MIN_ACCEPT_LOCATION_MATCH_SHARE,
        single_match_strong_score: float = SINGLE_MATCH_STRONG_SCORE,
    ) -> None:
        if max_scan <= 0:
            raise ValueError("max_scan must be positive.")
        for name, value in {
            "min_score": min_score,
            "min_accept_top_score": min_accept_top_score,
            "min_accept_avg_top3_score": min_accept_avg_top3_score,
            "min_accept_category_share": min_accept_category_share,
            "min_accept_location_match_share": min_accept_location_match_share,
            "single_match_strong_score": single_match_strong_score,
        }.items():
            if not 0 <= value <= 1:
                raise ValueError(f"{name} must be between 0 and 1.")
        self.fact_repository = fact_repository or TrendJobFactRepository()
        self.semantic_searcher = semantic_searcher
        self.max_scan = max_scan
        self.min_score = min_score
        self.min_accept_top_score = min_accept_top_score
        self.min_accept_avg_top3_score = min_accept_avg_top3_score
        self.min_accept_category_share = min_accept_category_share
        self.min_accept_location_match_share = min_accept_location_match_share
        self.single_match_strong_score = single_match_strong_score

    def search(
        self,
        *,
        role_query: str,
        location_id: str | None = None,
        top_k: int = DEFAULT_TOP_K,
    ) -> list[RoleFactMatch]:
        if top_k <= 0:
            raise ValueError("top_k must be positive.")

        role_tokens = _tokens(role_query)
        if not role_tokens:
            return []

        matches_by_key: dict[str, RoleFactMatch] = {}
        for fact in self.fact_repository.list_for_role_search(location_id=location_id, max_scan=self.max_scan):
            match = self._keyword_match(fact, role_tokens=role_tokens, location_id=location_id)
            if match and match.score >= self.min_score:
                matches_by_key[match.job_key] = match

        if self.semantic_searcher is not None:
            for semantic_match in self.semantic_searcher.search(
                role_query=role_query,
                location_id=location_id,
                top_k=top_k,
            ):
                current = matches_by_key.get(semantic_match.job_key)
                if current is None:
                    matches_by_key[semantic_match.job_key] = semantic_match
                else:
                    preferred = semantic_match if semantic_match.score > current.score else current
                    matches_by_key[semantic_match.job_key] = RoleFactMatch(
                        job_key=preferred.job_key,
                        job_title=preferred.job_title,
                        company=preferred.company,
                        job_url=preferred.job_url,
                        job_category_ids=preferred.job_category_ids,
                        job_family_ids=preferred.job_family_ids,
                        location_ids=preferred.location_ids,
                        score=max(current.score, semantic_match.score),
                        match_method="hybrid",
                    )

        return sorted(matches_by_key.values(), key=lambda item: (-item.score, item.job_title, item.job_key))[:top_k]

    def resolve_role(
        self,
        *,
        role_query: str,
        location_id: str | None = None,
        top_k: int = DEFAULT_TOP_K,
    ) -> RoleResolutionResult:
        matches = self.search(role_query=role_query, location_id=location_id, top_k=top_k)
        if not matches:
            return _role_resolution_result(
                matches=[],
                category_id=None,
                family_id=None,
                confidence="low",
                accepted=False,
                top_score=0.0,
                category_score_share=0.0,
                location_match_share=None if location_id is None else 0.0,
                rejection_reason="no_role_matches",
            )

        category_scores = _score_by_value(matches, "job_category_ids")
        family_scores = _score_by_value(matches, "job_family_ids")
        category_id, category_score = _top_counter_item(category_scores)
        family_id, _ = _top_counter_item(family_scores)
        total_category_score = sum(match.score for match in matches)
        category_score_share = category_score / total_category_score if total_category_score else 0.0
        top_score = matches[0].score
        avg_top3_score = sum(match.score for match in matches[:3]) / min(len(matches), 3)
        location_match_share = _location_match_share(matches, location_id)

        accepted, confidence, rejection_reason = self._evaluate_resolution(
            matched_fact_count=len(matches),
            top_score=top_score,
            avg_top3_score=avg_top3_score,
            category_score_share=category_score_share,
            location_match_share=location_match_share,
            has_category=category_id is not None,
            has_family=family_id is not None,
        )
        return _role_resolution_result(
            matches=matches,
            category_id=category_id if accepted else None,
            family_id=family_id if accepted else None,
            confidence=confidence,
            accepted=accepted,
            top_score=top_score,
            category_score_share=category_score_share,
            location_match_share=location_match_share,
            rejection_reason=rejection_reason,
        )

    def resolve_category_and_family(
        self,
        *,
        role_query: str,
        location_id: str | None = None,
        top_k: int = DEFAULT_TOP_K,
    ) -> tuple[str | None, str | None, list[RoleFactMatch]]:
        resolution = self.resolve_role(role_query=role_query, location_id=location_id, top_k=top_k)
        return resolution.resolved_job_category_id, resolution.resolved_job_family_id, resolution.matches

    def _evaluate_resolution(
        self,
        *,
        matched_fact_count: int,
        top_score: float,
        avg_top3_score: float,
        category_score_share: float,
        location_match_share: float | None,
        has_category: bool,
        has_family: bool,
    ) -> tuple[bool, str, str | None]:
        if not has_category or not has_family:
            return False, "low", "missing_category_or_family"
        if category_score_share < self.min_accept_category_share:
            return False, "low", "ambiguous_category"
        if location_match_share is not None and location_match_share < self.min_accept_location_match_share:
            return False, "low", "weak_location_coverage"
        if matched_fact_count == 1:
            if top_score >= self.single_match_strong_score:
                return True, "medium", None
            return False, "low", "insufficient_sample"
        if top_score < self.min_accept_top_score and avg_top3_score < self.min_accept_avg_top3_score:
            return False, "low", "weak_match_score"
        if top_score >= self.single_match_strong_score and category_score_share >= 0.75:
            return True, "high", None
        return True, "medium", None

    def _keyword_match(
        self,
        fact: JobCategoryTrendJobFact,
        *,
        role_tokens: set[str],
        location_id: str | None,
    ) -> RoleFactMatch | None:
        title_tokens = _tokens(fact.job_title)
        if not title_tokens:
            return None
        if not fact.job_category_ids or not fact.job_family_ids:
            return None

        overlap = role_tokens & title_tokens
        if not overlap:
            return None

        score = len(overlap) / len(role_tokens)
        normalized_title = _text_key(fact.job_title)
        normalized_role = " ".join(sorted(role_tokens, key=lambda token: _text_key(fact.job_title).find(token)))
        if normalized_role and normalized_role in normalized_title:
            score += TITLE_CONTAINS_BONUS
        if location_id and location_id in fact.location_ids:
            score += LOCATION_BOOST
        if fact.is_active is True:
            score += ACTIVE_BOOST

        return RoleFactMatch(
            job_key=fact.job_key,
            job_title=fact.job_title,
            company=fact.company,
            job_url=fact.job_url,
            job_category_ids=list(fact.job_category_ids),
            job_family_ids=list(fact.job_family_ids),
            location_ids=list(fact.location_ids),
            score=min(score, 1.0),
            match_method="keyword",
        )


def _role_resolution_result(
    *,
    matches: list[RoleFactMatch],
    category_id: str | None,
    family_id: str | None,
    confidence: str,
    accepted: bool,
    top_score: float,
    category_score_share: float,
    location_match_share: float | None,
    rejection_reason: str | None,
) -> RoleResolutionResult:
    return RoleResolutionResult(
        resolved_job_category_id=category_id,
        resolved_job_family_id=family_id,
        confidence=confidence,
        accepted=accepted,
        top_score=top_score,
        matched_fact_count=len(matches),
        category_score_share=category_score_share,
        location_match_share=location_match_share,
        rejection_reason=rejection_reason,
        matches=list(matches),
    )


def _score_by_value(matches: list[RoleFactMatch], attribute: str) -> Counter[str]:
    scores: Counter[str] = Counter()
    for match in matches:
        for value in getattr(match, attribute):
            scores[value] += match.score
    return scores


def _top_counter_item(counter: Counter[str]) -> tuple[str | None, float]:
    if not counter:
        return None, 0.0
    return sorted(counter.items(), key=lambda item: (-item[1], item[0]))[0]


def _location_match_share(matches: list[RoleFactMatch], location_id: str | None) -> float | None:
    if not location_id:
        return None
    if not matches:
        return 0.0
    matching = sum(1 for match in matches if location_id in match.location_ids)
    return matching / len(matches)


def _tokens(value: str | None) -> set[str]:
    text = _text_key(value)
    if not text:
        return set()
    return {token for token in text.split() if len(token) >= 2}


def _text_key(value: str | None) -> str:
    if not value:
        return ""
    text = str(value).replace(chr(273), "d").replace(chr(272), "D")
    text = unicodedata.normalize("NFD", text)
    text = "".join(character for character in text if unicodedata.category(character) != "Mn")
    text = text.casefold()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()