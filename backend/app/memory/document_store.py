from __future__ import annotations

import json

from sqlalchemy import case, desc, or_, select

from ..storage.models import MemoryDocument, MemoryItem
from .store_utils import DOCUMENT_TITLES, KIND_LABELS, utcnow
from .types import MemoryDocumentType


class MemoryDocumentStoreMixin:
    def list_documents(self, *, user_id: int, conversation_id: int | None) -> list[MemoryDocument]:
        filters = [MemoryDocument.user_id == user_id]
        if conversation_id is not None:
            filters.append(
                or_(
                    MemoryDocument.conversation_id.is_(None),
                    MemoryDocument.conversation_id == conversation_id,
                )
            )
        else:
            filters.append(MemoryDocument.conversation_id.is_(None))
        return self._db.scalars(
            select(MemoryDocument)
            .where(*filters)
            .order_by(
                case(
                    (MemoryDocument.doc_type == "user_profile", 0),
                    (MemoryDocument.doc_type == "conversation_brief", 1),
                    (MemoryDocument.doc_type == "workspace_profile", 2),
                    else_=3,
                ),
                desc(MemoryDocument.updated_at),
                desc(MemoryDocument.id),
            )
        ).all()

    def rebuild_documents(self, *, user_id: int, conversation_id: int | None) -> None:
        global_items = self._list_items(user_id=user_id, scope="global", status="active")
        conversation_items = self._list_items(
            user_id=user_id,
            scope="conversation",
            status="active",
            conversation_id=conversation_id,
        )
        working_items = self._list_items(
            user_id=user_id,
            scope="working",
            status="active",
            conversation_id=conversation_id,
        )

        profile_items = [item for item in global_items if item.kind in {"profile", "preference"}]
        workspace_items = [item for item in global_items if item.kind not in {"profile", "preference"}]
        conversation_doc_items = [*conversation_items, *working_items]

        self._upsert_document(
            user_id=user_id,
            conversation_id=None,
            doc_type="user_profile",
            items=profile_items,
        )
        self._upsert_document(
            user_id=user_id,
            conversation_id=None,
            doc_type="workspace_profile",
            items=workspace_items,
        )
        self._upsert_document(
            user_id=user_id,
            conversation_id=conversation_id,
            doc_type="conversation_brief",
            items=conversation_doc_items,
        )

    def _upsert_document(
        self,
        *,
        user_id: int,
        conversation_id: int | None,
        doc_type: MemoryDocumentType,
        items: list[MemoryItem],
    ) -> None:
        existing = self._db.scalar(
            select(MemoryDocument).where(
                MemoryDocument.user_id == user_id,
                MemoryDocument.conversation_id == conversation_id,
                MemoryDocument.doc_type == doc_type,
            )
        )
        content = self._render_document(doc_type=doc_type, items=items)
        if not content:
            if existing is not None:
                self._db.delete(existing)
                self._db.flush()
            return

        source_ids = [item.id for item in items]
        if existing is None:
            existing = MemoryDocument(
                user_id=user_id,
                conversation_id=conversation_id,
                doc_type=doc_type,
                title=DOCUMENT_TITLES[doc_type],
                content=content,
                source_memory_ids_json=json.dumps(source_ids, ensure_ascii=False),
                auto_managed=True,
            )
            self._db.add(existing)
            self._db.flush()
            return

        existing.title = DOCUMENT_TITLES[doc_type]
        existing.content = content
        existing.source_memory_ids_json = json.dumps(source_ids, ensure_ascii=False)
        existing.auto_managed = True
        existing.updated_at = utcnow()
        self._db.add(existing)
        self._db.flush()

    def _render_document(self, *, doc_type: MemoryDocumentType, items: list[MemoryItem]) -> str:
        if not items:
            return ""

        ordered = sorted(items, key=self._document_item_sort_key)
        groups: dict[str, list[MemoryItem]] = {}
        for item in ordered:
            groups.setdefault(item.kind, []).append(item)

        lines: list[str] = []
        if doc_type == "user_profile":
            lines.append("Stable user profile. Prefer direct evidence from the current conversation if conflicts appear.")
        elif doc_type == "workspace_profile":
            lines.append("Persistent workspace context shared across this user's conversations.")
        else:
            lines.append("Current thread brief. These points describe the ongoing conversation only.")

        for kind, group in groups.items():
            lines.append("")
            lines.append(f"{KIND_LABELS.get(kind, kind.title())}:")
            for item in group[:12]:
                state_label = "confirmed" if item.confidence_state == "confirmed" else "inferred"
                line = f"- [{state_label}] {item.title}"
                if item.detail:
                    line += f" :: {item.detail}"
                if (item.evidence_count or 0) > 1:
                    line += f" [evidence {item.evidence_count}]"
                if item.scope == "working" and item.expires_at is not None:
                    line += f" [expires {item.expires_at.strftime('%Y-%m-%d %H:%M')}]"
                lines.append(line)
        return "\n".join(lines).strip()

    def _document_item_sort_key(self, item: MemoryItem) -> tuple[int, int, int, str, int]:
        # 中文注释：文档内部顺序表达注入权重：confirmed 全局优先，其次当前 working，再到会话和 inferred 全局。
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
            0 if item.pinned else 1,
            priority,
            -int(item.evidence_count or 0),
            item.kind,
            -(item.id or 0),
        )

