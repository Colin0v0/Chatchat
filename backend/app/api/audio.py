from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile

from ..auth import require_current_user
from ..audio import AudioModelLoadError, get_audio_services
from ..core.config import settings
from ..schemas import AudioTranscriptionOut

router = APIRouter(prefix="/api/audio", tags=["audio"])
logger = logging.getLogger("chatchat.audio")


@router.post("/transcribe", response_model=AudioTranscriptionOut)
async def transcribe_audio(
    request: Request,
    file: UploadFile = File(...),
    _=Depends(require_current_user),
) -> AudioTranscriptionOut:
    services = get_audio_services(request)
    payload = await file.read()
    await file.close()
    logger.info(
        "audio upload received | filename=%s | content_type=%s | bytes=%s",
        file.filename,
        file.content_type,
        len(payload),
    )
    if not payload:
        raise HTTPException(status_code=400, detail="Audio file is empty.")
    if len(payload) > settings.audio_max_upload_size_bytes:
        raise HTTPException(status_code=400, detail="Audio file is too large.")

    try:
        return services.transcriber.transcribe(payload)
    except AudioModelLoadError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
