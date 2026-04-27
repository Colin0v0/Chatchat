from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from ..schemas import AudioSpeechOut


class AudioSynthesisError(RuntimeError):
    pass


@dataclass(frozen=True)
class AudioSynthesisRequest:
    text: str
    voice: str | None = None
    rate: float | None = None


class DashScopeSpeechSynthesizer:
    def __init__(
        self,
        *,
        model_name: str,
        base_url: str,
        api_key: str,
        enabled: bool,
        voice: str,
        audio_format: str,
        sample_rate: int,
        timeout_seconds: float,
        max_chars: int,
    ):
        self._model_name = model_name.strip()
        self._base_url = base_url.strip().rstrip("/")
        self._api_key = api_key.strip()
        self._enabled = enabled
        self._voice = voice.strip()
        self._audio_format = audio_format.strip().lower() or "mp3"
        self._sample_rate = sample_rate
        self._timeout_seconds = timeout_seconds
        self._max_chars = max(1, max_chars)

    @property
    def is_enabled(self) -> bool:
        return self._enabled

    def synthesize(self, request: AudioSynthesisRequest) -> AudioSpeechOut:
        if not self._enabled:
            raise AudioSynthesisError("Audio speech synthesis is disabled.")
        if not self._base_url:
            raise AudioSynthesisError("Audio speech synthesis API base URL is not configured.")
        if not self._api_key:
            raise AudioSynthesisError("Audio speech synthesis API key is not configured.")

        text = request.text.strip()
        if not text:
            raise AudioSynthesisError("Audio speech synthesis text is empty.")
        if len(text) > self._max_chars:
            text = text[: self._max_chars]

        voice = (request.voice or "").strip() or self._voice
        payload = self._request_payload(text=text, voice=voice, rate=request.rate)

        try:
            with httpx.Client(
                headers=self._headers(),
                timeout=self._timeout_seconds,
            ) as client:
                response = client.post(self._base_url, json=payload)
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            raise AudioSynthesisError(f"Audio speech synthesis API failed: HTTP {status_code}") from exc
        except httpx.HTTPError as exc:
            raise AudioSynthesisError(f"Audio speech synthesis API failed: {exc}") from exc

        return self._parse_response(response.json(), voice=voice)

    def _request_payload(self, *, text: str, voice: str, rate: float | None) -> dict[str, object]:
        input_payload: dict[str, object] = {
            "text": text,
            "voice": voice,
            "format": self._audio_format,
            "sample_rate": self._sample_rate,
        }
        if rate is not None:
            input_payload["rate"] = max(0.5, min(2.0, rate))

        return {
            "model": self._model_name,
            "input": input_payload,
        }

    def _parse_response(self, payload: object, *, voice: str) -> AudioSpeechOut:
        if not isinstance(payload, dict):
            raise AudioSynthesisError("Audio speech synthesis API returned a non-object response.")

        output = payload.get("output")
        if not isinstance(output, dict):
            raise AudioSynthesisError("Audio speech synthesis API response did not include output.")

        audio = output.get("audio")
        if not isinstance(audio, dict):
            raise AudioSynthesisError("Audio speech synthesis API response did not include audio.")

        url = audio.get("url")
        if not isinstance(url, str) or not url:
            raise AudioSynthesisError("Audio speech synthesis API response did not include an audio URL.")

        usage = payload.get("usage")
        characters = usage.get("characters") if isinstance(usage, dict) else None
        expires_at = audio.get("expires_at")
        request_id = payload.get("request_id")
        audio_id = audio.get("id")

        return AudioSpeechOut(
            audio_id=audio_id if isinstance(audio_id, str) else None,
            characters=characters if isinstance(characters, int) else None,
            content_type=self._content_type(),
            expires_at=expires_at if isinstance(expires_at, int) else None,
            model=self._model_name,
            request_id=request_id if isinstance(request_id, str) else None,
            url=url,
            voice=voice,
        )

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    def _content_type(self) -> str:
        if self._audio_format == "wav":
            return "audio/wav"
        if self._audio_format == "opus":
            return "audio/ogg"
        if self._audio_format == "pcm":
            return "audio/L16"
        return "audio/mpeg"
