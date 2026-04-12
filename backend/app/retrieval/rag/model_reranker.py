from __future__ import annotations

import asyncio
import json
import logging
import re

import httpx

from ...chat.types import ChatMessagePayload
from ...core.config import Settings
from ...core.http import limited_request, shared_http_clients
from ...llm.capabilities import Provider, model_provider_and_name, normalize_base_url
from ...llm.catalog import resolve_model_route
from ...llm.openai_client import (
    _extract_responses_output,
    _parse_openai_json_response,
    apply_reasoning_controls,
    apply_responses_reasoning_controls,
    openai_base_url,
    openai_headers,
    responses_message_payload,
)
from ...llm.ollama_runtime import ollama_keep_alive_value
from .types import RetrievalCandidate

JSON_SCORE_PATTERN = re.compile(r'"score"\s*:\s*([01](?:\.\d+)?)')
NUMBER_PATTERN = re.compile(r'([01](?:\.\d+)?)')
logger = logging.getLogger("chatchat.rerank")


class ModelReranker:
    def __init__(self, settings: Settings, rerank_window: int):
        self._settings = settings
        self._model_id = settings.knowledge_rerank_model.strip()
        self._provider, self._upstream_model, self._base_url_override, self._api_key_override = (
            self._resolve_model_target(self._model_id)
        )
        self._rerank_window = max(1, rerank_window)
        self._max_chars = max(240, settings.knowledge_rerank_max_chars)
        self._max_concurrency = max(1, settings.knowledge_rerank_max_concurrency)
        self._num_ctx = max(256, settings.knowledge_rerank_num_ctx)
        self._base_url = settings.ollama_base_url.rstrip("/")
        self._request_timeout = httpx.Timeout(settings.request_timeout_seconds, connect=10.0)
        self._keep_alive = ollama_keep_alive_value(settings.ollama_keep_alive_seconds)
        self._disabled_reason = self._detect_disabled_reason()

        if self._model_id and self._disabled_reason:
            logger.warning(
                "knowledge reranker disabled | model=%s | provider=%s | reason=%s",
                self._model_id,
                self._provider,
                self._disabled_reason,
            )

    @property
    def enabled(self) -> bool:
        return bool(self._model_id) and self._disabled_reason is None

    @property
    def disabled_reason(self) -> str | None:
        return self._disabled_reason

    async def rerank(
        self,
        *,
        query: str,
        candidates: list[RetrievalCandidate],
    ) -> list[RetrievalCandidate]:
        if not query.strip() or not candidates:
            return self._finalize(candidates)
        if not self.enabled:
            return self._finalize(candidates)

        rerank_slice = candidates[: self._rerank_window]
        scores = await asyncio.gather(
            *(self._score_candidate(query=query, candidate=candidate) for candidate in rerank_slice)
        )

        reranked: list[RetrievalCandidate] = []
        for index, candidate in enumerate(candidates):
            if index < len(scores):
                candidate.rerank_score = scores[index]
                candidate.final_score = (candidate.hybrid_score * 0.35) + (scores[index] * 0.65)
            else:
                candidate.rerank_score = 0.0
                candidate.final_score = candidate.hybrid_score
            reranked.append(candidate)

        reranked.sort(key=lambda item: item.final_score, reverse=True)
        return reranked

    def _finalize(self, candidates: list[RetrievalCandidate]) -> list[RetrievalCandidate]:
        for candidate in candidates:
            candidate.rerank_score = 0.0
            candidate.final_score = candidate.hybrid_score
        return candidates

    def _resolve_model_target(
        self,
        model_id: str,
    ) -> tuple[Provider, str, str | None, str | None]:
        route = resolve_model_route(model_id) if model_id else None
        if route is not None:
            return (
                route["provider"],
                route["upstream_model"],
                route.get("base_url"),
                route.get("api_key"),
            )

        provider, model_name = model_provider_and_name(model_id)
        return provider, model_name, None, None

    def _detect_disabled_reason(self) -> str | None:
        normalized = self._model_id.strip().lower()
        if not normalized:
            return "unconfigured"
        if self._provider == "ollama" and "qwen3-reranker" in normalized:
            return "ollama_rerank_unsupported"
        return None

    async def _score_candidate(
        self,
        *,
        query: str,
        candidate: RetrievalCandidate,
    ) -> float:
        if self._provider == "codex":
            return await self._score_candidate_codex(query=query, candidate=candidate)
        if self._provider in ("openai", "openai_local"):
            return await self._score_candidate_openai(query=query, candidate=candidate)
        return await self._score_candidate_ollama(query=query, candidate=candidate)

    async def _score_candidate_codex(
        self,
        *,
        query: str,
        candidate: RetrievalCandidate,
    ) -> float:
        prompt = self._build_prompt(query=query, candidate=candidate)
        client = await shared_http_clients.get_client(
            base_url=normalize_base_url(openai_base_url(self._provider, self._base_url_override)),
            headers=openai_headers(self._provider, self._api_key_override),
            timeout=httpx.Timeout(
                self._settings.request_timeout_seconds,
                connect=self._settings.openai_connect_timeout_seconds,
            ),
            limits=httpx.Limits(
                max_connections=max(1, self._settings.http_pool_max_connections),
                max_keepalive_connections=max(1, self._settings.http_pool_max_keepalive_connections),
            ),
        )
        gate, max_concurrency = self._request_gate()
        retry_errors: list[str] = []

        for attempt in range(2):
            payload = self._build_codex_payload(prompt)
            if attempt > 0:
                # Retry with lower reasoning overhead to maximize deterministic short JSON output.
                payload["reasoning"] = {"effort": "minimal"}

            async with limited_request(gate=gate, max_concurrency=max_concurrency):
                response = await client.post("/responses", json=payload)
                response.raise_for_status()

            payload_data = _parse_openai_json_response(response, context="responses.create")
            content = self._extract_codex_content(payload_data)

            try:
                score = self._parse_score(content)
                return max(0.0, min(1.0, score))
            except RuntimeError as exc:
                # Some OpenAI-compatible routers occasionally return empty message text while still
                # carrying partial structured payload. Try parsing from the raw response body.
                try:
                    fallback_raw = json.dumps(payload_data, ensure_ascii=False)
                    score = self._parse_score(fallback_raw)
                    return max(0.0, min(1.0, score))
                except RuntimeError:
                    retry_errors.append(str(exc))
                    if attempt == 0:
                        logger.warning(
                            "codex rerank response parse failed; retrying once | model=%s | reason=%s",
                            self._upstream_model,
                            exc,
                        )
                        continue
                    break

        raise RuntimeError(
            "Reranker could not parse a score from codex response. "
            f"Last errors: {' | '.join(retry_errors) if retry_errors else 'unknown'}"
        )

    async def _score_candidate_openai(
        self,
        *,
        query: str,
        candidate: RetrievalCandidate,
    ) -> float:
        prompt = self._build_prompt(query=query, candidate=candidate)
        client = await shared_http_clients.get_client(
            base_url=normalize_base_url(openai_base_url(self._provider, self._base_url_override)),
            headers=openai_headers(self._provider, self._api_key_override),
            timeout=httpx.Timeout(
                self._settings.request_timeout_seconds,
                connect=self._settings.openai_connect_timeout_seconds,
            ),
            limits=httpx.Limits(
                max_connections=max(1, self._settings.http_pool_max_connections),
                max_keepalive_connections=max(1, self._settings.http_pool_max_keepalive_connections),
            ),
        )
        gate, max_concurrency = self._request_gate()
        payload = self._build_openai_payload(prompt)

        async with limited_request(gate=gate, max_concurrency=max_concurrency):
            response = await client.post("/chat/completions", json=payload)
            response.raise_for_status()

        payload_data = response.json()
        if not isinstance(payload_data, dict):
            raise RuntimeError("Reranker returned an unexpected response shape.")
        content = self._extract_openai_content(payload_data)
        score = self._parse_score(content)
        return max(0.0, min(1.0, score))

    def _build_openai_payload(self, prompt: str) -> dict[str, object]:
        payload: dict[str, object] = {
            "model": self._upstream_model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a strict retrieval reranker. "
                        "Return JSON only in the exact form {\"score\": 0.00}."
                    ),
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            "stream": False,
            "temperature": 0,
            "max_tokens": 24,
        }
        apply_reasoning_controls(payload, provider=self._provider, thinking_enabled=False)
        return payload

    def _build_codex_payload(self, prompt: str) -> dict[str, object]:
        payload: dict[str, object] = {
            "model": self._upstream_model,
            "input": [
                responses_message_payload(
                    ChatMessagePayload(
                        role="system",
                        content=(
                            "You are a strict retrieval reranker. "
                            "Return JSON only in the exact form {\"score\": 0.00}."
                        ),
                    )
                ),
                responses_message_payload(
                    ChatMessagePayload(
                        role="user",
                        content=prompt,
                    )
                ),
            ],
            "max_output_tokens": 64,
            "text": {"format": {"type": "json_object"}},
        }
        apply_responses_reasoning_controls(payload, thinking_enabled=False)
        return payload

    def _extract_codex_content(self, payload: dict[str, object]) -> str:
        output = _extract_responses_output(payload)
        message = output.get("message", "").strip()
        if message:
            return message

        output_text = payload.get("output_text")
        if isinstance(output_text, str) and output_text.strip():
            return output_text.strip()

        collected_chunks: list[str] = []
        items = payload.get("output")
        if isinstance(items, list):
            for item in items:
                if not isinstance(item, dict):
                    continue
                content = item.get("content")
                if isinstance(content, list):
                    for part in content:
                        if not isinstance(part, dict):
                            continue
                        text = part.get("text")
                        if isinstance(text, str) and text.strip():
                            collected_chunks.append(text.strip())
                summary = item.get("summary")
                if isinstance(summary, list):
                    for part in summary:
                        if not isinstance(part, dict):
                            continue
                        text = part.get("text")
                        if isinstance(text, str) and text.strip():
                            collected_chunks.append(text.strip())
                refusal = item.get("refusal")
                if isinstance(refusal, str) and refusal.strip():
                    collected_chunks.append(refusal.strip())

        return "\n".join(collected_chunks).strip()

    async def _score_candidate_ollama(
        self,
        *,
        query: str,
        candidate: RetrievalCandidate,
    ) -> float:
        prompt = self._build_prompt(query=query, candidate=candidate)
        client = await shared_http_clients.get_client(
            base_url=self._base_url,
            timeout=self._request_timeout,
            limits=httpx.Limits(max_connections=32, max_keepalive_connections=16),
        )

        async with limited_request(gate="ollama", max_concurrency=self._max_concurrency):
            response = await client.post(
                "/api/generate",
                json={
                    "model": self._upstream_model,
                    "prompt": prompt,
                    "format": "json",
                    "stream": False,
                    "keep_alive": self._keep_alive,
                    "options": {
                        "temperature": 0,
                        "num_predict": 16,
                        "num_ctx": self._num_ctx,
                    },
                },
            )
            response.raise_for_status()

        payload = response.json()
        content = str(payload.get("response", "")).strip()
        score = self._parse_score(content)
        return max(0.0, min(1.0, score))

    def _request_gate(self) -> tuple[str, int]:
        if self._provider == "openai_local":
            return "openai_local", min(
                self._max_concurrency,
                max(1, self._settings.openai_local_http_max_concurrency),
            )
        if self._provider == "codex":
            return "codex", min(
                self._max_concurrency,
                max(1, self._settings.openai_http_max_concurrency),
            )
        if self._provider == "openai":
            return "openai", min(
                self._max_concurrency,
                max(1, self._settings.openai_http_max_concurrency),
            )
        return "ollama", self._max_concurrency

    def _extract_openai_content(self, payload: dict[str, object]) -> str:
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            raise RuntimeError("Reranker returned no choices.")

        first = choices[0]
        if not isinstance(first, dict):
            raise RuntimeError("Reranker returned an invalid choice payload.")
        message = first.get("message")
        if not isinstance(message, dict):
            raise RuntimeError("Reranker returned an invalid message payload.")
        content = message.get("content", "")
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            text_parts: list[str] = []
            for item in content:
                if isinstance(item, dict):
                    text = item.get("text")
                    if isinstance(text, str) and text.strip():
                        text_parts.append(text.strip())
            return "\n".join(text_parts).strip()
        return str(content).strip()

    def _build_prompt(self, *, query: str, candidate: RetrievalCandidate) -> str:
        passage = self._truncate(candidate.chunk.content)
        return (
            "You are a strict retrieval reranker.\n"
            "Judge how useful the passage is for answering the query.\n"
            "Return valid JSON only in the exact form {\"score\": 0.00}.\n"
            "Do not output markdown, punctuation art, explanations, or any extra keys.\n"
            "Use a score between 0 and 1.\n"
            "1.0 means the passage is highly relevant and directly useful.\n"
            "0.0 means the passage is irrelevant.\n\n"
            f"Query:\n{query.strip()}\n\n"
            f"Passage title:\n{candidate.chunk.path} | {candidate.chunk.heading}\n\n"
            f"Passage:\n{passage}\n"
        )

    def _truncate(self, value: str) -> str:
        normalized = value.strip()
        if len(normalized) <= self._max_chars:
            return normalized
        return normalized[: self._max_chars].rstrip()

    def _parse_score(self, content: str) -> float:
        if not content:
            raise RuntimeError("Reranker returned an empty response.")

        try:
            payload = json.loads(content)
        except json.JSONDecodeError:
            payload = None

        if isinstance(payload, dict):
            raw = payload.get("score")
            if isinstance(raw, (int, float)):
                return float(raw)
            if isinstance(raw, str):
                return float(raw.strip())

        matched = JSON_SCORE_PATTERN.search(content) or NUMBER_PATTERN.search(content)
        if matched:
            return float(matched.group(1))

        raise RuntimeError(f"Reranker returned an invalid score payload: {content[:160]}")
