from __future__ import annotations

import base64
import io
import logging
import math
import wave
from array import array
from dataclasses import dataclass

import httpx

from ..schemas import AudioTranscriptionOut
from .ffmpeg import transcode_audio_to_wav


class AudioModelLoadError(RuntimeError):
    pass


logger = logging.getLogger("chatchat.audio")
SUPPORTED_ASR_LANGUAGES = {"auto", "zh", "en", "yue", "ja", "ko", "nospeech"}


@dataclass(frozen=True)
class AudioGateDecision:
    skip: bool
    reason: str | None
    rms_dbfs: float


def _normalize_language(value: str) -> str:
    normalized = value.strip().lower()
    if normalized == "cn":
        return "zh"
    if normalized not in SUPPORTED_ASR_LANGUAGES:
        return "zh"
    return normalized


class AudioTranscriber:
    def __init__(
        self,
        *,
        model_name: str,
        enabled: bool,
        language: str = "zh",
        min_duration_ms: int = 650,
        min_rms_dbfs: float = -65.0,
    ):
        self._model_name = model_name
        self._enabled = enabled
        self._language = _normalize_language(language)
        self._min_duration_ms = max(0, min_duration_ms)
        self._min_rms_dbfs = min_rms_dbfs

    @property
    def requires_local_gpu(self) -> bool:
        return False

    @property
    def is_enabled(self) -> bool:
        return self._enabled

    def load(self) -> None:
        return

    def unload(self) -> None:
        return

    def transcribe(self, audio_bytes: bytes) -> AudioTranscriptionOut:
        if not self._enabled:
            raise AudioModelLoadError("Audio transcription is disabled in the current environment.")
        wav_bytes = transcode_audio_to_wav(audio_bytes)
        duration_ms = self._wav_duration_ms(wav_bytes)
        gate = self._inspect_audio(wav_bytes, duration_ms=duration_ms)
        logger.info(
            "audio transcribe input | bytes=%s | wav_bytes=%s | duration_ms=%s | rms_dbfs=%.1f | language=%s",
            len(audio_bytes),
            len(wav_bytes),
            duration_ms,
            gate.rms_dbfs,
            self._language,
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

        text = self._transcribe_wav(wav_bytes).strip()
        logger.info(
            "audio transcribe %s | duration_ms=%s | rms_dbfs=%.1f | text_len=%s",
            "success" if text else "empty",
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

    def _transcribe_wav(self, wav_bytes: bytes) -> str:
        raise NotImplementedError("AudioTranscriber must be backed by an API implementation.")

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
    ):
        super().__init__(
            model_name=model_name,
            enabled=enabled,
            language=language,
            min_duration_ms=min_duration_ms,
            min_rms_dbfs=min_rms_dbfs,
        )
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key.strip()
        self._timeout_seconds = max(1.0, timeout_seconds)
        self._max_request_bytes = max(1, max_request_bytes)

    def load(self) -> None:
        if not self._enabled:
            return
        if not self._base_url:
            raise AudioModelLoadError("Audio transcription API base URL is not configured.")
        if not self._api_key:
            raise AudioModelLoadError("Audio transcription API key is not configured.")

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
