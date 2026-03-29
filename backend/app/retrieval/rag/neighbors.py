from __future__ import annotations

from .types import RagChunk, RetrievalCandidate


def expand_neighbor_chunks(
    *,
    primary_candidates: list[RetrievalCandidate],
    chunks_by_path: dict[str, list[RagChunk]],
    neighbor_window: int,
    limit: int,
) -> list[RagChunk]:
    if neighbor_window <= 0:
        return [candidate.chunk for candidate in primary_candidates[:limit]]

    results: list[RagChunk] = []
    seen_ids: set[str] = set()

    for candidate in primary_candidates:
        if len(results) >= limit:
            break

        sibling_chunks = chunks_by_path.get(candidate.chunk.path, [])
        if not sibling_chunks:
            continue

        anchor_index = candidate.chunk.order
        for offset in range(-neighbor_window, neighbor_window + 1):
            sibling_index = anchor_index + offset
            if sibling_index < 0 or sibling_index >= len(sibling_chunks):
                continue

            chunk = sibling_chunks[sibling_index]
            if chunk.id in seen_ids:
                continue

            seen_ids.add(chunk.id)
            results.append(chunk)
            if len(results) >= limit:
                break

    return results

