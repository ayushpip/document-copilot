from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from openai import OpenAI
from sqlalchemy import Select, bindparam, func, literal, select
from sqlalchemy.orm import Session

from app.config import settings
from app.database.models import DocumentChunk, SourceDocument
from app.retrieval.schemas import RetrievalFilters, SearchHit


def embed_query(query: str) -> list[float]:
    """Embed a retrieval query with the configured OpenAI embedding model."""

    client = OpenAI(api_key=settings.openai_api_key)
    response = client.embeddings.create(
        model=settings.openai_embedding_model,
        input=query,
        dimensions=settings.openai_embedding_dimensions,
    )
    return response.data[0].embedding


def _base_hit_columns(score):
    return (
        DocumentChunk.id.label("chunk_id"),
        DocumentChunk.source_document_id.label("source_document_id"),
        SourceDocument.company.label("company"),
        SourceDocument.filing_year.label("filing_year"),
        SourceDocument.filing_type.label("filing_type"),
        SourceDocument.filing_url.label("filing_url"),
        DocumentChunk.chunk_index.label("chunk_index"),
        DocumentChunk.content.label("content"),
        DocumentChunk.chunk_metadata.label("metadata"),
        score.label("score"),
    )


def _apply_filters(statement: Select, filters: RetrievalFilters | None) -> Select:
    if filters is None:
        return statement
    if filters.company:
        statement = statement.where(SourceDocument.company == filters.company.upper())
    if filters.filing_year:
        statement = statement.where(SourceDocument.filing_year == filters.filing_year)
    if filters.filing_type:
        statement = statement.where(SourceDocument.filing_type == filters.filing_type.upper())
    return statement


def semantic_search_statement(
    query_embedding: Sequence[float],
    limit: int,
    filters: RetrievalFilters | None = None,
) -> Select:
    distance = DocumentChunk.embedding.cosine_distance(bindparam("query_embedding", value=query_embedding))
    score = literal(1.0) - distance
    statement = (
        select(*_base_hit_columns(score))
        .join(SourceDocument, SourceDocument.id == DocumentChunk.source_document_id)
        .where(DocumentChunk.embedding.is_not(None))
        .order_by(distance)
        .limit(limit)
    )
    return _apply_filters(statement, filters)


def full_text_search_statement(query: str, limit: int, filters: RetrievalFilters | None = None) -> Select:
    text_query = func.websearch_to_tsquery("english", bindparam("query", value=query))
    score = func.ts_rank_cd(DocumentChunk.search_vector, text_query)
    statement = (
        select(*_base_hit_columns(score))
        .join(SourceDocument, SourceDocument.id == DocumentChunk.source_document_id)
        .where(DocumentChunk.search_vector.op("@@")(text_query))
        .order_by(score.desc())
        .limit(limit)
    )
    return _apply_filters(statement, filters)


def _rows_to_hits(rows) -> list[SearchHit]:
    return [
        SearchHit(
            chunk_id=row.chunk_id,
            source_document_id=row.source_document_id,
            company=row.company,
            filing_year=row.filing_year,
            filing_type=row.filing_type,
            filing_url=row.filing_url,
            chunk_index=row.chunk_index,
            content=row.content,
            metadata=row.metadata or {},
            rank=index,
            score=float(row.score or 0),
        )
        for index, row in enumerate(rows, start=1)
    ]


def semantic_search(
    db: Session,
    query_embedding: Sequence[float],
    limit: int,
    filters: RetrievalFilters | None = None,
) -> list[SearchHit]:
    rows = db.execute(semantic_search_statement(query_embedding, limit, filters)).all()
    return _rows_to_hits(rows)


def full_text_search(
    db: Session,
    query: str,
    limit: int,
    filters: RetrievalFilters | None = None,
) -> list[SearchHit]:
    rows = db.execute(full_text_search_statement(query, limit, filters)).all()
    return _rows_to_hits(rows)


def fetch_hits_by_ids(db: Session, chunk_ids: Sequence[UUID]) -> dict[UUID, SearchHit]:
    if not chunk_ids:
        return {}
    statement = (
        select(
            DocumentChunk.id.label("chunk_id"),
            DocumentChunk.source_document_id.label("source_document_id"),
            SourceDocument.company.label("company"),
            SourceDocument.filing_year.label("filing_year"),
            SourceDocument.filing_type.label("filing_type"),
            SourceDocument.filing_url.label("filing_url"),
            DocumentChunk.chunk_index.label("chunk_index"),
            DocumentChunk.content.label("content"),
            DocumentChunk.chunk_metadata.label("metadata"),
            literal(0.0).label("score"),
        )
        .join(SourceDocument, SourceDocument.id == DocumentChunk.source_document_id)
        .where(DocumentChunk.id.in_(chunk_ids))
    )
    return {hit.chunk_id: hit for hit in _rows_to_hits(db.execute(statement).all())}


def fetch_neighbor_chunks(db: Session, hits: Sequence[SearchHit], window: int) -> dict[UUID, list[str]]:
    if not hits or window <= 0:
        return {hit.chunk_id: [] for hit in hits}

    neighbors: dict[UUID, list[str]] = {}
    for hit in hits:
        statement = (
            select(DocumentChunk.content)
            .where(DocumentChunk.source_document_id == hit.source_document_id)
            .where(DocumentChunk.chunk_index >= hit.chunk_index - window)
            .where(DocumentChunk.chunk_index <= hit.chunk_index + window)
            .where(DocumentChunk.id != hit.chunk_id)
            .order_by(DocumentChunk.chunk_index)
        )
        neighbors[hit.chunk_id] = list(db.scalars(statement))
    return neighbors
