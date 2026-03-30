from __future__ import annotations

from dataclasses import dataclass
from threading import Lock

from fastapi import Request

from ..core.config import Settings
from .transcriber import AudioTranscriber


@dataclass(frozen=True)
class AudioServices:
    transcriber: AudioTranscriber
    local_gpu_lock: Lock


def build_audio_services(settings: Settings, *, local_gpu_lock: Lock) -> AudioServices:
    return AudioServices(
        transcriber=AudioTranscriber(
            model_name=settings.audio_transcription_model,
            device=settings.audio_transcription_device,
            compute_type=settings.audio_transcription_compute_type,
            vad_filter=settings.audio_transcription_vad_filter,
            idle_timeout_seconds=settings.local_model_idle_timeout_seconds,
        ),
        local_gpu_lock=local_gpu_lock,
    )


def get_audio_services(request: Request) -> AudioServices:
    return request.app.state.audio_services
