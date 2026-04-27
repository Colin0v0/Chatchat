from __future__ import annotations

from dataclasses import dataclass

from fastapi import Request

from ..core.config import Settings
from .synthesizer import DashScopeSpeechSynthesizer
from .transcriber import AudioTranscriber, OpenAICompatibleAudioTranscriber


@dataclass(frozen=True)
class AudioServices:
    transcriber: AudioTranscriber
    synthesizer: DashScopeSpeechSynthesizer


def build_audio_services(settings: Settings) -> AudioServices:
    synthesizer = DashScopeSpeechSynthesizer(
        model_name=settings.audio_tts_model,
        base_url=settings.audio_tts_base_url,
        api_key=settings.audio_tts_api_key.strip() or settings.dashscope_api_key,
        enabled=settings.audio_tts_enabled,
        voice=settings.audio_tts_voice,
        audio_format=settings.audio_tts_format,
        sample_rate=settings.audio_tts_sample_rate,
        timeout_seconds=settings.audio_tts_timeout_seconds,
        max_chars=settings.audio_tts_max_chars,
    )
    return AudioServices(
        transcriber=OpenAICompatibleAudioTranscriber(
            model_name=settings.audio_transcription_model,
            base_url=settings.audio_transcription_base_url.strip() or settings.dashscope_base_url,
            api_key=settings.audio_transcription_api_key.strip() or settings.dashscope_api_key,
            enabled=settings.audio_transcription_enabled,
            language=settings.audio_transcription_language,
            timeout_seconds=settings.audio_transcription_timeout_seconds,
            max_request_bytes=settings.audio_transcription_api_max_bytes,
            min_duration_ms=settings.audio_transcription_min_duration_ms,
            min_rms_dbfs=settings.audio_transcription_min_rms_dbfs,
        ),
        synthesizer=synthesizer,
    )


def get_audio_services(request: Request) -> AudioServices:
    return request.app.state.audio_services
