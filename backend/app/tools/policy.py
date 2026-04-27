from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ..schemas import ToolMode
from ..retrieval.rag.text import normalize_path_fragment

ContextTool = Literal["knowledge", "search"]
ToolPolicyMode = Literal["off", "knowledge", "search"]


@dataclass(frozen=True)
class ToolPolicy:
    mode: ToolPolicyMode
    source_mode: ToolMode
    knowledge_folders: tuple[str, ...] = ()

    @property
    def is_enabled(self) -> bool:
        return self.mode != "off"

    @property
    def requested_tools(self) -> tuple[ContextTool, ...]:
        if self.mode == "knowledge":
            return ("knowledge",)
        if self.mode == "search":
            return ("search",)
        return ()

    def to_metadata(self) -> dict[str, str]:
        payload = {
            "tool_mode": self.source_mode,
            "tool_policy": self.mode,
        }
        if self.knowledge_folders:
            payload["knowledge_folders"] = ",".join(self.knowledge_folders)
        return payload

    def to_context_payload(self) -> dict[str, object]:
        payload: dict[str, object] = dict(self.to_metadata())
        payload["tool_plan"] = list(self.requested_tools)
        payload["knowledge_folders"] = list(self.knowledge_folders)
        return payload


def build_tool_policy(tool_mode: ToolMode, *, knowledge_folders: list[str] | None = None) -> ToolPolicy:
    folders = _normalize_knowledge_folders(knowledge_folders or [])
    if tool_mode == "knowledge":
        return ToolPolicy(mode="knowledge", source_mode=tool_mode, knowledge_folders=folders)
    if tool_mode == "search":
        return ToolPolicy(mode="search", source_mode=tool_mode)
    return ToolPolicy(mode="off", source_mode="none")


def _normalize_knowledge_folders(values: list[str]) -> tuple[str, ...]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        raw_value = str(value)
        folder = "" if raw_value.strip() == "__root__" else normalize_path_fragment(raw_value)
        if folder in seen:
            continue
        seen.add(folder)
        normalized.append(folder)
        if len(normalized) >= 20:
            break
    return tuple(normalized)
