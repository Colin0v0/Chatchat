from __future__ import annotations

import json
import logging
import re

from ..chat.types import ChatMessagePayload
from ..llm import complete_chat
from .types import MEMORY_KINDS, MEMORY_SCOPES, MemoryCandidate

logger = logging.getLogger("chatchat.memory")

_THINK_BLOCK_RE = re.compile(r"<think>.*?</think>", re.IGNORECASE | re.DOTALL)
_INVALID_JSON_ESCAPE_RE = re.compile(r'\\(?!["\\/bfnrtu])')


class MemoryExtractor:
    def __init__(self, *, extract_limit: int):
        self._extract_limit = max(1, extract_limit)

    async def extract(
        self,
        *,
        model: str,
        conversation_title: str,
        user_message: str,
        assistant_message: str,
        existing_memories: list[str],
    ) -> list[MemoryCandidate]:
        if not user_message.strip() or not assistant_message.strip():
            return []

        prompt = self._build_prompt(
            conversation_title=conversation_title,
            user_message=user_message,
            assistant_message=assistant_message,
            existing_memories=existing_memories,
        )
        raw = await complete_chat(
            model=model,
            messages=prompt,
            thinking_enabled=False,
        )
        payload = self._parse_payload(raw)
        if payload is None:
            text_preview = raw[:200] if raw else "(empty response)"
            logger.info(
                "memory extraction returned invalid payload (non-fatal, skipped) | model=%s | preview=%s",
                model,
                text_preview,
            )
            return []
        return self._normalize_candidates(payload)

    def _build_prompt(
        self,
        *,
        conversation_title: str,
        user_message: str,
        assistant_message: str,
        existing_memories: list[str],
    ) -> list[ChatMessagePayload]:
        memory_block = "\n".join(f"- {item}" for item in existing_memories) or "- none"
        instructions = (
            "You extract durable memories for a personal AI workspace.\n"
            "Return strict JSON with this shape: "
            '{"items":[{"scope":"global|conversation","kind":"profile|preference|goal|project|fact|constraint","title":"...","detail":"...","tags":["..."],"confidence":0.0}]}\n'
            "Keep items atomic. Prefer facts that will matter in future turns.\n"
            "Do not output any <think> tags or analysis sections.\n"
            "Do not use markdown fences.\n"
            "Do not include LaTeX, backslashes, or formulas in title/detail; rewrite them as plain Chinese text.\n"
            "Do not include one-off requests, greetings, temporary wording, or things already obvious from the current question alone.\n"
            "Default to scope=conversation.\n"
            "Use scope=global only for durable user identity, long-term preferences, or stable facts that should remain useful across unrelated future chats.\n"
            "If an item is specific to the current task, current project, current session, or recent exchange, it must stay in scope=conversation.\n"
            "Avoid paraphrasing an existing memory as a new item. If a similar memory already exists, keep wording aligned with the existing one.\n"
            f"Return at most {self._extract_limit} items. No markdown.\n"
            "Write title, detail, and tags in concise Simplified Chinese."
        )
        content = (
            f"Conversation title: {conversation_title.strip() or 'Untitled'}\n\n"
            f"Existing related memories:\n{memory_block}\n\n"
            f"Latest user message:\n{user_message.strip()}\n\n"
            f"Latest assistant response:\n{assistant_message.strip()}"
        )
        return [
            ChatMessagePayload(role="system", content=instructions),
            ChatMessagePayload(role="user", content=content),
        ]

    def _parse_payload(self, raw: str) -> dict[str, object] | None:
        text = raw.strip()
        if not text:
            return None

        # Some thinking models still emit hidden thought blocks even when disabled.
        text = _THINK_BLOCK_RE.sub("", text).strip()

        if text.startswith("```"):
            lines = text.splitlines()
            if len(lines) >= 3:
                text = "\n".join(lines[1:-1]).strip()

        if not text:
            return None

        # If the model adds pre/post text, keep only the JSON-looking segment.
        object_start = text.find("{")
        object_end = text.rfind("}")
        if object_start != -1 and object_end > object_start:
            text = text[object_start : object_end + 1]

        # LLM outputs often include single backslashes (e.g. \cdot) that break strict JSON.
        candidate = _INVALID_JSON_ESCAPE_RE.sub(r"\\\\", text)

        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError as exc:
            preview = candidate[:180] if candidate else "(empty)"
            logger.info(
                "memory extraction json parse error | error=%s | preview=%s",
                str(exc),
                preview,
            )
            return None

        if not isinstance(payload, dict):
            logger.debug(
                "memory extraction payload is not dict | type=%s",
                type(payload).__name__,
            )
            return None

        return payload

    def _normalize_candidates(self, payload: dict[str, object]) -> list[MemoryCandidate]:
        items = payload.get("items")
        if not isinstance(items, list):
            return []

        candidates: list[MemoryCandidate] = []
        seen_signatures: set[tuple[str, str, str, str]] = set()
        for item in items:
            if not isinstance(item, dict):
                continue
            scope = str(item.get("scope", "conversation")).strip().lower()
            if scope not in MEMORY_SCOPES:
                continue
            kind = str(item.get("kind", "fact")).strip().lower()
            if kind not in MEMORY_KINDS:
                continue
            title = " ".join(str(item.get("title", "")).strip().split())
            if not title:
                continue
            detail = " ".join(str(item.get("detail", "")).strip().split())
            tags_raw = item.get("tags", [])
            tags = []
            if isinstance(tags_raw, list):
                for value in tags_raw:
                    tag = str(value).strip()
                    if tag and tag not in tags:
                        tags.append(tag)
            confidence_raw = item.get("confidence", 0.7)
            confidence = 0.7
            if isinstance(confidence_raw, (int, float)):
                confidence = max(0.0, min(1.0, float(confidence_raw)))
            signature = (
                scope,
                kind,
                title.casefold(),
                detail.casefold(),
            )
            if signature in seen_signatures:
                continue
            seen_signatures.add(signature)
            candidates.append(
                MemoryCandidate(
                    scope=scope,
                    kind=kind,
                    title=title,
                    detail=detail,
                    tags=tuple(tags[:6]),
                    confidence=confidence,
                )
            )
            if len(candidates) >= self._extract_limit:
                break
        return candidates
