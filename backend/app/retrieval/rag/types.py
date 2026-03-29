from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RagChunk:
    id: str
    path: str
    directory: str
    heading: str
    content: str
    order: int
    embedding: list[float]
    tags: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class MarkdownDocument:
    path: str
    content: str
    signature: str


@dataclass(frozen=True)
class RagChunkSpec:
    id: str
    path: str
    directory: str
    heading: str
    content: str
    order: int
    tags: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class QueryFilters:
    cleaned_query: str
    folders: tuple[str, ...] = ()
    paths: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()


@dataclass
class RetrievalCandidate:
    chunk: RagChunk
    vector_score: float
    keyword_score: float
    hybrid_score: float
    rerank_score: float = 0.0
    final_score: float = 0.0


@dataclass(frozen=True)
class RagContextPayload:
    context_message: dict[str, str] | None
    sources: list[dict[str, str | float]]
    should_refuse: bool = False
    refusal_message: str | None = None
