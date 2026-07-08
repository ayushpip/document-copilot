from uuid import uuid4

from app.retrieval.fusion import reciprocal_rank_fusion
from app.retrieval.schemas import SearchHit


def make_hit(chunk_id=None, rank=1, score=1.0) -> SearchHit:
    return SearchHit(
        chunk_id=chunk_id or uuid4(),
        source_document_id=uuid4(),
        company="AAPL",
        filing_year=2025,
        filing_type="10-K",
        filing_url="https://example.com/aapl",
        chunk_index=rank,
        content="content",
        metadata={},
        rank=rank,
        score=score,
    )


def test_reciprocal_rank_fusion_rewards_items_found_by_both_retrievers() -> None:
    shared = uuid4()
    semantic_only = uuid4()
    full_text_only = uuid4()

    fused = reciprocal_rank_fusion(
        [
            [make_hit(shared, rank=1, score=0.9), make_hit(semantic_only, rank=2, score=0.8)],
            [make_hit(full_text_only, rank=1, score=0.7), make_hit(shared, rank=2, score=0.6)],
        ],
        k=60,
    )

    assert fused[0].chunk_id == shared
    assert fused[0].semantic_rank == 1
    assert fused[0].full_text_rank == 2
    assert len({hit.chunk_id for hit in fused}) == 3


def test_reciprocal_rank_fusion_breaks_ties_deterministically() -> None:
    first = uuid4()
    second = uuid4()

    fused = reciprocal_rank_fusion([[make_hit(second)], [make_hit(first)]], k=60)

    assert [hit.chunk_id for hit in fused] == sorted([first, second], key=str)
