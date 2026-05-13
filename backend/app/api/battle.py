from __future__ import annotations

import json
from dataclasses import dataclass, field
from collections.abc import AsyncIterator
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from ..auth import require_current_user
from ..chat.context import append_message_attachments
from ..chat.history import MessageHistoryService
from ..chat.types import ChatMessagePayload
from ..chat.state import get_chat_services
from ..multimodal.file_types import resolve_attachment_type
from ..runtime.model_runner import stream_model_response
from ..schemas import (
    BattlePreferenceDatasetRowOut,
    BattlePreferenceModelStatOut,
    BattlePreferenceSummaryOut,
    BattleRoundPayload,
    BattleSessionCreateIn,
    BattleSessionDetailOut,
    BattleSessionRenameIn,
    BattleSessionSummaryOut,
    BattleSessionUpdateIn,
    BattleStreamRequest,
    ReasoningProfileValue,
    ToolMode,
)
from ..providers import resolve_model_profile
from ..storage.database import get_db
from ..storage.media import media_url, persist_uploaded_attachments, remove_media_files
from ..storage.models import BattleSession, Conversation, Message, User
from ..tools import ToolContextBuildRequest, ToolPlanRequest, build_tool_policy

router = APIRouter(prefix="/api/battle", tags=["battle"])


@dataclass(frozen=True)
class BattlePreparedPrompt:
    messages: list[ChatMessagePayload]
    refusal_message: str | None = None
    sources: list[dict[str, str | float | None]] | None = None
    attachments: list[dict[str, object]] = field(default_factory=list)


def _ndjson(payload: dict[str, object]) -> str:
    return json.dumps(payload, ensure_ascii=False) + "\n"


def _ensure_battle_input_present(*, content: str, upload_count: int) -> None:
    if not content and upload_count == 0:
        raise HTTPException(status_code=400, detail="Message cannot be empty")


def _ensure_battle_title_present(title: str) -> str:
    normalized = title.strip()
    if not normalized:
        raise HTTPException(status_code=400, detail="Battle title cannot be empty")
    return normalized


def _ensure_uploads_supported_by_model(*, model: str, uploads: list[UploadFile]) -> None:
    profile = resolve_model_profile(model)
    if profile is None:
        raise HTTPException(status_code=400, detail="Model is not enabled in catalog.")

    for upload in uploads:
        try:
            attachment_type = resolve_attachment_type(
                getattr(upload, "filename", "") or "",
                getattr(upload, "content_type", "") or "",
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        if attachment_type.kind == "image" and not profile.capabilities.input_image:
            raise HTTPException(status_code=400, detail="The selected model does not support image uploads.")
        if attachment_type.extension == ".pdf" and not profile.capabilities.input_pdf:
            raise HTTPException(status_code=400, detail="The selected model does not support PDF uploads.")
        if attachment_type.kind == "file" and attachment_type.extension != ".pdf" and not profile.capabilities.input_other_file:
            raise HTTPException(status_code=400, detail="The selected model does not support file uploads.")


def _load_battle_session_for_user(*, db: Session, session_id: int, user_id: int) -> BattleSession:
    session = db.scalar(
        select(BattleSession).where(
            BattleSession.id == session_id,
            BattleSession.user_id == user_id,
        )
    )
    if session is None:
        raise HTTPException(status_code=404, detail="Battle session not found")
    return session


def _battle_preview(rounds: list[dict[str, object]]) -> str:
    if not rounds:
        return ""
    latest = rounds[-1]
    prompt = str(latest.get("prompt", "")).strip().replace("\n", " ")
    return prompt[:140]


def _battle_session_summary_payload(session: BattleSession) -> BattleSessionSummaryOut:
    rounds = session.rounds
    return BattleSessionSummaryOut(
        id=session.id,
        title=session.title,
        updated_at=session.updated_at,
        last_message_preview=_battle_preview(rounds),
    )


def _battle_session_detail_payload(session: BattleSession) -> BattleSessionDetailOut:
    return BattleSessionDetailOut(
        id=session.id,
        title=session.title,
        created_at=session.created_at,
        updated_at=session.updated_at,
        rounds=session.rounds,
    )


def _side_model_value(round_payload: BattleRoundPayload, side_id: str, key: str) -> str:
    side = round_payload.sides.a if side_id == "a" else round_payload.sides.b
    value = side.model.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Battle side {side_id} model.{key} must be a non-empty string")
    return value.strip()


def _battle_preference_rows(sessions: list[BattleSession]) -> list[BattlePreferenceDatasetRowOut]:
    rows: list[BattlePreferenceDatasetRowOut] = []
    for session in sessions:
        for raw_round in session.rounds:
            round_payload = BattleRoundPayload.model_validate(raw_round)
            if round_payload.vote is None:
                continue

            model_a_id = _side_model_value(round_payload, "a", "id")
            model_a_label = _side_model_value(round_payload, "a", "label")
            model_b_id = _side_model_value(round_payload, "b", "id")
            model_b_label = _side_model_value(round_payload, "b", "label")
            preferred_side = round_payload.vote if round_payload.vote in {"a", "b"} else None
            preferred_model_id = model_a_id if preferred_side == "a" else model_b_id if preferred_side == "b" else None
            rejected_model_id = model_b_id if preferred_side == "a" else model_a_id if preferred_side == "b" else None
            rows.append(
                BattlePreferenceDatasetRowOut(
                    session_id=session.id,
                    session_title=session.title,
                    round_id=round_payload.id,
                    prompt=round_payload.prompt,
                    vote=round_payload.vote,
                    preferred_side=preferred_side,
                    preferred_model_id=preferred_model_id,
                    rejected_model_id=rejected_model_id,
                    model_a_id=model_a_id,
                    model_a_label=model_a_label,
                    model_b_id=model_b_id,
                    model_b_label=model_b_label,
                    answer_a=round_payload.sides.a.content,
                    answer_b=round_payload.sides.b.content,
                    created_at=round_payload.createdAt,
                )
            )
    return rows


def _battle_preference_summary(rows: list[BattlePreferenceDatasetRowOut]) -> BattlePreferenceSummaryOut:
    stats: dict[str, BattlePreferenceModelStatOut] = {}

    def ensure_model(model_id: str, label: str) -> BattlePreferenceModelStatOut:
        current = stats.get(model_id)
        if current is not None:
            return current
        current = BattlePreferenceModelStatOut(model_id=model_id, label=label)
        stats[model_id] = current
        return current

    for row in rows:
        a_stat = ensure_model(row.model_a_id, row.model_a_label)
        b_stat = ensure_model(row.model_b_id, row.model_b_label)
        a_stat.appearances += 1
        b_stat.appearances += 1
        if row.vote == "a":
            a_stat.wins += 1
            b_stat.losses += 1
        elif row.vote == "b":
            b_stat.wins += 1
            a_stat.losses += 1
        elif row.vote == "both_good":
            a_stat.both_good += 1
            b_stat.both_good += 1
        elif row.vote == "both_bad":
            a_stat.both_bad += 1
            b_stat.both_bad += 1

    # 中文注释：这里输出的是用户真实投票沉淀，后续可以直接导出做模型偏好评估集。
    return BattlePreferenceSummaryOut(
        voted_rounds=len(rows),
        a_wins=sum(1 for row in rows if row.vote == "a"),
        b_wins=sum(1 for row in rows if row.vote == "b"),
        both_good=sum(1 for row in rows if row.vote == "both_good"),
        both_bad=sum(1 for row in rows if row.vote == "both_bad"),
        model_stats=sorted(stats.values(), key=lambda item: (-item.wins, -item.appearances, item.label)),
    )


def _extract_battle_media_paths(rounds: list[dict[str, object]]) -> list[str]:
    paths: list[str] = []
    for round_item in rounds:
        attachments = round_item.get("attachments", [])
        if not isinstance(attachments, list):
            continue
        for attachment in attachments:
            if not isinstance(attachment, dict):
                continue
            url = str(attachment.get("url", "")).strip()
            if not url.startswith("/media/"):
                continue
            paths.append(url.removeprefix("/media/"))
    return paths


@router.get("/sessions", response_model=list[BattleSessionSummaryOut])
def list_battle_sessions(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user),
):
    sessions = db.scalars(
        select(BattleSession)
        .where(BattleSession.user_id == current_user.id)
        .order_by(desc(BattleSession.updated_at), desc(BattleSession.id))
    ).all()
    return [_battle_session_summary_payload(session) for session in sessions]


def _load_user_battle_sessions(db: Session, user_id: int) -> list[BattleSession]:
    return list(
        db.scalars(
            select(BattleSession)
            .where(BattleSession.user_id == user_id)
            .order_by(desc(BattleSession.updated_at), desc(BattleSession.id))
        ).all()
    )


@router.get("/preferences/summary", response_model=BattlePreferenceSummaryOut)
def get_battle_preference_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user),
):
    rows = _battle_preference_rows(_load_user_battle_sessions(db, current_user.id))
    return _battle_preference_summary(rows)


@router.get("/preferences/dataset", response_model=list[BattlePreferenceDatasetRowOut])
def get_battle_preference_dataset(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user),
):
    return _battle_preference_rows(_load_user_battle_sessions(db, current_user.id))


@router.post("/sessions", response_model=BattleSessionDetailOut)
def create_battle_session(
    payload: BattleSessionCreateIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user),
):
    title = _ensure_battle_title_present(payload.title)
    session = BattleSession(
        user_id=current_user.id,
        title=title,
        rounds_json=json.dumps([item.model_dump(mode="json") for item in payload.rounds], ensure_ascii=False),
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return _battle_session_detail_payload(session)


@router.get("/sessions/{session_id}", response_model=BattleSessionDetailOut)
def get_battle_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user),
):
    session = _load_battle_session_for_user(db=db, session_id=session_id, user_id=current_user.id)
    return _battle_session_detail_payload(session)


@router.put("/sessions/{session_id}", response_model=BattleSessionDetailOut)
def update_battle_session(
    session_id: int,
    payload: BattleSessionUpdateIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user),
):
    session = _load_battle_session_for_user(db=db, session_id=session_id, user_id=current_user.id)
    session.title = _ensure_battle_title_present(payload.title)
    session.rounds_json = json.dumps([item.model_dump(mode="json") for item in payload.rounds], ensure_ascii=False)
    db.add(session)
    db.commit()
    db.refresh(session)
    return _battle_session_detail_payload(session)


@router.patch("/sessions/{session_id}", response_model=BattleSessionSummaryOut)
def rename_battle_session(
    session_id: int,
    payload: BattleSessionRenameIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user),
):
    session = _load_battle_session_for_user(db=db, session_id=session_id, user_id=current_user.id)
    session.title = _ensure_battle_title_present(payload.title)
    db.add(session)
    db.commit()
    db.refresh(session)
    return _battle_session_summary_payload(session)


@router.delete("/sessions/{session_id}", status_code=204)
def delete_battle_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user),
):
    session = _load_battle_session_for_user(db=db, session_id=session_id, user_id=current_user.id)
    remove_media_files(_extract_battle_media_paths(session.rounds))
    db.delete(session)
    db.commit()


async def _prepare_battle_prompt(
    *,
    db: Session,
    payload: BattleStreamRequest,
    request: Request,
    current_user: User,
    uploads: list[UploadFile],
) -> BattlePreparedPrompt:
    content = payload.message.strip()
    _ensure_battle_input_present(content=content, upload_count=len(uploads))
    _ensure_uploads_supported_by_model(model=payload.model, uploads=uploads)
    profile = resolve_model_profile(payload.model)
    if profile is None:
        raise HTTPException(status_code=400, detail="Model is not enabled in catalog.")

    saved_attachments = await persist_uploaded_attachments(uploads)
    _ensure_battle_input_present(content=content, upload_count=len(saved_attachments))

    services = get_chat_services(request)
    conversation = Conversation(user_id=None, title="Battle prompt", model=payload.model)
    db.add(conversation)
    db.flush()
    message = Message(conversation_id=conversation.id, role="user", content=content)
    db.add(message)
    db.flush()
    append_message_attachments(db=db, message=message, attachments=saved_attachments)
    db.commit()
    db.refresh(message)

    try:
        # Battle 不落普通会话，但复用聊天链路的附件解析、RAG 和 Web 上下文构造。
        history_messages = [message]
        history_service = MessageHistoryService(db, services.attachment_context_service)
        prepared_history = await history_service.prepare(model=payload.model, messages=history_messages)
        prepared_retrieval_history = await history_service.prepare_retrieval_history(
            model=payload.model,
            messages=history_messages,
        )
        tool_policy = build_tool_policy(payload.tool_mode, knowledge_folders=payload.knowledge_folders)
        tool_plan = services.tool_runtime.plan_context(
            request=ToolPlanRequest(query=content, tool_policy=tool_policy),
        )
        include_file_context = len(saved_attachments) > 0
        prompt_context = await services.tool_runtime.build_context_payload(
            request=ToolContextBuildRequest(
                db=db,
                user_id=current_user.id,
                query=content,
                plan=tool_plan,
                retrieval_messages=prepared_retrieval_history.messages,
                memory_query_hints=[],
                conversation_messages=history_messages,
                include_file_context=include_file_context,
                include_image_context=profile.native_multimodal_mode == "false",
            ),
        )

        if prompt_context.should_refuse and prompt_context.refusal_message:
            return BattlePreparedPrompt(
                messages=[],
                refusal_message=prompt_context.refusal_message,
                sources=prompt_context.sources,
            )

        history_payloads = [
            ChatMessagePayload(role=m["role"], content=m["content"])
            for m in payload.history
        ]
        messages = [
            *([prompt_context.context_message] if prompt_context.context_message else []),
            *history_payloads,
            *prepared_history.messages,
        ]
        attachments = [
            {
                "id": f"battle-{attachment.relative_path.replace('/', '-')}"
                if attachment.relative_path
                else f"battle-{hash(attachment.original_name)}",
                "kind": attachment.kind,
                "original_name": attachment.original_name,
                "mime_type": attachment.mime_type,
                "size_bytes": attachment.size_bytes,
                "extension": attachment.extension,
                "url": media_url(attachment.relative_path),
            }
            for attachment in saved_attachments
        ]
        return BattlePreparedPrompt(messages=messages, sources=prompt_context.sources, attachments=attachments)
    finally:
        db.delete(conversation)
        db.commit()


async def _battle_event_stream(payload: BattleStreamRequest, prepared: BattlePreparedPrompt) -> AsyncIterator[str]:
    content_parts: list[str] = []
    yield _ndjson({"type": "meta", "model": payload.model})
    if prepared.attachments:
        yield _ndjson({"type": "attachments", "attachments": prepared.attachments})
    if prepared.sources:
        yield _ndjson({"type": "sources", "sources": prepared.sources})

    if prepared.refusal_message:
        yield _ndjson({"type": "token", "content": prepared.refusal_message})
        yield _ndjson({"type": "done", "content": prepared.refusal_message})
        return

    try:
        # Battle 模式不写入普通会话，只把同一个问题发给指定模型做匿名对比。
        async for chunk in stream_model_response(
            model=payload.model,
            messages=prepared.messages,
            requested_reasoning_profile=payload.reasoning_profile,
        ):
            if chunk.reasoning_delta:
                yield _ndjson({"type": "reasoning", "content": chunk.reasoning_delta})
            if chunk.output_text_delta:
                content_parts.append(chunk.output_text_delta)
                yield _ndjson({"type": "token", "content": chunk.output_text_delta})
            if chunk.done:
                yield _ndjson({"type": "done", "content": "".join(content_parts).strip()})
                return
    except Exception as exc:
        yield _ndjson({"type": "error", "message": str(exc)})


@router.post("/stream")
async def battle_stream(
    request: Request,
    message: str = Form(""),
    model: str = Form(...),
    tool_mode: ToolMode = Form("none"),
    knowledge_folders: Optional[list[str]] = Form(None),
    reasoning_profile: Optional[ReasoningProfileValue] = Form(None),
    history: Optional[str] = Form(None),
    files: Optional[list[UploadFile]] = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user),
):
    parsed_history = json.loads(history) if history else []
    payload = BattleStreamRequest(
        message=message,
        model=model,
        tool_mode=tool_mode,
        knowledge_folders=knowledge_folders or [],
        reasoning_profile=reasoning_profile,
        history=parsed_history,
    )
    prepared = await _prepare_battle_prompt(
        db=db,
        payload=payload,
        request=request,
        current_user=current_user,
        uploads=files or [],
    )

    return StreamingResponse(
        _battle_event_stream(payload, prepared),
        media_type="application/x-ndjson; charset=utf-8",
        headers={"Cache-Control": "no-store"},
    )
