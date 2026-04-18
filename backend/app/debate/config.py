from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from ..schemas import DebateSessionCreateIn, ToolMode

DEFAULT_FREE_DEBATE_BUDGET_MS = 60_000
DEFAULT_STAGE_TURN_BUDGET_MS = {
    "opening": 10_000,
    "rebuttal": 10_000,
    "closing": 15_000,
    "judge_decision": 10_000,
}


def _to_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return default


def _to_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _normalize_tool_mode(value: Any) -> ToolMode:
    normalized = str(value or "").strip().lower()
    if normalized == "knowledge":
        return "knowledge"
    if normalized == "search":
        return "search"
    return "none"


@dataclass(frozen=True)
class DebateSessionConfig:
    style: str = ""
    pro_style: str = ""
    con_style: str = ""
    tool_mode: ToolMode = "none"
    judge_model_id: str = ""
    free_debate_enabled: bool = True
    opening_budget_ms: int = DEFAULT_STAGE_TURN_BUDGET_MS["opening"]
    rebuttal_budget_ms: int = DEFAULT_STAGE_TURN_BUDGET_MS["rebuttal"]
    free_debate_budget_ms: int = DEFAULT_FREE_DEBATE_BUDGET_MS
    closing_budget_ms: int = DEFAULT_STAGE_TURN_BUDGET_MS["closing"]

    @classmethod
    def from_create_payload(cls, payload: DebateSessionCreateIn) -> "DebateSessionConfig":
        return cls(
            style=payload.style.strip(),
            pro_style=payload.pro_style.strip(),
            con_style=payload.con_style.strip(),
            tool_mode=payload.tool_mode,
            judge_model_id=payload.judge_model_id.strip(),
            free_debate_enabled=payload.free_debate_enabled,
            opening_budget_ms=max(1_000, payload.opening_duration_sec * 1000),
            rebuttal_budget_ms=max(1_000, payload.rebuttal_duration_sec * 1000),
            free_debate_budget_ms=max(1_000, payload.free_debate_duration_sec * 1000),
            closing_budget_ms=max(1_000, payload.closing_duration_sec * 1000),
        )

    @classmethod
    def from_payload(cls, payload: dict[str, Any] | None) -> "DebateSessionConfig":
        data = payload or {}
        return cls(
            style=str(data.get("style", "")).strip(),
            pro_style=str(data.get("pro_style", "")).strip(),
            con_style=str(data.get("con_style", "")).strip(),
            tool_mode=_normalize_tool_mode(data.get("tool_mode")),
            judge_model_id=str(data.get("judge_model_id", "")).strip(),
            free_debate_enabled=_to_bool(data.get("free_debate_enabled"), True),
            opening_budget_ms=max(1_000, _to_int(data.get("opening_budget_ms"), DEFAULT_STAGE_TURN_BUDGET_MS["opening"])),
            rebuttal_budget_ms=max(1_000, _to_int(data.get("rebuttal_budget_ms"), DEFAULT_STAGE_TURN_BUDGET_MS["rebuttal"])),
            free_debate_budget_ms=max(1_000, _to_int(data.get("free_debate_budget_ms"), DEFAULT_FREE_DEBATE_BUDGET_MS)),
            closing_budget_ms=max(1_000, _to_int(data.get("closing_budget_ms"), DEFAULT_STAGE_TURN_BUDGET_MS["closing"])),
        )

    @classmethod
    def from_json(cls, raw: str | None) -> "DebateSessionConfig":
        try:
            payload = json.loads(raw or "{}")
        except json.JSONDecodeError:
            payload = {}
        return cls.from_payload(payload if isinstance(payload, dict) else {})

    @property
    def stage_time_limits_ms(self) -> dict[str, int]:
        return {
            "opening": self.opening_budget_ms,
            "rebuttal": self.rebuttal_budget_ms,
            "free_debate": self.free_debate_budget_ms,
            "closing": self.closing_budget_ms,
        }

    def style_for_side(self, side: str) -> str:
        if side == "pro" and self.pro_style:
            return self.pro_style
        if side == "con" and self.con_style:
            return self.con_style
        return self.style or "理性清晰"

    def to_payload(self) -> dict[str, object]:
        return {
            "style": self.style,
            "pro_style": self.pro_style,
            "con_style": self.con_style,
            "tool_mode": self.tool_mode,
            "judge_model_id": self.judge_model_id,
            "free_debate_enabled": self.free_debate_enabled,
            "opening_budget_ms": self.opening_budget_ms,
            "rebuttal_budget_ms": self.rebuttal_budget_ms,
            "free_debate_budget_ms": self.free_debate_budget_ms,
            "closing_budget_ms": self.closing_budget_ms,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_payload(), ensure_ascii=False)
