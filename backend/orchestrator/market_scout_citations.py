from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


def append_market_scout_sources(answer: str, tool_calls: list[dict[str, Any]]) -> str:
    return f"{answer.rstrip()}{market_scout_source_suffix(answer, tool_calls)}"


def market_scout_source_suffix(answer: str, tool_calls: list[dict[str, Any]]) -> str:
    sources = _market_scout_sources(tool_calls)
    if not sources:
        return ""

    existing_url_keys = {_canonical_url(url) for url in _urls_in_text(answer)}
    existing_label_keys = {_canonical_label(label) for label in _markdown_link_labels(answer)}
    has_source_heading = "nguồn tham khảo" in answer.casefold() or "nguon tham khao" in answer.casefold()
    if has_source_heading:
        lines = _source_lines(
            sources,
            excluded_url_keys=existing_url_keys,
            excluded_label_keys=existing_label_keys,
        )
        return "\n" + "\n".join(lines) if lines else ""

    lines = _source_lines(sources)
    if not lines:
        return ""
    return "\n\nNguồn tham khảo:\n" + "\n".join(lines)


def _market_scout_sources(tool_calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for tool_call in reversed(tool_calls):
        if tool_call.get("name") != "market_scout":
            continue
        output = _mapping(tool_call.get("output"))
        sources = output.get("sources")
        if isinstance(sources, list):
            return [source for source in sources if isinstance(source, dict)]

        data = output.get("data") if isinstance(output.get("data"), dict) else {}
        summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
        signal = data.get("signal") if isinstance(data.get("signal"), dict) else {}
        for nested_sources in (summary.get("sources"), signal.get("sources")):
            if isinstance(nested_sources, list):
                return [source for source in nested_sources if isinstance(source, dict)]
    return []


def _source_lines(
    sources: list[dict[str, Any]],
    *,
    excluded_url_keys: set[str] | None = None,
    excluded_label_keys: set[str] | None = None,
) -> list[str]:
    lines: list[str] = []
    seen_url_keys: set[str] = set(excluded_url_keys or set())
    seen_label_keys: set[str] = set(excluded_label_keys or set())
    for source in sources:
        url = _source_url(source)
        url_key = _canonical_url(url)
        publisher = _label(source.get("publisher"))
        source_name = _label(source.get("source_name") or source.get("citation") or source.get("title"))
        label = " - ".join(part for part in (publisher, source_name) if part) or "Nguồn tham khảo"
        label_key = _canonical_label(label)
        if not url or not url_key or url_key in seen_url_keys or label_key in seen_label_keys:
            continue
        seen_url_keys.add(url_key)
        seen_label_keys.add(label_key)
        lines.append(f"- [{label}]({url})")
        if len(lines) >= 5:
            break
    return lines


def _mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                parsed = _mapping(item["text"])
                if parsed:
                    return parsed
        return {}
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _source_url(source: dict[str, Any]) -> str:
    return str(source.get("url") or "").strip()


def _urls_in_text(value: str) -> list[str]:
    return re.findall(r"https?://[^\s)>\]]+", value)


def _markdown_link_labels(value: str) -> list[str]:
    return re.findall(r"\[([^\]]+)\]\(https?://", value)


def _canonical_url(value: str) -> str:
    try:
        parts = urlsplit(value.strip())
    except ValueError:
        return ""
    if not parts.scheme or not parts.netloc:
        return ""
    filtered_query = [
        (key, item)
        for key, item in parse_qsl(parts.query, keep_blank_values=True)
        if not key.casefold().startswith("utm_") and key.casefold() not in {"src", "source", "ref"}
    ]
    path = parts.path.rstrip("/") or "/"
    return urlunsplit(
        (
            parts.scheme.casefold(),
            parts.netloc.casefold(),
            path,
            urlencode(filtered_query),
            "",
        )
    )


def _label(value: Any) -> str:
    text = " ".join(str(value or "").replace("[", "").replace("]", "").split())
    return text[:100].strip()


def _canonical_label(value: str) -> str:
    return " ".join(value.casefold().split())
