from __future__ import annotations

from datetime import datetime

from ..chat.types import ChatMessagePayload
from ..storage.models import MemoryDocument, MemoryItem
from .store_utils import utcnow
from .types import PastChatReference


class MemoryPromptPayloadMixin:
    def _build_prompt_message(
        self,
        *,
        documents: list[MemoryDocument],
        hit_items: list[MemoryItem],
        past_chat_refs: list[PastChatReference],
        dynamic_recap: str,
        is_fresh_conversation: bool = False,
    ) -> ChatMessagePayload:
        lines = [
            "The following is what you know about the user from past conversations.",
            "Use this naturally—do not mention that you \"remember\" it unless it genuinely improves the response.",
            "Prefer the current conversation over this background if they conflict.",
        ]
        if is_fresh_conversation:
            lines.append(
                "If this is the very first exchange, greet the user briefly using what you know about them."
            )

        # Render documents (curated summaries like user_profile, workspace_profile, conversation_brief)
        if documents:
            for document in documents:
                lines.append("")
                lines.append(f"{document.title}:")
                lines.append(document.content)

        # Render hit_items as natural context (skip technical labels like [global/Profile])
        if hit_items:
            lines.append("")
            lines.append("Related context:")
            for item in sorted(hit_items, key=self._prompt_item_sort_key):
                line = f"- {item.title}"
                if item.detail:
                    line += f": {item.detail}"
                time_hint = self._relative_time_hint(item.updated_at or item.created_at)
                if time_hint:
                    line += f" ({time_hint})"
                lines.append(line)

        if past_chat_refs:
            lines.append("")
            lines.append("Relevant past chats:")
            if dynamic_recap.strip():
                lines.append(dynamic_recap.strip())
            else:
                for reference in past_chat_refs[:5]:
                    line = f"- {reference.conversation_title}: {reference.summary or reference.excerpt}"
                    time_hint = self._relative_time_hint(reference.updated_at)
                    if time_hint:
                        line += f" ({time_hint})"
                    lines.append(line)

        return ChatMessagePayload(role="system", content="\n".join(lines).strip())

    def _prompt_item_sort_key(self, item: MemoryItem) -> tuple[int, int, int, int]:
        # 中文注释：召回注入的优先级要表达可信度和作用域，避免 inferred 全局压过当前会话事实。
        if item.confidence_state == "confirmed" and item.scope == "global":
            priority = 0
        elif item.scope == "working":
            priority = 1
        elif item.scope == "conversation":
            priority = 2
        elif item.scope == "global":
            priority = 3
        else:
            priority = 4
        return (
            priority,
            0 if item.pinned else 1,
            -int(item.evidence_count or 0),
            -(item.id or 0),
        )

    def _prompt_memory_item_payload(self, item: MemoryItem) -> dict[str, object]:
        return {
            "id": item.id,
            "scope": item.scope,
            "kind": item.kind,
            "title": item.title,
            "detail": item.detail or "",
            "tags": item.tags,
            "confidence_state": item.confidence_state,
            "evidence_count": item.evidence_count or 0,
        }

    def _prompt_memory_document_payload(self, document: MemoryDocument) -> dict[str, object]:
        content = " ".join((document.content or "").split()).strip()
        return {
            "id": document.id,
            "doc_type": document.doc_type,
            "title": document.title,
            "content": content[:600],
            "source_memory_ids": document.source_memory_ids,
        }

    def _prompt_past_chat_payload(self, reference: PastChatReference) -> dict[str, object]:
        return {
            "id": reference.id,
            "conversation_id": reference.conversation_id,
            "conversation_title": reference.conversation_title,
            "user_message_id": reference.user_message_id,
            "assistant_message_id": reference.assistant_message_id,
            "summary": reference.summary,
            "excerpt": reference.excerpt,
            "score": round(reference.score, 3),
        }

    def _relative_time_hint(self, dt: datetime | None) -> str:
        if dt is None:
            return ""
        now = utcnow()
        delta = now - dt
        if delta.days < 1:
            return "今天"
        if delta.days < 2:
            return "昨天"
        if delta.days < 7:
            return f"{delta.days} 天前"
        if delta.days < 30:
            weeks = delta.days // 7
            return f"{weeks} 周前"
        if delta.days < 365:
            months = delta.days // 30
            return f"{months} 个月前"
        years = delta.days // 365
        return f"{years} 年前"
