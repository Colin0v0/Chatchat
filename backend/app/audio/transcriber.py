from __future__ import annotations

import gc
import io
import os
import tempfile
import wave
from threading import Lock
from typing import Any, Callable

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
        enabled: bool,
    ):
        self._model_name = model_name
        self._device = device
        self._enabled = enabled
        self._lock = Lock()
        self._model: Any | None = None
        self._postprocess: Callable[[str], str] | None = None

    @property
    def requires_local_gpu(self) -> bool:
        return self._device.startswith("cuda")

    @property
    def is_enabled(self) -> bool:
        return self._enabled

    def load(self) -> None:
        if not self._enabled:
            return
        with self._lock:
            if self._model is not None and self._postprocess is not None:
                return
            self._model, self._postprocess = self._load_model(
                model_name=self._model_name,
                device=self._device,
            )

    def unload(self) -> None:
        with self._lock:
            if self._model is None:
                return
            self._model = None
            self._postprocess = None
        gc.collect()

    def transcribe(self, audio_bytes: bytes) -> AudioTranscriptionOut:
        if not self._enabled:
            raise AudioModelLoadError(
                "Audio transcription is disabled in the current environment."
            )
        self.load()
        wav_bytes = transcode_audio_to_wav(audio_bytes)
        text = self._transcribe_wav(wav_bytes)
        return AudioTranscriptionOut(
            text=text,
            language="auto",
            duration_ms=self._wav_duration_ms(wav_bytes),
        )

    def _transcribe_wav(self, wav_bytes: bytes) -> str:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
            temp_file.write(wav_bytes)
            temp_path = temp_file.name

        try:
            result = self._require_model().generate(
                input=temp_path,
                cache={},
                language="auto",
                use_itn=True,
                batch_size=1,
            )
        except Exception as exc:
            raise RuntimeError(f"SenseVoice transcription failed: {exc}") from exc
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

        if not isinstance(result, list) or not result:
            raise RuntimeError("SenseVoice returned an empty response.")

        raw_text = str(result[0].get("text", "")).strip()
        if not raw_text:
            return ""

        return self._require_postprocess()(raw_text).strip()

    def _require_model(self) -> Any:
        if self._model is None:
            raise RuntimeError("SenseVoice is not loaded.")
        return self._model

    def _require_postprocess(self) -> Callable[[str], str]:
        if self._postprocess is None:
            raise RuntimeError("SenseVoice postprocessor is not loaded.")
        return self._postprocess

    def _load_model(self, *, model_name: str, device: str) -> tuple[Any, Callable[[str], str]]:
        try:
            from funasr import AutoModel
            from funasr.utils.postprocess_utils import rich_transcription_postprocess
        except ImportError as exc:
            raise RuntimeError(
                "funasr is required for audio transcription. Install backend dependencies first."
            ) from exc

        try:
            model = AutoModel(
                model=model_name,
                disable_update=True,
                device=device,
                trust_remote_code=False,
            )
        except Exception as exc:
            raise AudioModelLoadError(
                "Failed to load SenseVoice-Small. Ensure the model path is valid or the server can download it."
            ) from exc

        return model, rich_transcription_postprocess

    def _wav_duration_ms(self, wav_bytes: bytes) -> int:
        with wave.open(io.BytesIO(wav_bytes), "rb") as wav_file:
            sample_rate = wav_file.getframerate()
            channel_count = wav_file.getnchannels()
            sample_width = wav_file.getsampwidth()
            pcm_bytes = wav_file.readframes(wav_file.getnframes())
        if sample_rate <= 0:
            return 0
        bytes_per_frame = channel_count * sample_width
        if bytes_per_frame <= 0:
            return 0
        frame_count = len(pcm_bytes) / bytes_per_frame
        return int((frame_count / sample_rate) * 1000)
