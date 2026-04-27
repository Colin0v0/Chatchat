from __future__ import annotations

import logging
import re
from dataclasses import dataclass

import httpx

from ..core.config import settings
from ..core.http import limited_request, shared_http_clients
from ..llm.capabilities import normalize_base_url
from ..provider_codecs.openai import _parse_openai_json_response

logger = logging.getLogger("chatchat.transport.openai_images")

IMAGE_QUALITIES = {"auto", "low", "medium", "high"}
IMAGE_OUTPUT_FORMATS = {"png", "jpeg", "webp"}
IMAGE_SIZE_PATTERN = re.compile(r"^(auto|[1-9]\d{1,4}x[1-9]\d{1,4})$")
OPENAI_NATIVE_IMAGE_SIZES = {"auto", "1024x1024", "1536x1024", "1024x1536"}


@dataclass(frozen=True)
class GeneratedImage:
    b64_json: str = ""
    url: str = ""
    revised_prompt: str = ""
    output_format: str = "png"


def openai_image_base_url(base_url_override: str | None = None) -> str:
    return (
        base_url_override
        or settings.openai_image_base_url.strip()
        or settings.openai_base_url
    )


def openai_image_headers(api_key_override: str | None = None) -> dict[str, str]:
    api_key = (
        api_key_override
        or settings.openai_image_api_key.strip()
        or settings.openai_api_key.strip()
    )
    return {"Authorization": f"Bearer {api_key}"} if api_key else {}


def normalize_image_quality(value: str | None) -> str:
    quality = (value or settings.openai_image_quality).strip().lower() or "auto"
    if quality not in IMAGE_QUALITIES:
        raise ValueError("Image quality must be one of: auto, low, medium, high.")
    return quality


def normalize_image_output_format(value: str | None) -> str:
    output_format = (value or settings.openai_image_output_format).strip().lower() or "png"
    if output_format == "jpg":
        output_format = "jpeg"
    if output_format not in IMAGE_OUTPUT_FORMATS:
        raise ValueError("Image output format must be one of: png, jpeg, webp.")
    return output_format


def normalize_image_size(value: str | None) -> str:
    size = (value or settings.openai_image_size).strip() or "1024x1024"
    normalized = size.lower()
    if not IMAGE_SIZE_PATTERN.match(normalized):
        raise ValueError("Image size must be auto or WIDTHxHEIGHT, for example 1024x1024.")
    if normalized not in OPENAI_NATIVE_IMAGE_SIZES:
        raise ValueError(
            "Image size must be one of the upstream-native sizes: "
            "auto, 1024x1024, 1536x1024, 1024x1536."
        )
    return normalized


def _image_timeout() -> httpx.Timeout:
    timeout_seconds = max(1.0, settings.openai_image_timeout_seconds)
    return httpx.Timeout(
        timeout_seconds,
        connect=settings.openai_connect_timeout_seconds,
    )


async def _openai_image_client(
    *,
    base_url_override: str | None,
    api_key_override: str | None,
) -> httpx.AsyncClient:
    return await shared_http_clients.get_client(
        base_url=normalize_base_url(openai_image_base_url(base_url_override)),
        headers=openai_image_headers(api_key_override),
        timeout=_image_timeout(),
        limits=httpx.Limits(
            max_connections=max(1, settings.http_pool_max_connections),
            max_keepalive_connections=max(1, settings.http_pool_max_keepalive_connections),
        ),
    )


async def generate_openai_image(
    *,
    prompt: str,
    size: str | None = None,
    quality: str | None = None,
    output_format: str | None = None,
    base_url_override: str | None = None,
    api_key_override: str | None = None,
) -> GeneratedImage:
    normalized_prompt = prompt.strip()
    if not normalized_prompt:
        raise ValueError("Image prompt is required.")

    resolved_output_format = normalize_image_output_format(output_format)
    requested_size = normalize_image_size(size)
    payload: dict[str, object] = {
        "model": settings.openai_image_model.strip() or "gpt-image-2",
        "prompt": normalized_prompt,
        "n": 1,
        "size": requested_size,
        "quality": normalize_image_quality(quality),
        "output_format": resolved_output_format,
    }

    logger.info(
        "generate_openai_image target | base_url=%s | model=%s | size=%s | quality=%s | format=%s",
        normalize_base_url(openai_image_base_url(base_url_override)),
        payload["model"],
        payload["size"],
        payload["quality"],
        resolved_output_format,
    )

    async with limited_request(
        gate="openai_image",
        max_concurrency=max(1, settings.openai_http_max_concurrency),
    ):
        client = await _openai_image_client(
            base_url_override=base_url_override,
            api_key_override=api_key_override,
        )
        response = await client.post("/images/generations", json=payload)
        response.raise_for_status()

    payload_data = _parse_openai_json_response(response, context="images.generations")
    data = payload_data.get("data")
    if not isinstance(data, list) or not data:
        raise RuntimeError("Image generation succeeded but returned no image data.")

    first_image = data[0]
    if not isinstance(first_image, dict):
        raise RuntimeError("Image generation returned an unexpected response shape.")
    b64_json = str(first_image.get("b64_json", "")).strip()
    image_url = str(first_image.get("url", "")).strip()
    if not b64_json and not image_url:
        returned_keys = ", ".join(sorted(str(key) for key in first_image.keys()))
        raise RuntimeError(
            "Image generation did not return b64_json or url."
            + (f" Returned keys: {returned_keys}." if returned_keys else "")
        )

    revised_prompt = str(first_image.get("revised_prompt", "")).strip()
    return GeneratedImage(
        b64_json=b64_json,
        url=image_url,
        revised_prompt=revised_prompt,
        output_format=resolved_output_format,
    )


__all__ = [
    "GeneratedImage",
    "generate_openai_image",
    "normalize_image_output_format",
    "normalize_image_quality",
    "normalize_image_size",
    "openai_image_base_url",
    "openai_image_headers",
]
