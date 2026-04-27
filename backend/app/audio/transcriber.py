from __future__ import annotations

import base64
import gc
import io
import logging
import math
import os
import re
import tempfile
import wave
from array import array
from contextlib import contextmanager
from dataclasses import dataclass
from threading import Lock
from typing import Any, Callable, Iterator

import httpx

from ..schemas import AudioTranscriptionOut
from .ffmpeg import transcode_audio_to_wav


class AudioModelLoadError(RuntimeError):
    pass


logger = logging.getLogger("chatchat.audio")

LANGUAGE_TAG_PATTERN = re.compile(r"<\|(zh|en|yue|ja|ko|nospeech)\|>", re.IGNORECASE)
MEANINGFUL_TRANSCRIPT_PATTERN = re.compile(r"[\u3400-\u9fffA-Za-z0-9]")
UNWANTED_SHORT_SCRIPT_PATTERN = re.compile(r"[\u3040-\u30ff\uac00-\ud7af]")
SUPPORTED_SENSEVOICE_LANGUAGES = {"auto", "zh", "en", "yue", "ja", "ko", "nospeech"}


@dataclass(frozen=True)
class AudioGateDecision:
    skip: bool
    reason: str | None
    rms_dbfs: float


def _normalize_language(value: str) -> str:
    normalized = value.strip().lower()
    if normalized == "cn":
        return "zh"
    if normalized not in SUPPORTED_SENSEVOICE_LANGUAGES:
        return "zh"
    return normalized


def _parse_allowed_languages(value: str) -> set[str]:
    allowed = {_normalize_language(item) for item in value.split(",") if item.strip()}
    allowed.discard("auto")
    return allowed or {"zh", "en"}


class AudioTranscriber:
    def __init__(
        self,
        *,
        model_name: str,
        device: str,
        enabled: bool,
        language: str = "zh",
        vad_model: str = "fsmn-vad",
        min_duration_ms: int = 650,
        min_rms_dbfs: float = -65.0,
        allowed_languages: str = "zh,en",
    ):
        self._model_name = model_name
        self._device = device
        self._enabled = enabled
        self._language = _normalize_language(language)
        self._vad_model = vad_model.strip()
        self._min_duration_ms = max(0, min_duration_ms)
        self._min_rms_dbfs = min_rms_dbfs
        self._allowed_languages = _parse_allowed_languages(allowed_languages)
        self._lock = Lock()
        self._model: Any | None = None
        self._postprocess: Callable[[str], str] | None = None
        self._vad_enabled = False

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
        wav_bytes = transcode_audio_to_wav(audio_bytes)
        duration_ms = self._wav_duration_ms(wav_bytes)
        gate = self._inspect_audio(wav_bytes, duration_ms=duration_ms)
        logger.info(
            "audio transcribe input | bytes=%s | wav_bytes=%s | duration_ms=%s | rms_dbfs=%.1f | language=%s | vad=%s",
            len(audio_bytes),
            len(wav_bytes),
            duration_ms,
            gate.rms_dbfs,
            self._language,
            self._vad_enabled,
        )
        if gate.skip:
            logger.info(
                "audio transcribe skipped | reason=%s | duration_ms=%s | rms_dbfs=%.1f | min_duration_ms=%s | min_rms_dbfs=%.1f",
                gate.reason,
                duration_ms,
                gate.rms_dbfs,
                self._min_duration_ms,
                self._min_rms_dbfs,
            )
            return AudioTranscriptionOut(
                text="",
                language=self._language,
                duration_ms=duration_ms,
                reason=gate.reason,
            )

        self.load()
        text = self._transcribe_wav(wav_bytes)
        if not text:
            logger.info(
                "audio transcribe empty | duration_ms=%s | rms_dbfs=%.1f",
                duration_ms,
                gate.rms_dbfs,
            )
        else:
            logger.info(
                "audio transcribe success | duration_ms=%s | rms_dbfs=%.1f | text_len=%s",
                duration_ms,
                gate.rms_dbfs,
                len(text),
            )
        return AudioTranscriptionOut(
            text=text,
            language=self._language,
            duration_ms=duration_ms,
            reason=None if text else "empty_transcript",
        )

    @contextmanager
    def _suppress_third_party_info_logs(self) -> Iterator[None]:
        targets = (
            logging.getLogger(),
            logging.getLogger("funasr"),
            logging.getLogger("modelscope"),
        )
        original_levels: list[tuple[logging.Logger, int]] = []
        for logger in targets:
            if logger.getEffectiveLevel() < logging.WARNING:
                original_levels.append((logger, logger.level))
                logger.setLevel(logging.WARNING)
        try:
            yield
        finally:
            for logger, level in reversed(original_levels):
                logger.setLevel(level)

    def _transcribe_wav(self, wav_bytes: bytes) -> str:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
            temp_file.write(wav_bytes)
            temp_path = temp_file.name

        try:
            result = self._generate_from_path(temp_path, use_vad=True)
            raw_text = self._extract_result_text(result)
            if not raw_text and self._vad_enabled:
                logger.info("audio transcribe model empty | reason=empty_raw_result | retry=without_vad")
                result = self._generate_from_path(temp_path, use_vad=False)
                raw_text = self._extract_result_text(result)
        except Exception as exc:
            raise RuntimeError(f"SenseVoice transcription failed: {exc}") from exc
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

        if not raw_text:
            logger.info("audio transcribe model empty | reason=empty_raw_result")
            return ""
        raw_language = self._extract_raw_language(raw_text)
        if self._should_drop_raw_result(raw_text):
            logger.info(
                "audio transcribe model dropped | reason=language_filter | raw_language=%s | raw_len=%s",
                raw_language,
                len(raw_text),
            )
            return ""

        text = self._require_postprocess()(raw_text).strip()
        if self._is_low_confidence_transcript(text):
            logger.info(
                "audio transcribe model dropped | reason=low_confidence | raw_language=%s | raw_len=%s | text_len=%s",
                raw_language,
                len(raw_text),
                len(text),
            )
            return ""
        logger.info(
            "audio transcribe model accepted | raw_language=%s | raw_len=%s | text_len=%s",
            raw_language,
            len(raw_text),
            len(text),
        )
        return text

    def _generate_from_path(self, temp_path: str, *, use_vad: bool) -> Any:
        with self._lock:
            model = self._require_model()
            if use_vad or not self._vad_enabled:
                with self._suppress_third_party_info_logs():
                    return model.generate(
                        input=temp_path,
                        cache={},
                        language=self._language,
                        use_itn=True,
                        **self._generate_options(use_vad=use_vad),
                    )

            original_vad_model = getattr(model, "vad_model", None)
            try:
                setattr(model, "vad_model", None)
                with self._suppress_third_party_info_logs():
                    return model.generate(
                        input=temp_path,
                        cache={},
                        language=self._language,
                        use_itn=True,
                        **self._generate_options(use_vad=False),
                    )
            finally:
                setattr(model, "vad_model", original_vad_model)

    def _extract_result_text(self, result: Any) -> str:
        if not isinstance(result, list) or not result:
            raise RuntimeError("SenseVoice returned an empty response.")
        first_result = result[0]
        if not isinstance(first_result, dict):
            return ""
        return str(first_result.get("text", "")).strip()

    def _generate_options(self, *, use_vad: bool) -> dict[str, object]:
        if self._vad_enabled and use_vad:
            return {
                "batch_size_s": 60,
                "merge_vad": True,
                "merge_length_s": 15,
            }
        return {"batch_size": 1}

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
            with self._suppress_third_party_info_logs():
                from funasr import AutoModel
                from funasr.utils.postprocess_utils import rich_transcription_postprocess
        except ImportError as exc:
            raise RuntimeError(
                "funasr is required for audio transcription. Install backend dependencies first."
            ) from exc

        model_kwargs: dict[str, object] = {
            "model": model_name,
            "disable_update": True,
            "device": device,
            "trust_remote_code": False,
        }
        if self._vad_model:
            model_kwargs.update(
                {
                    "vad_model": self._vad_model,
                    "vad_kwargs": {"max_single_segment_time": 30000},
                }
            )

        try:
            with self._suppress_third_party_info_logs():
                model = AutoModel(**model_kwargs)
                self._vad_enabled = bool(self._vad_model)
        except Exception as exc:
            if not self._vad_model:
                raise AudioModelLoadError(
                    "Failed to load SenseVoice-Small. Ensure the model path is valid or the server can download it."
                ) from exc

            logger.warning(
                "failed to load SenseVoice with VAD, retrying without VAD | vad_model=%s",
                self._vad_model,
            )
            try:
                model_kwargs.pop("vad_model", None)
                model_kwargs.pop("vad_kwargs", None)
                with self._suppress_third_party_info_logs():
                    model = AutoModel(**model_kwargs)
                    self._vad_enabled = False
            except Exception as fallback_exc:
                raise AudioModelLoadError(
                    "Failed to load SenseVoice-Small. Ensure the model path is valid or the server can download it."
                ) from fallback_exc

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

    def _should_skip_audio(self, wav_bytes: bytes, *, duration_ms: int) -> bool:
        return self._inspect_audio(wav_bytes, duration_ms=duration_ms).skip

    def _inspect_audio(self, wav_bytes: bytes, *, duration_ms: int) -> AudioGateDecision:
        if duration_ms <= 0:
            return AudioGateDecision(skip=True, reason="empty_audio", rms_dbfs=float("-inf"))
        rms_dbfs = self._wav_rms_dbfs(wav_bytes)
        if duration_ms < self._min_duration_ms:
            return AudioGateDecision(skip=True, reason="too_short", rms_dbfs=rms_dbfs)
        if rms_dbfs < self._min_rms_dbfs:
            return AudioGateDecision(skip=True, reason="too_quiet", rms_dbfs=rms_dbfs)
        return AudioGateDecision(skip=False, reason=None, rms_dbfs=rms_dbfs)

    def _wav_rms_dbfs(self, wav_bytes: bytes) -> float:
        with wave.open(io.BytesIO(wav_bytes), "rb") as wav_file:
            sample_width = wav_file.getsampwidth()
            pcm_bytes = wav_file.readframes(wav_file.getnframes())
        if not pcm_bytes or sample_width <= 0:
            return float("-inf")

        samples: list[int]
        if sample_width == 2:
            values = array("h")
            values.frombytes(pcm_bytes)
            samples = list(values)
            max_amplitude = float(1 << 15)
        else:
            max_amplitude = float(1 << (sample_width * 8 - 1))
            samples = [
                int.from_bytes(
                    pcm_bytes[index:index + sample_width],
                    byteorder="little",
                    signed=sample_width > 1,
                )
                for index in range(0, len(pcm_bytes), sample_width)
                if len(pcm_bytes[index:index + sample_width]) == sample_width
            ]
            if sample_width == 1:
                samples = [sample - 128 for sample in samples]

        if not samples or max_amplitude <= 0:
            return float("-inf")

        rms = math.sqrt(sum(sample * sample for sample in samples) / len(samples))
        if rms <= 0:
            return float("-inf")
        return 20 * math.log10(rms / max_amplitude)

    def _should_drop_raw_result(self, raw_text: str) -> bool:
        match = LANGUAGE_TAG_PATTERN.search(raw_text)
        if match is None:
            return False
        language = _normalize_language(match.group(1))
        return language == "nospeech" or language not in self._allowed_languages

    def _extract_raw_language(self, raw_text: str) -> str:
        match = LANGUAGE_TAG_PATTERN.search(raw_text)
        if match is None:
            return "unknown"
        return _normalize_language(match.group(1))

    def _is_low_confidence_transcript(self, text: str) -> bool:
        compact_text = text.strip().replace(" ", "")
        if not compact_text:
            return True
        if len(compact_text) <= 3 and not MEANINGFUL_TRANSCRIPT_PATTERN.search(compact_text):
            return True
        return len(compact_text) <= 4 and bool(UNWANTED_SHORT_SCRIPT_PATTERN.search(compact_text))


class OpenAICompatibleAudioTranscriber(AudioTranscriber):
    def __init__(
        self,
        *,
        model_name: str,
        base_url: str,
        api_key: str,
        enabled: bool,
        language: str = "zh",
        timeout_seconds: float = 60.0,
        max_request_bytes: int = 10 * 1024 * 1024,
        min_duration_ms: int = 650,
        min_rms_dbfs: float = -65.0,
        allowed_languages: str = "zh,en",
    ):
        super().__init__(
            model_name=model_name,
            device="api",
            enabled=enabled,
            language=language,
            vad_model="",
            min_duration_ms=min_duration_ms,
            min_rms_dbfs=min_rms_dbfs,
            allowed_languages=allowed_languages,
        )
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key.strip()
        self._timeout_seconds = max(1.0, timeout_seconds)
        self._max_request_bytes = max(1, max_request_bytes)

    @property
    def requires_local_gpu(self) -> bool:
        return False

    def load(self) -> None:
        if not self._enabled:
            return
        if not self._base_url:
            raise AudioModelLoadError("Audio transcription API base URL is not configured.")
        if not self._api_key:
            raise AudioModelLoadError("Audio transcription API key is not configured.")

    def unload(self) -> None:
        return

    def _transcribe_wav(self, wav_bytes: bytes) -> str:
        self.load()
        data_url = self._wav_data_url(wav_bytes)
        if len(data_url.encode("utf-8")) > self._max_request_bytes:
            raise RuntimeError("Audio request is too large for the configured transcription API.")

        try:
            with httpx.Client(
                base_url=self._base_url,
                headers=self._headers(),
                timeout=self._timeout_seconds,
            ) as client:
                response = client.post(
                    "chat/completions",
                    json=self._request_payload(data_url),
                )
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            raise RuntimeError(f"Audio transcription API failed: HTTP {status_code}") from exc
        except httpx.HTTPError as exc:
            raise RuntimeError(f"Audio transcription API failed: {exc}") from exc

        return self._extract_api_text(response.json()).strip()

    def _request_payload(self, data_url: str) -> dict[str, object]:
        asr_options: dict[str, object] = {"enable_itn": False}
        if self._language not in {"auto", "nospeech"}:
            asr_options["language"] = self._language

        return {
            "model": self._model_name,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_audio",
                            "input_audio": {"data": data_url},
                        },
                    ],
                }
            ],
            "stream": False,
            "asr_options": asr_options,
        }

    def _extract_api_text(self, payload: object) -> str:
        if not isinstance(payload, dict):
            raise RuntimeError("Audio transcription API returned a non-object response.")
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            raise RuntimeError("Audio transcription API response did not include choices.")
        first_choice = choices[0]
        if not isinstance(first_choice, dict):
            raise RuntimeError("Audio transcription API response included an invalid choice.")
        message = first_choice.get("message")
        if not isinstance(message, dict):
            raise RuntimeError("Audio transcription API response did not include a message.")
        content = message.get("content", "")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, dict) and isinstance(item.get("text"), str):
                    parts.append(item["text"])
            return "".join(parts)
        return ""

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    def _wav_data_url(self, wav_bytes: bytes) -> str:
        encoded = base64.b64encode(wav_bytes).decode("ascii")
        return f"data:audio/wav;base64,{encoded}"
