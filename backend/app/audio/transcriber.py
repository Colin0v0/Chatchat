from __future__ import annotations

import io
import wave
import gc

from ..core.idle_runtime import IdleRuntime
from ..schemas import AudioTranscriptionOut
from .ffmpeg import transcode_audio_to_wav


class AudioModelLoadError(RuntimeError):
    pass


class AudioTranscriber:
    def __init__(
        self,
        *,
        model_name: str,
        device: str,
        compute_type: str,
        vad_filter: bool,
        idle_timeout_seconds: float,
    ):
        self._model_name = model_name
        self._device = device
        self._compute_type = compute_type
        self._vad_filter = vad_filter
        self._runtime = IdleRuntime(
            runtime_name="audio.whisper",
            loader=lambda: self._load_model(
                model_name=self._model_name,
                device=self._device,
                compute_type=self._compute_type,
            ),
            unloader=self._unload_model,
            idle_timeout_seconds=idle_timeout_seconds,
        )

    @property
    def requires_local_gpu(self) -> bool:
        return self._device.startswith("cuda")

    def transcribe(self, audio_bytes: bytes) -> AudioTranscriptionOut:
        wav_bytes = transcode_audio_to_wav(audio_bytes)
        with self._runtime.lease() as model:
            segments, info = model.transcribe(
                io.BytesIO(wav_bytes),
                vad_filter=self._vad_filter,
            )
        text = self._decode_segments(segments)
        return AudioTranscriptionOut(
            text=text,
            language=self._normalize_language(info.language),
            duration_ms=self._wav_duration_ms(wav_bytes),
        )

    def _load_model(self, *, model_name: str, device: str, compute_type: str):
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise RuntimeError(
                "faster-whisper is required for audio transcription. Install backend dependencies first."
            ) from exc

        try:
            return WhisperModel(model_name, device=device, compute_type=compute_type)
        except Exception as exc:
            raise AudioModelLoadError(
                "Failed to load speech model. Ensure model files are available locally or enable Hugging Face access."
            ) from exc

    def _unload_model(self, model) -> None:
        del model
        gc.collect()

    def _decode_segments(self, segments) -> str:
        parts: list[str] = []
        for segment in segments:
            content = getattr(segment, "text", "").strip()
            if content:
                parts.append(content)
        return " ".join(parts).strip()

    def _normalize_language(self, language: str | None) -> str:
        if not language:
            return "unknown"
        return language.strip().lower() or "unknown"

    def _wav_duration_ms(self, wav_bytes: bytes) -> int:
        with wave.open(io.BytesIO(wav_bytes), "rb") as wav_file:
            sample_rate = wav_file.getframerate()
            frame_count = wav_file.getnframes()
        if sample_rate <= 0:
            return 0
        return int((frame_count / sample_rate) * 1000)
