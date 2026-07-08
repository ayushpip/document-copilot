from uuid import uuid4

from app.retrieval import retriever
from app.retrieval.schemas import RetrievalFilters, RetrievalSettings, SearchHit


def make_hit(chunk_id=None, source_document_id=None, chunk_index=0, rank=1) -> SearchHit:
    return SearchHit(
        chunk_id=chunk_id or uuid4(),
        source_document_id=source_document_id or uuid4(),
        company="AAPL",
        filing_year=2025,
        filing_type="10-K",
        filing_url="https://example.com/aapl",
        chunk_index=chunk_index,
        content=f"chunk {chunk_index}",
        metadata={"section": "MD&A"},
        rank=rank,
        score=1.0,
    )


def test_retrieve_source_passages_orchestrates_hybrid_retrieval(monkeypatch) -> None:
    shared_id = uuid4()
    source_document_id = uuid4()
    shared = make_hit(shared_id, source_document_id, chunk_index=10, rank=1)
    semantic_only = make_hit(source_document_id=source_document_id, chunk_index=11, rank=2)
    full_text_only = make_hit(source_document_id=source_document_id, chunk_index=12, rank=2)
    hit_by_id = {hit.chunk_id: hit for hit in [shared, semantic_only, full_text_only]}
    calls = {}

    def fake_embed_query(query):
        calls["embed_query"] = query
        return [0.1, 0.2, 0.3]

    def fake_semantic_search(db, query_embedding, limit, filters):
        calls["semantic"] = (query_embedding, limit, filters)
        return [shared, semantic_only]

    def fake_full_text_search(db, query, limit, filters):
        calls["full_text"] = (query, limit, filters)
        return [full_text_only, shared]

    def fake_fetch_hits_by_ids(db, chunk_ids):
        calls["chunk_ids"] = chunk_ids
        return {chunk_id: hit_by_id[chunk_id] for chunk_id in chunk_ids}

    def fake_fetch_neighbor_chunks(db, hits, window):
        calls["neighbors"] = (hits, window)
        return {hit.chunk_id: [f"neighbor for {hit.chunk_index}"] for hit in hits}

    monkeypatch.setattr(retriever, "embed_query", fake_embed_query)
    monkeypatch.setattr(retriever, "semantic_search", fake_semantic_search)
    monkeypatch.setattr(retriever, "full_text_search", fake_full_text_search)
    monkeypatch.setattr(retriever, "fetch_hits_by_ids", fake_fetch_hits_by_ids)
    monkeypatch.setattr(retriever, "fetch_neighbor_chunks", fake_fetch_neighbor_chunks)

    result = retriever.retrieve_source_passages(
        db=object(),
        query="  Apple revenue mix  ",
        filters=RetrievalFilters(company="AAPL"),
        retrieval_settings=RetrievalSettings(candidate_k=2, final_k=2, neighbor_window=1),
    )

    assert result.query == "Apple revenue mix"
    assert len(result.passages) == 2
    assert result.passages[0].chunk_id == shared_id
    assert result.passages[0].semantic_rank == 1
    assert result.passages[0].full_text_rank == 2
    assert result.passages[0].neighbor_chunks == ["neighbor for 10"]
    assert calls["semantic"][1] == 2
    assert calls["full_text"][0] == "Apple revenue mix"
    assert calls["neighbors"][1] == 1
