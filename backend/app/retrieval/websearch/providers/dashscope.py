from __future__ import annotations

import re
from urllib.parse import urlparse, urlunparse

import httpx

from ....core.config import Settings
from ....core.http import limited_request, shared_http_clients
from ....llm.capabilities import normalize_base_url
from ..types import WebQuery, WebSearchResult

DASHSCOPE_GENERATION_URL = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"
REFERENCE_PATTERN_TEMPLATE = r"(?:\[ref_{index}\]|\[{index}\])"


class DashScopeWebSearchProvider:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._base_url, self._endpoint_path = _split_endpoint_url(_dashscope_generation_url(settings))
        self._api_key = str(getattr(settings, "web_search_api_key", "")).strip() or str(
            getattr(settings, "dashscope_api_key", ""),
        ).strip()
        self._timeout = httpx.Timeout(settings.web_search_timeout_seconds, connect=10.0)
        self._max_results = max(1, settings.web_search_max_results)
        self._model = str(getattr(settings, "web_search_model", "qwen-plus")).strip() or "qwen-plus"
        self._strategy = str(getattr(settings, "web_search_strategy", "turbo")).strip().lower() or "turbo"
        self._forced_search = bool(getattr(settings, "web_search_forced", True))
        self._enable_source = bool(getattr(settings, "web_search_enable_source", True))
        self._enable_citation = bool(getattr(settings, "web_search_enable_citation", True))
        self._citation_format = str(getattr(settings, "web_search_citation_format", "[ref_<number>]")).strip()

    @property
    def configured(self) -> bool:
        return bool(self._api_key and self._model)

    async def search(self, query: WebQuery) -> list[WebSearchResult]:
        if not self.configured or not query.cleaned_query:
            return []

        payload = self._build_request_payload(query)
        async with limited_request(
            gate="web_search",
            max_concurrency=self._settings.web_search_http_max_concurrency,
        ):
            client = await shared_http_clients.get_client(
                base_url=self._base_url,
                timeout=self._timeout,
                limits=httpx.Limits(
                    max_connections=max(1, self._settings.http_pool_max_connections),
                    max_keepalive_connections=max(1, self._settings.http_pool_max_keepalive_connections),
                ),
            )
            response = await client.post(self._endpoint_path, headers=self._headers(), json=payload)
            if response.is_error:
                raise RuntimeError(_build_error_message(response))

        return self._parse_response(response.json())

    def _build_request_payload(self, query: WebQuery) -> dict[str, object]:
        prompt = _build_search_prompt(query.cleaned_query)
        search_options: dict[str, object] = {
            "enable_source": self._enable_source,
            "enable_citation": self._enable_citation,
            "forced_search": self._forced_search,
            "search_strategy": self._strategy,
        }
        if self._citation_format:
            search_options["citation_format"] = self._citation_format
        if query.include_domains:
            search_options["assigned_site_list"] = list(query.include_domains[:25])

        return {
            "model": self._model,
            "input": {
                "messages": [
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ]
            },
            "parameters": {
                "result_format": "message",
                "enable_search": True,
                "search_options": search_options,
            },
        }

    def _headers(self) -> dict[str, str]:
        if not self._api_key:
            raise RuntimeError("WEB_SEARCH_API_KEY or DASHSCOPE_API_KEY is required for DashScope web search.")
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    def _parse_response(self, payload: object) -> list[WebSearchResult]:
        if not isinstance(payload, dict):
            raise RuntimeError("DashScope web search returned a non-object response.")

        answer = _extract_answer_text(payload)
        search_results = _extract_search_results(payload)
        results: list[WebSearchResult] = []
        for position, item in enumerate(search_results):
            if not isinstance(item, dict):
                continue
            url = str(item.get("url", "")).strip()
            title = str(item.get("title", "")).strip()
            if not url or not title:
                continue

            source_index = _parse_index(item.get("index"), fallback=position + 1)
            excerpt = (
                _first_text_field(item, ("snippet", "summary", "content", "description"))
                or _excerpt_for_source(answer, source_index)
                or title
            )
            results.append(
                WebSearchResult(
                    title=title,
                    url=url,
                    domain=_domain_from_url(url, site_name=str(item.get("site_name", "")).strip()),
                    excerpt=excerpt,
                    content=excerpt or answer,
                    provider_score=_provider_score(item, position=position, total=len(search_results)),
                    published_at=_first_text_field(item, ("published_at", "published_date", "publish_time", "date")),
                )
            )
            if len(results) >= self._max_results:
                break
        return results


def _build_search_prompt(query: str) -> str:
    return (
        "请联网搜索并整理与用户问题最相关的事实。"
        "要求：只保留可由搜索来源支持的信息，尽量简洁；重要事实后保留来源角标；不要编造来源。"
        f"\n\n用户问题：{query.strip()}"
    )


def _extract_search_results(payload: dict[str, object]) -> list[object]:
    output = payload.get("output")
    if isinstance(output, dict):
        search_info = output.get("search_info")
        if isinstance(search_info, dict):
            raw_results = search_info.get("search_results")
            if isinstance(raw_results, list):
                return raw_results
    return []


def _extract_answer_text(payload: dict[str, object]) -> str:
    output = payload.get("output")
    if not isinstance(output, dict):
        return ""

    raw_text = output.get("text")
    if isinstance(raw_text, str) and raw_text.strip():
        return raw_text.strip()

    choices = output.get("choices")
    if not isinstance(choices, list):
        return ""
    for choice in choices:
        if not isinstance(choice, dict):
            continue
        message = choice.get("message")
        if not isinstance(message, dict):
            continue
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return content.strip()
    return ""


def _excerpt_for_source(answer: str, source_index: int) -> str:
    if not answer.strip() or source_index <= 0:
        return ""
    reference_pattern = REFERENCE_PATTERN_TEMPLATE.format(index=re.escape(str(source_index)))
    parts = re.split(r"(?<=[。！？.!?])\s+|\n+", answer.strip())
    for part in parts:
        if re.search(reference_pattern, part):
            return part.strip()
    match = re.search(reference_pattern, answer)
    if not match:
        return ""
    start = max(0, answer.rfind("。", 0, match.start()) + 1, answer.rfind("\n", 0, match.start()) + 1)
    end_candidates = [index for index in (answer.find("。", match.end()), answer.find("\n", match.end())) if index >= 0]
    end = min(end_candidates) + 1 if end_candidates else min(len(answer), match.end() + 220)
    return answer[start:end].strip()


def _first_text_field(item: dict[str, object], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _parse_index(value: object, *, fallback: int) -> int:
    if isinstance(value, bool):
        return fallback
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return fallback
    return parsed if parsed > 0 else fallback


def _provider_score(item: dict[str, object], *, position: int, total: int) -> float:
    raw_score = item.get("score")
    if not isinstance(raw_score, bool):
        try:
            return max(0.0, min(1.0, float(raw_score)))
        except (TypeError, ValueError):
            pass

    denominator = max(total, 1)
    return max(0.05, min(1.0, 1.0 - (position / denominator)))


def _build_error_message(response: httpx.Response) -> str:
    status = response.status_code
    reason = response.reason_phrase or "HTTP error"
    content_type = response.headers.get("content-type", "")

    if "application/json" in content_type:
        try:
            payload = response.json()
        except ValueError:
            return f"DashScope web search request failed: {status} {reason}."
        detail = None
        if isinstance(payload, dict):
            error = payload.get("error")
            if isinstance(error, dict):
                detail = error.get("message") or error.get("code")
            detail = detail or payload.get("message") or payload.get("code")
        if isinstance(detail, str) and detail.strip():
            return f"DashScope web search request failed: {status} {detail.strip()}."

    return f"DashScope web search request failed: {status} {reason}."


def _dashscope_generation_url(settings: Settings) -> str:
    configured = str(getattr(settings, "web_search_base_url", "")).strip()
    normalized = normalize_base_url(configured or DASHSCOPE_GENERATION_URL)
    if _is_plain_non_dashscope_root(normalized):
        normalized = DASHSCOPE_GENERATION_URL
    parsed = urlparse(normalized)
    path = parsed.path.rstrip("/")
    if path.endswith("/api/v1/services/aigc/text-generation/generation"):
        return normalized
    if path.endswith("/compatible-mode/v1"):
        return urlunparse(parsed._replace(path="/api/v1/services/aigc/text-generation/generation"))
    if path.endswith("/api/v1"):
        return f"{normalized}/services/aigc/text-generation/generation"
    if path in {"", "/"}:
        return f"{normalized}/api/v1/services/aigc/text-generation/generation"
    return normalized


def _split_endpoint_url(url: str) -> tuple[str, str]:
    parsed = urlparse(url)
    base_url = urlunparse((parsed.scheme, parsed.netloc, "", "", "", ""))
    path = parsed.path or "/"
    if parsed.query:
        path = f"{path}?{parsed.query}"
    return base_url.rstrip("/"), path


def _is_plain_non_dashscope_root(url: str) -> bool:
    parsed = urlparse(url)
    path = parsed.path.rstrip("/")
    return parsed.netloc.lower() != "dashscope.aliyuncs.com" and path in {"", "/"}


def _domain_from_url(url: str, *, site_name: str = "") -> str:
    parsed = urlparse(url)
    return parsed.netloc.lower() or site_name.lower()
