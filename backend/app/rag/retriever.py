from __future__ import annotations

import math
from collections import Counter

from .query_filters import chunk_matches_filters
from .text import tokenize_text
from .types import QueryFilters, RagChunk, RetrievalCandidate


def cosine_similarity(vector_a: list[float], vector_b: list[float]) -> float:
    if len(vector_a) != len(vector_b):
        return 0.0

    dot = sum(left * right for left, right in zip(vector_a, vector_b, strict=False))
    norm_a = math.sqrt(sum(value * value for value in vector_a))
    norm_b = math.sqrt(sum(value * value for value in vector_b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class HybridRetriever:
    def __init__(self, bm25_k1: float = 1.2, bm25_b: float = 0.75, vector_weight: float = 0.72):
        self._bm25_k1 = bm25_k1
        self._bm25_b = bm25_b
        self._vector_weight = vector_weight

        self._chunks: list[RagChunk] = []
        self._token_counts: list[Counter[str]] = []
        self._doc_lengths: list[int] = []
        self._avg_doc_length = 0.0
        self._idf: dict[str, float] = {}

    def set_chunks(self, chunks: list[RagChunk]) -> None:
        self._chunks = chunks
        self._token_counts = []
        self._doc_lengths = []

        doc_frequency: Counter[str] = Counter()
        for chunk in chunks:
            tokens = tokenize_text(self._chunk_text(chunk))
            token_counter = Counter(tokens)
            self._token_counts.append(token_counter)
            self._doc_lengths.append(sum(token_counter.values()))
            for token in token_counter:
                doc_frequency[token] += 1

        if self._doc_lengths:
            self._avg_doc_length = sum(self._doc_lengths) / len(self._doc_lengths)
        else:
            self._avg_doc_length = 0.0

        doc_count = len(chunks)
        self._idf = {
            token: math.log(1 + (doc_count - df + 0.5) / (df + 0.5))
            for token, df in doc_frequency.items()
        }

    def retrieve(
        self,
        *,
        query_filters: QueryFilters,
        query_embedding: list[float],
        top_k: int,
        candidate_limit: int,
    ) -> list[RetrievalCandidate]:
        if not self._chunks:
            return []

        top_k = max(1, top_k)
        candidate_limit = max(top_k, candidate_limit)
        candidate_indices = [
            index
            for index, chunk in enumerate(self._chunks)
            if chunk_matches_filters(chunk, query_filters)
        ]
        if not candidate_indices:
            return []

        vector_scores = [
            cosine_similarity(query_embedding, self._chunks[index].embedding)
            for index in candidate_indices
        ]
        keyword_scores = self._bm25_scores(query_filters.cleaned_query, candidate_indices)
        vector_normalized = self._min_max_normalize(vector_scores)
        keyword_normalized = self._min_max_normalize(keyword_scores)

        candidates: list[RetrievalCandidate] = []
        for local_index, chunk_index in enumerate(candidate_indices):
            hybrid_score = (
                self._vector_weight * vector_normalized[local_index]
                + (1.0 - self._vector_weight) * keyword_normalized[local_index]
            )
            candidates.append(
                RetrievalCandidate(
                    chunk=self._chunks[chunk_index],
                    vector_score=vector_normalized[local_index],
                    keyword_score=keyword_normalized[local_index],
                    hybrid_score=hybrid_score,
                    final_score=hybrid_score,
                )
            )

        candidates.sort(key=lambda item: item.hybrid_score, reverse=True)
        return candidates[:candidate_limit]

    def _bm25_scores(self, query: str, candidate_indices: list[int]) -> list[float]:
        query_tokens = tokenize_text(query)
        if not query_tokens or not candidate_indices:
            return [0.0 for _ in candidate_indices]

        scores: list[float] = []
        for index in candidate_indices:
            token_counter = self._token_counts[index]
            doc_length = self._doc_lengths[index] or 1
            score = 0.0
            for token in query_tokens:
                tf = token_counter.get(token, 0)
                if tf <= 0:
                    continue

                idf = self._idf.get(token, 0.0)
                denominator = tf + self._bm25_k1 * (
                    1 - self._bm25_b + self._bm25_b * (doc_length / (self._avg_doc_length or 1))
                )
                score += idf * ((tf * (self._bm25_k1 + 1)) / denominator)
            scores.append(score)
        return scores

    def _chunk_text(self, chunk: RagChunk) -> str:
        return "\n".join(
            [
                chunk.path,
                chunk.directory,
                " ".join(chunk.tags),
                chunk.heading,
                chunk.content,
            ]
        )

    def _min_max_normalize(self, values: list[float]) -> list[float]:
        if not values:
            return []
        min_value = min(values)
        max_value = max(values)
        if math.isclose(min_value, max_value):
            if max_value <= 0:
                return [0.0 for _ in values]
            if 0.0 <= max_value <= 1.0:
                return [max_value for _ in values]
            return [1.0 for _ in values]
        scale = max_value - min_value
        return [(value - min_value) / scale for value in values]
