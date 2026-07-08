from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from uuid import UUID

from app.retrieval.schemas import FusedHit, SearchHit


def reciprocal_rank_fusion(
    ranked_lists: Sequence[Sequence[SearchHit]],
    k: int = 60,
) -> list[FusedHit]:
    """Fuse ranked chunk IDs using ranks, not backend-specific scores."""

    scores: dict[UUID, float] = defaultdict(float)
    semantic_by_id: dict[UUID, tuple[int, float]] = {}
    full_text_by_id: dict[UUID, tuple[int, float]] = {}

    for list_index, ranking in enumerate(ranked_lists):
        for rank, hit in enumerate(ranking, start=1):
            scores[hit.chunk_id] += 1.0 / (k + rank)
            if list_index == 0:
                semantic_by_id[hit.chunk_id] = (rank, hit.score)
            elif list_index == 1:
                full_text_by_id[hit.chunk_id] = (rank, hit.score)

    fused = sorted(scores.items(), key=lambda item: (-item[1], str(item[0])))
    return [
        FusedHit(
            chunk_id=chunk_id,
            rank=rank,
            fused_score=score,
            semantic_rank=semantic_by_id[chunk_id][0] if chunk_id in semantic_by_id else None,
            semantic_score=semantic_by_id[chunk_id][1] if chunk_id in semantic_by_id else None,
            full_text_rank=full_text_by_id[chunk_id][0] if chunk_id in full_text_by_id else None,
            full_text_score=full_text_by_id[chunk_id][1] if chunk_id in full_text_by_id else None,
        )
        for rank, (chunk_id, score) in enumerate(fused, start=1)
    ]
