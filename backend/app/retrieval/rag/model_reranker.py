from __future__ import annotations

import logging

import httpx

from ...cache import build_cache_key, get_json, set_json
from ...core.config import Settings
from ...core.http import limited_request
from ...llm.capabilities import normalize_base_url
from .types import RetrievalCandidate

logger = logging.getLogger("chatchat.rerank")
DASHSCOPE_RERANK_URL = "https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank"
DASHSCOPE_RERANK_PROVIDERS = {"dashscope", "aliyun", "bailian", "alibabacloud"}
DASHSCOPE_SCORE_KEYS = ("relevance_score", "score")


class ModelReranker:
    def __init__(self, settings: Settings, rerank_window: int):
        self._settings = settings
        self._model_id = settings.knowledge_rerank_model.strip()
        self._provider = self._resolve_provider()
        self._upstream_model = self._resolve_model_name(self._model_id)
        self._rerank_window = max(1, rerank_window)
        self._max_chars = max(240, settings.knowledge_rerank_max_chars)
        self._max_concurrency = max(1, settings.knowledge_rerank_max_concurrency)
        self._cache_ttl_seconds = max(1, int(getattr(settings, "cache_rerank_ttl_seconds", 21600)))
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
        scores = await self._score_candidates_dashscope(query=query, candidates=rerank_slice)

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

    def _resolve_provider(self) -> str:
        configured = str(getattr(self._settings, "knowledge_rerank_provider", "dashscope")).strip().lower()
        if configured in DASHSCOPE_RERANK_PROVIDERS:
            return "dashscope"
        return configured or "dashscope"

    def _resolve_model_name(self, model_id: str) -> str:
        parts = model_id.split(":", 1)
        if len(parts) == 2 and parts[0].strip().lower() in DASHSCOPE_RERANK_PROVIDERS:
            return parts[1].strip()
        if len(parts) == 2:
            return ""
        return model_id.strip()

    def _detect_disabled_reason(self) -> str | None:
        normalized = self._model_id.strip()
        if not normalized:
            return "unconfigured"
        if self._provider != "dashscope":
            return "unsupported_provider"
        if not self._upstream_model:
            return "unsupported_model_provider"
        if not self._dashscope_api_key():
            return "dashscope_api_key_missing"
        return None

    async def _score_candidates_dashscope(
        self,
        *,
        query: str,
        candidates: list[RetrievalCandidate],
    ) -> list[float]:
        if not candidates:
            return []

        timeout_seconds = max(
            1.0,
            float(getattr(self._settings, "knowledge_rerank_timeout_seconds", 30.0)),
        )
        payload = self._build_dashscope_rerank_payload(query=query, candidates=candidates)
        cache_key = self._cache_key(payload)
        cached = await get_json(self._settings, cache_key)
        if cached is not None:
            return self._parse_cached_scores(cached, expected_count=len(candidates))

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(timeout_seconds, connect=min(10.0, timeout_seconds)),
        ) as client:
            async with limited_request(gate="dashscope_rerank", max_concurrency=self._max_concurrency):
                response = await client.post(
                    self._dashscope_rerank_url(),
                    headers=self._dashscope_headers(),
                    json=payload,
                )
                response.raise_for_status()

        scores = self._parse_dashscope_rerank_scores(response.json(), expected_count=len(candidates))
        # rerank 输入是 query + 截断后的候选文本，缓存可以避开重复排序请求。
        await set_json(
            self._settings,
            cache_key,
            scores,
            ttl_seconds=self._cache_ttl_seconds,
        )
        return scores

    def _build_dashscope_rerank_payload(
        self,
        *,
        query: str,
        candidates: list[RetrievalCandidate],
    ) -> dict[str, object]:
        documents = [self._candidate_document_text(candidate) for candidate in candidates]
        return {
            "model": self._upstream_model,
            "input": {
                "query": query.strip(),
                "documents": documents,
            },
            "parameters": {
                "return_documents": False,
                "top_n": len(documents),
            },
        }

    def _parse_dashscope_rerank_scores(self, payload: object, *, expected_count: int) -> list[float]:
        if not isinstance(payload, dict):
            raise RuntimeError("DashScope rerank returned a non-object response.")

        raw_results: object = None
        output = payload.get("output")
        if isinstance(output, dict):
            raw_results = output.get("results")
        if raw_results is None:
            raw_results = payload.get("results")
        if not isinstance(raw_results, list):
            raise RuntimeError("DashScope rerank response did not include results.")

        scores = [0.0] * max(0, expected_count)
        for item in raw_results:
            if not isinstance(item, dict):
                continue
            raw_index = item.get("index")
            if isinstance(raw_index, bool):
                continue
            try:
                index = int(raw_index)
            except (TypeError, ValueError):
                continue
            if index < 0 or index >= len(scores):
                continue

            raw_score = next((item.get(key) for key in DASHSCOPE_SCORE_KEYS if key in item), None)
            if isinstance(raw_score, bool):
                continue
            try:
                score = float(raw_score)
            except (TypeError, ValueError):
                continue
            scores[index] = max(0.0, min(1.0, score))

        return scores

    def _parse_cached_scores(self, payload: object, *, expected_count: int) -> list[float]:
        if not isinstance(payload, list):
            raise RuntimeError("Rerank cache entry must be a list.")
        scores = [float(value) for value in payload]
        if len(scores) != expected_count:
            raise RuntimeError(
                "Rerank cache returned an unexpected score count. "
                f"Expected {expected_count}, got {len(scores)}."
            )
        return [max(0.0, min(1.0, score)) for score in scores]

    def _cache_key(self, payload: dict[str, object]) -> str:
        return build_cache_key(
            self._settings,
            namespace="rerank",
            version=1,
            payload={
                "provider": self._provider,
                "model": self._upstream_model,
                "payload": payload,
            },
        )

    def _candidate_document_text(self, candidate: RetrievalCandidate) -> str:
        title = " | ".join(
            part.strip()
            for part in (candidate.chunk.path, candidate.chunk.heading)
            if part.strip()
        )
        passage = self._truncate(candidate.chunk.content)
        if title:
            return f"{title}\n{passage}".strip()
        return passage

    def _dashscope_headers(self) -> dict[str, str]:
        api_key = self._dashscope_api_key()
        if not api_key:
            raise RuntimeError("KNOWLEDGE_RERANK_API_KEY or DASHSCOPE_API_KEY is required for DashScope rerank.")
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    def _dashscope_api_key(self) -> str:
        return (
            str(getattr(self._settings, "knowledge_rerank_api_key", "")).strip()
            or str(getattr(self._settings, "dashscope_api_key", "")).strip()
        )

    def _dashscope_rerank_url(self) -> str:
        configured_url = str(getattr(self._settings, "knowledge_rerank_base_url", "")).strip()
        normalized = normalize_base_url(configured_url or DASHSCOPE_RERANK_URL)
        if "/services/rerank/" in normalized or normalized.endswith("/reranks"):
            return normalized
        if normalized.endswith("/api/v1"):
            return f"{normalized}/services/rerank/text-rerank/text-rerank"
        return f"{normalized}/api/v1/services/rerank/text-rerank/text-rerank"

    def _truncate(self, value: str) -> str:
        normalized = value.strip()
        if len(normalized) <= self._max_chars:
            return normalized
        return normalized[: self._max_chars].rstrip()
