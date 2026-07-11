from uuid import uuid4

from app.assistant.evidence import build_evidence_brief
from app.assistant.evidence_retrieval import build_targeted_evidence_queries, recover_structured_evidence
from app.retrieval import RetrievedPassage, RetrievalFilters, RetrievalResult, RetrievalSettings
from app.retrieval.schemas import SearchHit


def make_result(content: str = "No structured table here.") -> RetrievalResult:
    return RetrievalResult(
        query="Compare Microsoft Intelligent Cloud revenue and operating income from 2022-2025.",
        passages=[
            RetrievedPassage(
                chunk_id=uuid4(),
                source_document_id=uuid4(),
                company="MSFT",
                filing_year=2025,
                filing_type="10-K",
                filing_url=None,
                chunk_index=1,
                content=content,
                metadata={},
                rank=1,
                fused_score=0.1,
            )
        ],
        settings=RetrievalSettings(neighbor_window=1),
        filters=RetrievalFilters(company="MSFT"),
    )


def test_build_targeted_evidence_queries_uses_requested_terms_and_years() -> None:
    result = make_result()
    brief = build_evidence_brief(result.query, result)

    queries = build_targeted_evidence_queries(result.query, brief)

    assert any("intelligent cloud" in query for query in queries)
    assert any("2022" in query for query in queries)
    assert "segment revenue operating income" not in queries


def test_build_targeted_evidence_queries_uses_defaults_without_specific_terms() -> None:
    result = make_result()
    brief = build_evidence_brief("Compare financial performance.", result)

    queries = build_targeted_evidence_queries("Compare financial performance.", brief)

    assert "segment revenue operating income" in queries


def test_recover_structured_evidence_merges_full_text_hits(monkeypatch) -> None:
    result = make_result()
    brief = build_evidence_brief(result.query, result)
    recovered_chunk_id = uuid4()
    recovered_source_document_id = uuid4()

    def fake_full_text_search(db, query, limit, filters):
        if filters.company != "MSFT":
            return []
        return [
            SearchHit(
                chunk_id=recovered_chunk_id,
                source_document_id=recovered_source_document_id,
                company="MSFT",
                filing_year=2025,
                filing_type="10-K",
                filing_url=None,
                chunk_index=84,
                content=(
                    "|  | 2025 | 2024 | 2023 |\n"
                    "| --- | --- | --- | --- |\n"
                    "| Intelligent Cloud |  |  |  |\n"
                    "| Revenue | 106,265 | 87,464 | 72,944 |\n"
                    "| Operating Income | 44,589 | 37,813 | 28,411 |"
                ),
                metadata={},
                rank=1,
                score=0.5,
            )
        ]

    def fake_fetch_neighbor_chunks(db, hits, window):
        return {recovered_chunk_id: []}

    monkeypatch.setattr("app.assistant.evidence_retrieval.full_text_search", fake_full_text_search)
    monkeypatch.setattr("app.assistant.evidence_retrieval.fetch_neighbor_chunks", fake_fetch_neighbor_chunks)

    recovered = recover_structured_evidence(object(), result.query, result, brief)

    assert len(recovered.passages) == 2
    assert recovered.passages[1].chunk_id == recovered_chunk_id
