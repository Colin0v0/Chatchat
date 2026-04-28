from __future__ import annotations

import json
import asyncio
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..application.chat_turns import resolve_chat_model
from ..auth import require_current_user
from ..chat.context import append_message_attachments, conversation_title
from ..core.config import settings
from ..provider_transports.openai_images import generate_openai_image
from ..runtime.streaming import ndjson_stream_response
from ..schemas import ImageGenerateRequest, ImageGenerationJobOut
from ..storage.access import get_user_conversation
from ..storage.database import SessionLocal, get_db
from ..storage.media import (
    media_url,
    persist_generated_image,
    persist_generated_image_bytes,
    remove_media_files,
)
from ..storage.models import Conversation, ImageGenerationJob, Message, User

router = APIRouter(prefix="/api/images", tags=["images"])
logger = logging.getLogger("chatchat.images")


@dataclass(frozen=True)
class PersistedImageGenerationTurn:
    conversation: Conversation
    user_message: Message


def _ndjson_event(payload: dict[str, object]) -> str:
    return json.dumps(payload, ensure_ascii=False) + "\n"


def _job_out(*, db: Session, job: ImageGenerationJob) -> ImageGenerationJobOut:
    conversation = db.get(Conversation, job.conversation_id)
    assistant_message = (
        db.get(Message, job.assistant_message_id)
        if job.assistant_message_id is not None
        else None
    )
    return ImageGenerationJobOut(
        job_id=job.id,
        status=job.status,
        conversation_id=job.conversation_id,
        user_message_id=job.user_message_id,
        assistant_message_id=job.assistant_message_id,
        conversation_title=conversation.title if conversation is not None else "",
        content=assistant_message.content if assistant_message is not None else "",
        error_message=job.error_message,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
    )


def _image_error_message(error: Exception) -> str:
    if isinstance(error, httpx.HTTPStatusError):
        try:
            payload = error.response.json()
        except ValueError:
            payload = None
        if isinstance(payload, dict):
            upstream_error = payload.get("error")
            if isinstance(upstream_error, dict) and isinstance(upstream_error.get("message"), str):
                return upstream_error["message"]
            if isinstance(payload.get("message"), str):
                return payload["message"]
            if isinstance(payload.get("detail"), str):
                return payload["detail"]
        if error.response.status_code == 524:
            return "Image generation timed out upstream: HTTP 524"
        return f"Image generation failed: HTTP {error.response.status_code}"
    if isinstance(error, ValueError):
        return str(error)
    if isinstance(error, RuntimeError):
        return str(error)
    return f"Image generation failed: {error}" if str(error) else "Image generation failed."


async def _download_generated_image(url: str) -> bytes:
    normalized_url = url.strip()
    if not normalized_url:
        raise RuntimeError("Image generation returned an empty image URL.")
    try:
        async with httpx.AsyncClient(timeout=settings.openai_image_timeout_seconds) as client:
            response = await client.get(normalized_url)
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise RuntimeError(f"Failed to download generated image: HTTP {exc.response.status_code}") from exc
    except httpx.HTTPError as exc:
        raise RuntimeError(f"Failed to download generated image: {exc}") from exc
    return response.content


def _persist_image_generation_turn(
    *,
    db: Session,
    current_user: User,
    payload: ImageGenerateRequest,
) -> PersistedImageGenerationTurn:
    prompt = payload.prompt.strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="Image prompt is required.")

    conversation = None
    if payload.conversation_id is not None:
        conversation = get_user_conversation(
            db,
            conversation_id=payload.conversation_id,
            user_id=current_user.id,
        )
        if conversation is None:
            raise HTTPException(status_code=404, detail="Conversation not found")

    profile = resolve_chat_model(
        requested_model=conversation.model if conversation else settings.default_model,
        fallback_model=settings.default_model,
    )

    if conversation is None:
        conversation = Conversation(
            user_id=current_user.id,
            title=conversation_title(prompt, 0),
            model=profile.id,
        )
        db.add(conversation)
        db.flush()
    elif conversation.model != profile.id:
        conversation.model = profile.id

    user_message = Message(
        conversation_id=conversation.id,
        role="user",
        content=prompt,
        response_mode="image",
    )
    conversation.updated_at = datetime.utcnow()
    db.add(user_message)
    db.add(conversation)
    db.commit()
    db.refresh(user_message)
    db.refresh(conversation)
    return PersistedImageGenerationTurn(conversation=conversation, user_message=user_message)


def _persist_image_generation_job(
    *,
    db: Session,
    current_user: User,
    turn: PersistedImageGenerationTurn,
    payload: ImageGenerateRequest,
) -> ImageGenerationJob:
    job = ImageGenerationJob(
        user_id=current_user.id,
        conversation_id=turn.conversation.id,
        user_message_id=turn.user_message.id,
        status="queued",
        prompt=payload.prompt.strip(),
        size=payload.size,
        quality=payload.quality,
        output_format=payload.output_format,
        model=settings.openai_image_model.strip(),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def _persist_generated_image_message(
    *,
    db: Session,
    conversation: Conversation,
    prompt: str,
    b64_json: str,
    output_format: str,
    target_size: str | None,
) -> Message:
    stored_attachment = persist_generated_image(
        b64_json=b64_json,
        output_format=output_format,
        original_name="generated-image",
        target_size=target_size,
    )
    try:
        image_url = media_url(stored_attachment.relative_path)
        assistant_content = f"已生成图片：\n\n![Generated image]({image_url})"
        assistant_message = Message(
            conversation_id=conversation.id,
            role="assistant",
            content=assistant_content,
            image_context=prompt,
            response_mode="image",
        )
        conversation.updated_at = datetime.utcnow()
        db.add(assistant_message)
        db.flush()
        append_message_attachments(
            db=db,
            message=assistant_message,
            attachments=[stored_attachment],
        )
        db.add(conversation)
        db.commit()
        db.refresh(assistant_message)
        return assistant_message
    except Exception:
        db.rollback()
        remove_media_files([stored_attachment.relative_path])
        raise


async def _persist_generated_image_response(
    *,
    db: Session,
    conversation: Conversation,
    prompt: str,
    b64_json: str,
    image_url: str,
    output_format: str,
    target_size: str | None,
) -> Message:
    if b64_json:
        return _persist_generated_image_message(
            db=db,
            conversation=conversation,
            prompt=prompt,
            b64_json=b64_json,
            output_format=output_format,
            target_size=target_size,
        )

    content = await _download_generated_image(image_url)
    stored_attachment = persist_generated_image_bytes(
        content=content,
        output_format=output_format,
        original_name="generated-image",
        target_size=target_size,
    )
    try:
        saved_image_url = media_url(stored_attachment.relative_path)
        assistant_content = f"已生成图片：\n\n![Generated image]({saved_image_url})"
        assistant_message = Message(
            conversation_id=conversation.id,
            role="assistant",
            content=assistant_content,
            image_context=prompt,
            response_mode="image",
        )
        conversation.updated_at = datetime.utcnow()
        db.add(assistant_message)
        db.flush()
        append_message_attachments(
            db=db,
            message=assistant_message,
            attachments=[stored_attachment],
        )
        db.add(conversation)
        db.commit()
        db.refresh(assistant_message)
        return assistant_message
    except Exception:
        db.rollback()
        remove_media_files([stored_attachment.relative_path])
        raise


async def _stream_image_generation(
    *,
    db: Session,
    turn: PersistedImageGenerationTurn,
    payload: ImageGenerateRequest,
) -> AsyncIterator[str]:
    yield _ndjson_event(
        {
            "type": "meta",
            "conversation_id": turn.conversation.id,
            "message_id": turn.user_message.id,
            "model": turn.conversation.model,
        }
    )
    yield _ndjson_event({"type": "status", "items": ["Generating image"]})

    try:
        generated = await generate_openai_image(
            prompt=payload.prompt,
            size=payload.size,
            quality=payload.quality,
            output_format=payload.output_format,
        )
        assistant_message = await _persist_generated_image_response(
            db=db,
            conversation=turn.conversation,
            prompt=payload.prompt.strip(),
            b64_json=generated.b64_json,
            image_url=generated.url,
            output_format=generated.output_format,
            target_size=None,
        )
    except Exception as exc:
        yield _ndjson_event({"type": "error", "message": _image_error_message(exc)})
        return

    yield _ndjson_event(
        {
            "type": "done",
            "assistant_message_id": assistant_message.id,
            "conversation_title": turn.conversation.title,
            "content": assistant_message.content,
        }
    )


async def _execute_image_generation_job(job_id: int) -> None:
    db = SessionLocal()
    try:
        job = db.get(ImageGenerationJob, job_id)
        if job is None:
            return

        job.status = "running"
        job.started_at = datetime.utcnow()
        job.updated_at = datetime.utcnow()
        db.add(job)
        db.commit()

        try:
            generated = await generate_openai_image(
                prompt=job.prompt,
                size=job.size,
                quality=job.quality,
                output_format=job.output_format,
            )
            conversation = db.get(Conversation, job.conversation_id)
            if conversation is None:
                raise RuntimeError("Conversation not found for image generation job.")
            assistant_message = await _persist_generated_image_response(
                db=db,
                conversation=conversation,
                prompt=job.prompt,
                b64_json=generated.b64_json,
                image_url=generated.url,
                output_format=generated.output_format,
                target_size=None,
            )
            job = db.get(ImageGenerationJob, job_id)
            if job is None:
                return
            job.status = "succeeded"
            job.assistant_message_id = assistant_message.id
            job.error_message = None
            job.finished_at = datetime.utcnow()
            job.updated_at = datetime.utcnow()
            db.add(job)
            db.commit()
        except Exception as exc:
            logger.exception("image generation job failed | job_id=%s", job_id)
            db.rollback()
            job = db.get(ImageGenerationJob, job_id)
            if job is None:
                return
            job.status = "failed"
            job.error_message = _image_error_message(exc)
            job.finished_at = datetime.utcnow()
            job.updated_at = datetime.utcnow()
            db.add(job)
            db.commit()
    finally:
        db.close()


def _start_image_generation_task(job_id: int) -> None:
    # 图片任务在后台跑，前端通过短轮询读取状态，避免长连接被代理层切断。
    asyncio.create_task(_execute_image_generation_job(job_id), name=f"image-generation-job-{job_id}")


@router.post("/jobs", response_model=ImageGenerationJobOut)
async def create_image_generation_job(
    payload: ImageGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user),
):
    turn = _persist_image_generation_turn(
        db=db,
        current_user=current_user,
        payload=payload,
    )
    job = _persist_image_generation_job(
        db=db,
        current_user=current_user,
        turn=turn,
        payload=payload,
    )
    _start_image_generation_task(job.id)
    return _job_out(db=db, job=job)


@router.get("/jobs/{job_id}", response_model=ImageGenerationJobOut)
def get_image_generation_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user),
):
    job = db.get(ImageGenerationJob, job_id)
    if job is None or job.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Image generation job not found")
    return _job_out(db=db, job=job)


@router.post("/generate")
async def generate_image(
    payload: ImageGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user),
):
    turn = _persist_image_generation_turn(
        db=db,
        current_user=current_user,
        payload=payload,
    )
    return ndjson_stream_response(
        _stream_image_generation(
            db=db,
            turn=turn,
            payload=payload,
        )
    )
