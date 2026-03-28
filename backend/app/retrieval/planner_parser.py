from __future__ import annotations

import json

from .planner_types import ToolDecision

VALID_TOOLS = {"none", "rag_search", "web_search", "both"}


def parse_tool_decision(raw: str) -> ToolDecision:
    payload = _load_json_payload(raw)
    tool = str(payload.get("tool", "")).strip()
    if tool not in VALID_TOOLS:
        raise RuntimeError(f"Tool planner returned unsupported tool: {tool or 'empty'}")

    reason = str(payload.get("reason", "")).strip()
    if not reason:
        raise RuntimeError("Tool planner returned empty reason")

    rag_query = str(payload.get("rag_query", "")).strip()
    web_query = str(payload.get("web_query", "")).strip()

    if tool in {"rag_search", "both"} and not rag_query:
        raise RuntimeError("Tool planner returned empty rag_query")
    if tool in {"web_search", "both"} and not web_query:
        raise RuntimeError("Tool planner returned empty web_query")

    return ToolDecision(
        tool=tool,
        reason=reason,
        rag_query=rag_query,
        web_query=web_query,
    )


def _load_json_payload(raw: str) -> dict[str, object]:
    cleaned = raw.strip()
    if not cleaned:
        raise RuntimeError("Tool planner returned an empty response")

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        cleaned = _strip_code_fence(cleaned)
        parsed = json.loads(cleaned)

    if not isinstance(parsed, dict):
        raise RuntimeError("Tool planner must return a JSON object")
    return parsed


def _strip_code_fence(raw: str) -> str:
    if raw.startswith("```") and raw.endswith("```"):
        lines = raw.splitlines()
        if len(lines) >= 3:
            return "\n".join(lines[1:-1]).strip()
    return raw
