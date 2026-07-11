from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy.orm import Session

from app.assistant.evidence import (
    AnswerPlan,
    EvidenceBrief,
    build_answer_plan,
    build_evidence_brief,
    requested_companies,
    requested_terms,
    requested_years,
)
from app.retrieval import RetrievedPassage, RetrievalFilters, RetrievalResult
from app.retrieval.queries import fetch_neighbor_chunks, full_text_search
from app.retrieval.schemas import SearchHit


FINANCIAL_TERMS = ("revenue", "operating income", "net sales")
DEFAULT_RECOVERY_QUERIES = (
    "Intelligent Cloud Revenue Cost of revenue Operating expenses Operating Income",
    "segment revenue operating income",
    "revenue operating income",
    "net sales revenue",
)


def build_targeted_evidence_queries(question: str, brief: EvidenceBrief) -> list[str]:
    """Build precise full-text queries to recover missing structured evidence."""

    terms = sorted(requested_terms(question))
    years = sorted(requested_years(question))
    gap_values = [gap.value for gap in brief.coverage_gaps]

    query_parts: list[str] = []
    if terms:
        query_parts.extend(terms)
    query_parts.extend(term for term in FINANCIAL_TERMS if term in question.lower())
    if "operating margin" in question.lower() and "operating income" not in query_parts:
        query_parts.append("operating income")
    if not query_parts:
        query_parts.extend(DEFAULT_RECOVERY_QUERIES)

    queries = set()
    base_query = " ".join(query_parts)
    if base_query:
        queries.add(base_query)
    for year in years:
        queries.add(f"{base_query} {year}".strip())
    for gap in gap_values:
        queries.add(f"{base_query} {gap}".strip())
    queries.update(DEFAULT_RECOVERY_QUERIES)

    return [query for query in queries if query]


def _passage_from_hit(hit: SearchHit, rank: int, neighbor_chunks: list[str]) -> RetrievedPassage:
    return RetrievedPassage(
        chunk_id=hit.chunk_id,
        source_document_id=hit.source_document_id,
        company=hit.company,
        filing_year=hit.filing_year,
        filing_type=hit.filing_type,
        filing_url=hit.filing_url,
        chunk_index=hit.chunk_index,
        content=hit.content,
        metadata=hit.metadata,
        rank=rank,
        fused_score=hit.score,
        full_text_rank=hit.rank,
        full_text_score=hit.score,
        neighbor_chunks=neighbor_chunks,
    )


def _merge_passages(base_passages: Sequence[RetrievedPassage], recovered_passages: Sequence[RetrievedPassage]) -> list[RetrievedPassage]:
    merged = list(base_passages)
    seen_ids = {passage.chunk_id for passage in merged}
    for passage in recovered_passages:
        if passage.chunk_id in seen_ids:
            continue
        seen_ids.add(passage.chunk_id)
        merged.append(passage)
    return merged


def recover_structured_evidence(
    db: Session,
    question: str,
    retrieval_result: RetrievalResult,
    brief: EvidenceBrief,
    *,
    limit_per_query: int = 8,
) -> RetrievalResult:
    """Run targeted full-text searches when initial retrieval lacks structured evidence coverage."""

    if not brief.coverage_gaps and brief.rows:
        return retrieval_result

    companies = sorted(requested_companies(question)) or [retrieval_result.filters.company]
    companies = [company for company in companies if company]
    if not companies:
        companies = [None]

    recovered_hits: list[SearchHit] = []
    for company in companies:
        filters = RetrievalFilters(company=company, filing_type=retrieval_result.filters.filing_type)
        for targeted_query in build_targeted_evidence_queries(question, brief):
            recovered_hits.extend(full_text_search(db, targeted_query, limit_per_query, filters))

    if not recovered_hits:
        return retrieval_result

    neighbors = fetch_neighbor_chunks(db, recovered_hits, retrieval_result.settings.neighbor_window)
    recovered_passages = [
        _passage_from_hit(hit, rank=len(retrieval_result.passages) + index, neighbor_chunks=neighbors.get(hit.chunk_id, []))
        for index, hit in enumerate(recovered_hits, start=1)
    ]

    return RetrievalResult(
        query=retrieval_result.query,
        query_plan=retrieval_result.query_plan,
        passages=_merge_passages(retrieval_result.passages, recovered_passages),
        settings=retrieval_result.settings,
        filters=retrieval_result.filters,
    )


def build_recovered_answer_plan(db: Session, question: str, retrieval_result: RetrievalResult) -> tuple[RetrievalResult, AnswerPlan]:
    """Build evidence, retrying targeted full-text recovery once if coverage is missing."""

    brief = build_evidence_brief(question, retrieval_result)
    recovered_result = recover_structured_evidence(db, question, retrieval_result, brief)
    return recovered_result, build_answer_plan(question, recovered_result)
