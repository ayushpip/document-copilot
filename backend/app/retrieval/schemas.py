from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RetrievalSettings(BaseModel):
    """Tunable retrieval settings with conservative defaults."""

    candidate_k: int = Field(default=50, ge=1)
    final_k: int = Field(default=10, ge=1)
    rrf_k: int = Field(default=60, ge=1)
    neighbor_window: int = Field(default=1, ge=0)


class RetrievalFilters(BaseModel):
    """Optional filing filters for retrieval queries."""

    company: str | None = None
    filing_year: int | None = None
    filing_type: str | None = None


class RetrievalQueryPlan(BaseModel):
    """LLM-planned retrieval queries and optional inferred filters."""

    original_query: str
    semantic_query: str
    full_text_query: str
    keywords: list[str] = Field(default_factory=list)
    companies: list[str] = Field(default_factory=list)
    filing_years: list[int] = Field(default_factory=list)
    filing_type: str | None = None


class SearchHit(BaseModel):
    """Single ranked hit from one retrieval backend."""

    model_config = ConfigDict(from_attributes=True)

    chunk_id: UUID
    source_document_id: UUID
    company: str
    filing_year: int
    filing_type: str
    filing_url: str | None
    chunk_index: int
    content: str
    metadata: dict
    rank: int
    score: float


class FusedHit(BaseModel):
    """Chunk ranked by reciprocal rank fusion."""

    chunk_id: UUID
    rank: int
    fused_score: float
    semantic_rank: int | None = None
    semantic_score: float | None = None
    full_text_rank: int | None = None
    full_text_score: float | None = None


class RetrievedPassage(BaseModel):
    """Ranked source passage returned to answer-generation layers."""

    chunk_id: UUID
    source_document_id: UUID
    company: str
    filing_year: int
    filing_type: str
    filing_url: str | None
    chunk_index: int
    content: str
    metadata: dict
    rank: int
    fused_score: float
    semantic_rank: int | None = None
    semantic_score: float | None = None
    full_text_rank: int | None = None
    full_text_score: float | None = None
    neighbor_chunks: list[str] = Field(default_factory=list)


class RetrievalResult(BaseModel):
    """Complete retrieval response for one user query."""

    query: str
    query_plan: RetrievalQueryPlan | None = None
    passages: list[RetrievedPassage]
    settings: RetrievalSettings
    filters: RetrievalFilters
