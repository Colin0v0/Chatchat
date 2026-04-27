from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass

import httpx


@dataclass(frozen=True)
class HttpClientKey:
    base_url: str
    headers: tuple[tuple[str, str], ...]
    timeout: tuple[float | None, float | None, float | None, float | None]
    limits: tuple[int, int | None]


class SharedHttpClientRegistry:
    def __init__(self) -> None:
        self._clients: dict[HttpClientKey, httpx.AsyncClient] = {}
        self._lock = asyncio.Lock()

    async def get_client(
        self,
        *,
        base_url: str,
        headers: dict[str, str] | None = None,
        timeout: httpx.Timeout | float | None = None,
        limits: httpx.Limits | None = None,
    ) -> httpx.AsyncClient:
        normalized_timeout = _normalize_timeout(timeout)
        normalized_limits = limits or httpx.Limits()
        key = HttpClientKey(
            base_url=base_url.rstrip("/"),
            headers=tuple(sorted((headers or {}).items())),
            timeout=normalized_timeout,
            limits=(
                normalized_limits.max_connections,
                normalized_limits.max_keepalive_connections,
            ),
        )
        async with self._lock:
            client = self._clients.get(key)
            if client is None:
                client = httpx.AsyncClient(
                    base_url=key.base_url,
                    headers=dict(key.headers),
                    timeout=_timeout_from_tuple(normalized_timeout),
                    limits=normalized_limits,
                )
                self._clients[key] = client
            return client

    async def aclose(self) -> None:
        async with self._lock:
            clients = list(self._clients.values())
            self._clients.clear()
        for client in clients:
            await client.aclose()


class RequestGateRegistry:
    def __init__(self) -> None:
        self._semaphores: dict[tuple[str, int], asyncio.Semaphore] = {}
        self._lock = asyncio.Lock()

    async def semaphore(self, *, gate: str, max_concurrency: int) -> asyncio.Semaphore:
        normalized_max = max(1, max_concurrency)
        key = (gate, normalized_max)
        async with self._lock:
            semaphore = self._semaphores.get(key)
            if semaphore is None:
                semaphore = asyncio.Semaphore(normalized_max)
                self._semaphores[key] = semaphore
            return semaphore


def _normalize_timeout(timeout: httpx.Timeout | float | None) -> tuple[float | None, float | None, float | None, float | None]:
    if isinstance(timeout, (int, float)):
        normalized = float(timeout)
        return (normalized, normalized, normalized, normalized)
    if timeout is None:
        default = httpx.Timeout(timeout=None)
        return (default.connect, default.read, default.write, default.pool)
    return (timeout.connect, timeout.read, timeout.write, timeout.pool)


def _timeout_from_tuple(values: tuple[float | None, float | None, float | None, float | None]) -> httpx.Timeout:
    connect, read, write, pool = values
    return httpx.Timeout(connect=connect, read=read, write=write, pool=pool)


shared_http_clients = SharedHttpClientRegistry()
shared_request_gates = RequestGateRegistry()


@asynccontextmanager
async def limited_request(*, gate: str, max_concurrency: int):
    semaphore = await shared_request_gates.semaphore(gate=gate, max_concurrency=max_concurrency)
    async with semaphore:
        yield
