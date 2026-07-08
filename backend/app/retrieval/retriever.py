from __future__ import annotations

from sqlalchemy.orm import Session

from app.retrieval.fusion import reciprocal_rank_fusion
from app.retrieval.queries import embed_query, fetch_hits_by_ids, fetch_neighbor_chunks, full_text_search, semantic_search
from app.retrieval.schemas import RetrievedPassage, RetrievalFilters, RetrievalResult, RetrievalSettings


def retrieve_source_passages(
    db: Session,
    query: str,
    filters: RetrievalFilters | None = None,
    retrieval_settings: RetrievalSettings | None = None,
) -> RetrievalResult:
    """Return fused, ranked source passages for a user question."""

    clean_query = query.strip()
    if not clean_query:
        raise ValueError("Retrieval query cannot be empty.")

    filters = filters or RetrievalFilters()
    retrieval_settings = retrieval_settings or RetrievalSettings()

    query_embedding = embed_query(clean_query)
    semantic_hits = semantic_search(db, query_embedding, retrieval_settings.candidate_k, filters)
    full_text_hits = full_text_search(db, clean_query, retrieval_settings.candidate_k, filters)
    fused_hits = reciprocal_rank_fusion([semantic_hits, full_text_hits], k=retrieval_settings.rrf_k)[
        : retrieval_settings.final_k
    ]

    hit_by_id = fetch_hits_by_ids(db, [hit.chunk_id for hit in fused_hits])
    ordered_pairs = [(fused_hit, hit_by_id[fused_hit.chunk_id]) for fused_hit in fused_hits if fused_hit.chunk_id in hit_by_id]
    ordered_hits = [base_hit for _, base_hit in ordered_pairs]
    neighbors = fetch_neighbor_chunks(db, ordered_hits, retrieval_settings.neighbor_window)

    passages = [
        RetrievedPassage(
            chunk_id=base_hit.chunk_id,
            source_document_id=base_hit.source_document_id,
            company=base_hit.company,
            filing_year=base_hit.filing_year,
            filing_type=base_hit.filing_type,
            filing_url=base_hit.filing_url,
            chunk_index=base_hit.chunk_index,
            content=base_hit.content,
            metadata=base_hit.metadata,
            rank=fused_hit.rank,
            fused_score=fused_hit.fused_score,
            semantic_rank=fused_hit.semantic_rank,
            semantic_score=fused_hit.semantic_score,
            full_text_rank=fused_hit.full_text_rank,
            full_text_score=fused_hit.full_text_score,
            neighbor_chunks=neighbors.get(base_hit.chunk_id, []),
        )
        for fused_hit, base_hit in ordered_pairs
    ]

    return RetrievalResult(query=clean_query, passages=passages, settings=retrieval_settings, filters=filters)
