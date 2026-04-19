import json
from types import SimpleNamespace

from app.debate.common import _free_debate_enabled, _stage_time_limits_ms
from app.debate.config import DebateSessionConfig
from app.schemas import DebateSessionCreateIn


def test_free_debate_enabled_respects_saved_session_config():
    session = SimpleNamespace(config_json=json.dumps({"free_debate_enabled": False}))

    assert _free_debate_enabled(session) is False


def test_stage_time_limits_read_saved_session_budgets():
    session = SimpleNamespace(
        config_json=json.dumps(
            {
                "opening_budget_ms": 15_000,
                "rebuttal_budget_ms": 18_000,
                "free_debate_budget_ms": 45_000,
                "closing_budget_ms": 20_000,
            }
        )
    )

    assert _stage_time_limits_ms(session) == {
        "opening": 15_000,
        "rebuttal": 18_000,
        "free_debate": 45_000,
        "closing": 20_000,
    }


def test_debate_session_config_serializes_create_payload():
    payload = DebateSessionCreateIn(
        topic="topic",
        pro_model_id="pro",
        con_model_id="con",
        judge_model_id="judge",
        style="balanced",
        pro_style="calm",
        con_style="sharp",
        tool_mode="search",
        free_debate_enabled=False,
        opening_duration_sec=12,
        rebuttal_duration_sec=14,
        free_debate_duration_sec=50,
        closing_duration_sec=18,
    )

    config = DebateSessionConfig.from_create_payload(payload)

    assert config.to_payload() == {
        "style": "balanced",
        "pro_style": "calm",
        "con_style": "sharp",
        "tool_mode": "search",
        "judge_model_id": "judge",
        "free_debate_enabled": False,
        "opening_budget_ms": 12_000,
        "rebuttal_budget_ms": 14_000,
        "free_debate_budget_ms": 50_000,
        "closing_budget_ms": 18_000,
    }
    assert config.style_for_side("pro") == "calm"
    assert config.style_for_side("con") == "sharp"
