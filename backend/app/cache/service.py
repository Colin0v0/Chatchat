from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from hashlib import sha256
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from redis.asyncio import Redis


_client: "Redis | None" = None
_client_url: str | None = None


def cache_enabled(settings: object) -> bool:
    return bool(getattr(settings, "cache_enabled", False))


def build_cache_key(
    settings: object,
    *,
    namespace: str,
    version: int,
    payload: object,
) -> str:
    digest = sha256(_stable_json(payload).encode("utf-8")).hexdigest()
    prefix = str(getattr(settings, "cache_key_prefix", "chatchat")).strip() or "chatchat"
    return f"{prefix}:{namespace}:v{version}:{digest}"


async def initialize_cache(settings: object) -> None:
    if not cache_enabled(settings):
        return
    await _redis_client(settings).ping()


async def close_cache() -> None:
    global _client, _client_url
    if _client is None:
        return
    await _client.aclose()
    _client = None
    _client_url = None


async def get_json(settings: object, key: str) -> object | None:
    if not cache_enabled(settings):
        return None

    raw = await _redis_client(settings).get(key)
    if raw is None:
        return None
    if not isinstance(raw, str):
        raise RuntimeError("Redis cache returned a non-text JSON payload.")
    return json.loads(raw)


async def set_json(settings: object, key: str, value: object, *, ttl_seconds: int) -> None:
    if not cache_enabled(settings):
        return

    ttl = max(1, int(ttl_seconds))
    await _redis_client(settings).set(key, _stable_json(value), ex=ttl)


def _redis_client(settings: object) -> "Redis":
    global _client, _client_url
    redis_url = str(getattr(settings, "redis_url", "")).strip()
    if not redis_url:
        raise RuntimeError("REDIS_URL is required when cache is enabled.")

    if _client is None or _client_url != redis_url:
        from redis.asyncio import Redis

        _client = Redis.from_url(redis_url, decode_responses=True)
        _client_url = redis_url
    return _client


def _stable_json(value: object) -> str:
    return json.dumps(
        _to_jsonable(value),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _to_jsonable(value: object) -> object:
    if is_dataclass(value) and not isinstance(value, type):
        return _to_jsonable(asdict(value))
    if isinstance(value, dict):
        return {str(key): _to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, set):
        return sorted(_to_jsonable(item) for item in value)
    return value
