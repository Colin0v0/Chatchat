from __future__ import annotations

from .text import tokenize_text
from .types import RetrievalCandidate


class LexicalReranker:
    def __init__(self, rerank_window: int = 12):
        self._rerank_window = max(1, rerank_window)

    def rerank(self, *, query: str, candidates: list[RetrievalCandidate]) -> list[RetrievalCandidate]:
        query_text = query.strip().lower()
        if not query_text or not candidates:
            return self._finalize(candidates)

        query_tokens = tokenize_text(query_text)
        reranked: list[RetrievalCandidate] = []
        for index, candidate in enumerate(candidates):
            if index >= self._rerank_window:
                candidate.rerank_score = 0.0
                candidate.final_score = candidate.hybrid_score
                reranked.append(candidate)
                continue

            heading_text = candidate.chunk.heading.lower()
            path_text = candidate.chunk.path.lower()
            content_text = candidate.chunk.content.lower()
            tag_tokens = [tag.lower() for tag in candidate.chunk.tags]

            bonus = 0.0
            if query_text in heading_text:
                bonus += 0.22
            elif query_text in path_text:
                bonus += 0.16
            elif query_text in content_text:
                bonus += 0.1

            bonus += 0.18 * _coverage_ratio(query_tokens, tokenize_text(heading_text))
            bonus += 0.12 * _coverage_ratio(query_tokens, tokenize_text(path_text))
            bonus += 0.1 * _coverage_ratio(query_tokens, tokenize_text(content_text))
            bonus += 0.14 * _coverage_ratio(query_tokens, tag_tokens)

            candidate.rerank_score = bonus
            candidate.final_score = candidate.hybrid_score + bonus
            reranked.append(candidate)

        reranked.sort(key=lambda item: item.final_score, reverse=True)
        return reranked

    def _finalize(self, candidates: list[RetrievalCandidate]) -> list[RetrievalCandidate]:
        for candidate in candidates:
            candidate.rerank_score = 0.0
            candidate.final_score = candidate.hybrid_score
        return candidates


def _coverage_ratio(query_tokens: list[str], field_tokens: list[str]) -> float:
    if not query_tokens or not field_tokens:
        return 0.0

    field_token_set = set(field_tokens)
    matched = sum(1 for token in query_tokens if token in field_token_set)
    return matched / len(query_tokens)

