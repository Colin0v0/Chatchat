from __future__ import annotations

from typing import Protocol

from ..types import WebQuery, WebSearchResult


class WebSearchProvider(Protocol):
    async def search(self, query: WebQuery) -> list[WebSearchResult]: ...
