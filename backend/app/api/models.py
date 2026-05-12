from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import require_current_user
from ..core.config import settings
from ..providers import build_model_options, normalize_model
from ..storage.database import get_db
from ..storage.models import BattleSession, DebateJudgeDecision, DebateParticipant, DebateTurn, Message, Run

router = APIRouter(tags=["system"])


@router.get("/api/health")
async def healthcheck():
    return {"status": "ok"}


def _bump_model_counter(counters: dict[str, int], model_id: object, delta: int = 1) -> None:
    normalized = str(model_id or "").strip()
    if normalized:
        counters[normalized] = counters.get(normalized, 0) + delta


def _model_love_scores(db: Session) -> dict[str, int]:
    scores: dict[str, int] = {}
    feedback_rows = db.execute(
        select(Run.model_id, Message.feedback_value)
        .join(Message, Run.response_message_id == Message.id)
        .where(
            Run.mode == "chat",
            Message.feedback_value.in_(("up", "down")),
        )
    ).all()
    for model_id, feedback in feedback_rows:
        # 中文注释：普通回答的赞踩是所有用户共享的实时口碑分，当前赞 +1，当前踩 -1。
        _bump_model_counter(scores, model_id, 1 if feedback == "up" else -1)

    for session in db.scalars(select(BattleSession)).all():
        for round_item in session.rounds:
            if not isinstance(round_item, dict):
                continue
            vote = round_item.get("vote")
            if vote not in {"a", "b"}:
                continue
            sides = round_item.get("sides")
            if not isinstance(sides, dict):
                continue
            winning_side = sides.get(vote)
            if not isinstance(winning_side, dict):
                continue
            model = winning_side.get("model")
            if not isinstance(model, dict):
                continue
            # 中文注释：Battle 只有明确选出 A/B 胜方时才加分；双好/双差不偏向任一模型。
            _bump_model_counter(scores, model.get("id"))

    debate_winners = db.execute(
        select(DebateParticipant.model_id)
        .join(DebateJudgeDecision, DebateJudgeDecision.session_id == DebateParticipant.session_id)
        .where(
            DebateJudgeDecision.winner_side.in_(("pro", "con")),
            DebateJudgeDecision.winner_side == DebateParticipant.side,
        )
    ).scalars()
    for model_id in debate_winners:
        # 中文注释：辩论裁决只有正反明确分出胜负时给胜方模型加一分；平局不加分。
        _bump_model_counter(scores, model_id)

    # 中文注释：对外叫“喜爱数”，不是净胜分；点踩最多把分数扣回 0，不能展示负数。
    return {model_id: max(0, score) for model_id, score in scores.items()}


def _model_usage_counts(db: Session) -> dict[str, int]:
    counts: dict[str, int] = {}
    for model_id in db.scalars(select(Run.model_id).where(Run.mode == "chat")).all():
        # 中文注释：普通聊天的模型调用来自 run 记录，所有用户共享统计。
        _bump_model_counter(counts, model_id)

    for session in db.scalars(select(BattleSession)).all():
        for round_item in session.rounds:
            if not isinstance(round_item, dict):
                continue
            sides = round_item.get("sides")
            if not isinstance(sides, dict):
                continue
            for side_id in ("a", "b"):
                side = sides.get(side_id)
                if not isinstance(side, dict):
                    continue
                if side.get("status") not in {"done", "error"}:
                    continue
                model = side.get("model")
                if isinstance(model, dict):
                    # 中文注释：Battle 两边各是一次真实模型调用，完成或失败都算一次调用。
                    _bump_model_counter(counts, model.get("id"))

    debate_turn_model_ids = db.execute(
        select(DebateParticipant.model_id)
        .join(DebateTurn, DebateTurn.speaker_participant_id == DebateParticipant.id)
        .where(
            DebateTurn.kind == "speaker_turn",
            DebateTurn.content != "",
        )
    ).scalars()
    for model_id in debate_turn_model_ids:
        # 中文注释：辩论每个已完成发言回合对应一次参赛模型调用。
        _bump_model_counter(counts, model_id)

    return counts


@router.get("/api/models")
async def list_models(
    db: Session = Depends(get_db),
    _=Depends(require_current_user),
):
    default_model = normalize_model(settings.default_model)
    love_scores = _model_love_scores(db)
    usage_counts = _model_usage_counts(db)
    models = []
    for option in build_model_options():
        model_id = str(option.get("id", "")).strip()
        models.append(
            {
                **option,
                "love_score": love_scores.get(model_id, 0),
                "usage_count": usage_counts.get(model_id, 0),
            }
        )
    return {
        "models": models,
        "default_model": default_model,
    }
