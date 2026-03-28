from __future__ import annotations

from .types import WebSearchPlan, WebSearchResult


def extract_result_content(plan: WebSearchPlan, result: WebSearchResult, limit: int) -> str:
    content = result.content.strip() or result.excerpt.strip()
    if not content:
        return ""

    lines = [line.strip() for line in content.splitlines() if line.strip()]
    if not lines:
        return _truncate(content, limit)

    prioritized: list[str] = []
    seen: set[str] = set()
    keywords = tuple(dict.fromkeys([*plan.query.entity_terms, *plan.query.required_terms]))
    for line in lines:
        lowered = line.lower()
        if keywords and not any(keyword in lowered for keyword in keywords):
            continue
        if line not in seen:
            prioritized.append(line)
            seen.add(line)
        if len("\n".join(prioritized)) >= limit:
            break

    selected = prioritized or lines[:6]
    return _truncate("\n".join(selected), limit)


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return f"{text[:limit].rstrip()}..."
