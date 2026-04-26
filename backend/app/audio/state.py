from __future__ import annotations

from dataclasses import dataclass

from fastapi import Request

from ..core.config import Settings
from .transcriber import AudioTranscriber


@dataclass(frozen=True)
class AudioServices:
    transcriber: AudioTranscriber


def build_audio_services(settings: Settings) -> AudioServices:
    return AudioServices(
        transcriber=AudioTranscriber(
            model_name=settings.audio_transcription_model,
            device=settings.audio_transcription_device,
            enabled=settings.audio_transcription_enabled,
            language=settings.audio_transcription_language,
            vad_model=settings.audio_transcription_vad_model,
            min_duration_ms=settings.audio_transcription_min_duration_ms,
            min_rms_dbfs=settings.audio_transcription_min_rms_dbfs,
            allowed_languages=settings.audio_transcription_allowed_languages,
        ),
    )


def get_audio_services(request: Request) -> AudioServices:
    return request.app.state.audio_services
