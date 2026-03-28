from __future__ import annotations

import json

MAX_HISTORY_ITEMS = 6
MAX_MESSAGE_CHARS = 500

SYSTEM_PROMPT = """You are a retrieval tool planner for a chat application.
Decide which retrieval tool is needed before answer generation.

Available tool names:
- none
- rag_search
- web_search
- both

Tool semantics:
- rag_search: search the user's private notes, Obsidian vault, local documents, diary, journal, files, or personal knowledge base.
- web_search: search public internet information, especially freshness-sensitive or lookup-style information.
- both: only when the answer truly needs both private notes and public web evidence.
- none: no retrieval tool is needed.

Decision rules:
- Prefer rag_search for questions about the user's own notes, documents, diary, vault, files, or previous written material.
- Prefer web_search for public facts, recent events, weather, stocks, sports, news, or public entity lookup.
- Choose both only when both sources are necessary for a correct answer.
- Choose none when the model can answer directly without retrieval.
- Do not invent unavailable tools.
- Respect tool availability. If a needed tool is disabled, still choose that tool instead of lying.

Return exactly one JSON object and nothing else.
Schema:
{
  "tool": "none" | "rag_search" | "web_search" | "both",
  "reason": "short reason",
  "rag_query": "required when tool is rag_search or both",
  "web_query": "required when tool is web_search or both"
}
"""


def build_tool_planner_messages(
    *,
    query: str,
    message_history: list[dict[str, str]],
    use_rag: bool,
    use_web: bool,
) -> list[dict[str, str]]:
    transcript = [
        {
            "role": item.get("role", ""),
            "content": item.get("content", "")[:MAX_MESSAGE_CHARS],
        }
        for item in message_history
        if item.get("role") in {"user", "assistant"} and item.get("content", "").strip()
    ][-MAX_HISTORY_ITEMS:]
    payload = {
        "current_query": query,
        "recent_messages": transcript,
        "tools": [
            {
                "name": "rag_search",
                "enabled": use_rag,
                "description": "Search the user's private notes and local documents.",
            },
            {
                "name": "web_search",
                "enabled": use_web,
                "description": "Search public web information.",
            },
        ],
    }
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False, indent=2)},
    ]
