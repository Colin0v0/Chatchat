from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ..schemas import ToolMode

ContextTool = Literal["knowledge", "search"]
ToolPolicyMode = Literal["off", "knowledge", "search"]


@dataclass(frozen=True)
class ToolPolicy:
    mode: ToolPolicyMode
    source_mode: ToolMode

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
        return {
            "tool_mode": self.source_mode,
            "tool_policy": self.mode,
        }

    def to_context_payload(self) -> dict[str, object]:
        payload: dict[str, object] = dict(self.to_metadata())
        payload["tool_plan"] = list(self.requested_tools)
        return payload


def build_tool_policy(tool_mode: ToolMode) -> ToolPolicy:
    if tool_mode == "knowledge":
        return ToolPolicy(mode="knowledge", source_mode=tool_mode)
    if tool_mode == "search":
        return ToolPolicy(mode="search", source_mode=tool_mode)
    return ToolPolicy(mode="off", source_mode="none")
