from __future__ import annotations

import re
from datetime import datetime, timedelta

from ..storage.models import Message
from .store_utils import utcnow
from .types import (
    MemoryCandidate,
    MemoryConfidenceState,
    MemoryStatus,
    MemoryTurnPolicy,
    MemoryWritePolicy,
)

EXPLICIT_MEMORY_MARKERS = (
    "记住",
    "记下来",
    "加入记忆",
    "加入全局记忆",
    "以后都",
    "以后默认",
    "长期记住",
    "remember this",
    "save this memory",
)
GLOBAL_MEMORY_MARKERS = (
    "全局",
    "长期",
    "以后都",
    "以后默认",
    "跨会话",
    "一直",
    "always",
    "across chats",
)
LOCAL_MEMORY_MARKERS = (
    "本次",
    "这次",
    "当前",
    "目前",
    "暂时",
    "先",
    "本轮",
    "这轮",
    "本会话",
    "这个会话",
    "当前对话",
    "局部",
    "临时",
    "this chat",
    "this conversation",
    "this time",
    "for now",
    "temporary",
)
STABLE_GLOBAL_MARKERS = (
    "姓名",
    "名字",
    "生日",
    "邮箱",
    "电话",
    "职业",
    "住在",
    "居住",
    "所在城市",
    "默认",
    "偏好",
    "习惯",
    "喜欢",
    "不喜欢",
    "name",
    "birthday",
    "email",
    "phone",
    "job",
    "profession",
    "live in",
    "prefer",
    "preference",
    "default",
)
TRANSIENT_MARKERS = (
    "这次",
    "本次",
    "当前",
    "先",
    "暂时",
    "目前",
    "this time",
    "for now",
    "current",
    "temporary",
)
GROOMING_MARKERS = (
    "谢谢",
    "感谢",
    "明白了",
    "好的",
    "知道了",
    "没问题",
    "ok",
    "okay",
    "thx",
    "thanks",
    "got it",
    "明白",
    "收到",
    "嗯",
    "哦",
    "啊",
    "好",
    "行",
    "可以",
)
TOKEN_PATTERN = re.compile(r"[0-9A-Za-z_\u4e00-\u9fff]{2,}")
PENDING_MEMORY_MIN_CONFIDENCE = 0.4


class MemoryPolicyMixin:
    def _build_turn_policy(self, *, user_message: Message) -> MemoryTurnPolicy:
        content = (user_message.content or "").strip().casefold()
        explicit_request = any(marker in content for marker in EXPLICIT_MEMORY_MARKERS)
        has_attachments = bool(user_message.attachments)
        target_scope = None
        if explicit_request:
            if any(marker in content for marker in GLOBAL_MEMORY_MARKERS):
                target_scope = "global"
            elif any(marker in content for marker in LOCAL_MEMORY_MARKERS):
                target_scope = "conversation"
        return MemoryTurnPolicy(
            explicit_request=explicit_request,
            target_scope=target_scope,
            allow_automatic_storage=not explicit_request and not has_attachments,
            skip_due_to_attachments=has_attachments and not explicit_request,
            modality="attachment" if has_attachments else "text",
        )

    def _should_attempt_auto_memory(self, *, user_message: Message) -> bool:
        content = (user_message.content or "").strip()
        if len(content) < 8:
            return False
        tokens = TOKEN_PATTERN.findall(content)
        if len(tokens) < 2:
            return False
        # Skip grooming / low-information responses
        content_lower = content.casefold()
        if any(marker in content_lower for marker in GROOMING_MARKERS):
            # If the message is very short and only contains grooming words, skip
            if len(content) < 30:
                return False
        return True

    def _resolve_auto_memory(
        self,
        *,
        candidate,
        policy: MemoryTurnPolicy,
    ) -> tuple[MemoryCandidate, MemoryStatus, MemoryConfidenceState, datetime | None, MemoryWritePolicy] | None:
        if policy.explicit_request:
            scope = self._resolve_explicit_scope(candidate=candidate, policy=policy)
            expires_at = utcnow() + timedelta(days=2) if scope == "working" else None
            return (
                MemoryCandidate(
                    scope=scope,
                    kind=candidate.kind,
                    title=candidate.title,
                    detail=candidate.detail,
                    tags=candidate.tags,
                    confidence=candidate.confidence,
                ),
                "active",
                "confirmed",
                expires_at,
                "session" if scope == "working" else "explicit",
            )

        if not policy.allow_automatic_storage:
            return None

        if self._looks_transient(candidate):
            return (
                MemoryCandidate(
                    scope="working",
                    kind=candidate.kind,
                    title=candidate.title,
                    detail=candidate.detail,
                    tags=candidate.tags,
                    confidence=candidate.confidence,
                ),
                "active",
                "inferred",
                utcnow() + timedelta(days=2),
                "session",
            )

        if candidate.confidence < self._auto_memory_min_confidence:
            if candidate.confidence < PENDING_MEMORY_MIN_CONFIDENCE:
                return None
            return (
                MemoryCandidate(
                    scope="conversation",
                    kind=candidate.kind,
                    title=candidate.title,
                    detail=candidate.detail,
                    tags=candidate.tags,
                    confidence=candidate.confidence,
                ),
                "active",
                "pending",
                None,
                "session",
            )

        scope = self._resolve_automatic_scope(candidate)
        return (
            MemoryCandidate(
                scope=scope,
                kind=candidate.kind,
                title=candidate.title,
                detail=candidate.detail,
                tags=candidate.tags,
                confidence=candidate.confidence,
            ),
            "active",
            "inferred",
            None,
            "explicit" if scope == "global" else "session",
        )

    def _looks_transient(self, candidate) -> bool:
        combined = " ".join([candidate.title, candidate.detail]).casefold()
        if any(marker in combined for marker in TRANSIENT_MARKERS):
            return True
        return candidate.kind in {"goal", "project", "constraint"}

    def _resolve_explicit_scope(
        self,
        *,
        candidate,
        policy: MemoryTurnPolicy,
    ) -> str:
        if policy.target_scope is not None:
            return policy.target_scope
        if self._looks_transient(candidate):
            return "working"
        if self._looks_stable_global(candidate):
            return "global"
        return self._resolve_automatic_scope(candidate)

    def _resolve_automatic_scope(self, candidate) -> str:
        # 中文注释：自动记忆默认留在当前会话；身份类画像可以先作为 inferred global，偏好需要多次证据再晋升。
        if candidate.kind == "profile" or self._looks_stable_identity_fact(candidate):
            return "global"
        return "conversation"

    def _looks_stable_global(self, candidate) -> bool:
        if self._looks_transient(candidate):
            return False
        if candidate.kind in {"profile", "preference"}:
            return True
        combined = " ".join([candidate.title, candidate.detail]).casefold()
        return any(marker in combined for marker in STABLE_GLOBAL_MARKERS)

    def _looks_stable_identity_fact(self, candidate) -> bool:
        if self._looks_transient(candidate):
            return False
        combined = " ".join([candidate.title, candidate.detail]).casefold()
        identity_markers = {
            "姓名",
            "名字",
            "生日",
            "邮箱",
            "电话",
            "职业",
            "住在",
            "居住",
            "所在城市",
            "name",
            "birthday",
            "email",
            "phone",
            "job",
            "profession",
            "live in",
        }
        return any(marker in combined for marker in identity_markers)
