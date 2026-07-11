from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from sqlalchemy.orm import Session

from app.config import settings
from app.retrieval import RetrievedPassage, RetrievalFilters, RetrievalResult, RetrievalSettings, retrieve_source_passages


INSTRUCTIONS_PATH = Path(__file__).with_name("instructions.md")


class GroundedCitation(BaseModel):
    """A single claim-to-passage citation produced by the agent."""

    chunk_id: UUID
    claim: str = Field(min_length=1)
    supporting_quote: str = Field(min_length=1)


class GroundedAnswer(BaseModel):
    """Structured answer that can be validated before persistence."""

    answer: str = Field(min_length=1)
    citations: list[GroundedCitation] = Field(default_factory=list)
    not_enough_evidence: bool = False


@dataclass
class DocumentAgentDeps:
    """Dependencies and evidence available to the document agent."""

    db: Session
    retrieval_result: RetrievalResult

    @property
    def allowed_passages(self) -> dict[UUID, RetrievedPassage]:
        return {passage.chunk_id: passage for passage in self.retrieval_result.passages}


def _passage_payload(passage: RetrievedPassage) -> dict:
    return {
        "chunk_id": str(passage.chunk_id),
        "company": passage.company,
        "filing_year": passage.filing_year,
        "filing_type": passage.filing_type,
        "filing_url": passage.filing_url,
        "chunk_index": passage.chunk_index,
        "content": passage.content,
        "neighbor_chunks": passage.neighbor_chunks,
    }


def _merge_retrieved_passages(deps: DocumentAgentDeps, passages: list[RetrievedPassage]) -> None:
    existing_ids = {passage.chunk_id for passage in deps.retrieval_result.passages}
    deps.retrieval_result.passages.extend(passage for passage in passages if passage.chunk_id not in existing_ids)


def _load_instructions() -> str:
    return INSTRUCTIONS_PATH.read_text(encoding="utf-8")


def search_filings(
    ctx: RunContext[DocumentAgentDeps],
    query: str,
    company: str | None = None,
    filing_year: int | None = None,
    filing_type: str | None = None,
) -> list[dict]:
    """Search filings for passages relevant to a specific sub-question."""

    result = retrieve_source_passages(
        ctx.deps.db,
        query,
        filters=RetrievalFilters(company=company, filing_year=filing_year, filing_type=filing_type),
        retrieval_settings=RetrievalSettings(candidate_k=25, final_k=5, neighbor_window=1),
    )
    _merge_retrieved_passages(ctx.deps, result.passages)
    return [_passage_payload(passage) for passage in result.passages]


def read_chunk(ctx: RunContext[DocumentAgentDeps], chunk_id: UUID) -> dict | None:
    """Read one of the retrieved evidence chunks by ID."""

    passage = ctx.deps.allowed_passages.get(chunk_id)
    return _passage_payload(passage) if passage else None


def read_surrounding_chunks(ctx: RunContext[DocumentAgentDeps], chunk_id: UUID) -> list[str]:
    """Read neighboring chunk text for one of the retrieved evidence chunks."""

    passage = ctx.deps.allowed_passages.get(chunk_id)
    return passage.neighbor_chunks if passage else []


def _openai_model_name() -> str:
    return settings.openai_chat_model.removeprefix("openai:")


def create_document_agent() -> Agent[DocumentAgentDeps, GroundedAnswer]:
    model = OpenAIChatModel(_openai_model_name(), provider=OpenAIProvider(api_key=settings.openai_api_key))
    return Agent(
        model,
        output_type=GroundedAnswer,
        deps_type=DocumentAgentDeps,
        system_prompt=_load_instructions(),
        tools=[search_filings, read_chunk, read_surrounding_chunks],
    )


def build_agent_prompt(question: str, retrieval_result: RetrievalResult) -> str:
    passages = "\n\n".join(
        (
            f"Passage {passage.rank}\n"
            f"chunk_id: {passage.chunk_id}\n"
            f"source: {passage.company} {passage.filing_type} {passage.filing_year}, chunk {passage.chunk_index}\n"
            f"content:\n{passage.content}"
        )
        for passage in retrieval_result.passages
    )
    return (
        f"Question:\n{question.strip()}\n\n"
        "Retrieved evidence passages:\n"
        f"{passages or 'No passages retrieved.'}\n\n"
        "Answer using only this evidence. Return the structured GroundedAnswer output."
    )


def run_document_agent(question: str, deps: DocumentAgentDeps) -> GroundedAnswer:
    document_agent = create_document_agent()
    result = document_agent.run_sync(build_agent_prompt(question, deps.retrieval_result), deps=deps)
    return result.output


async def run_document_agent_async(question: str, deps: DocumentAgentDeps) -> GroundedAnswer:
    document_agent = create_document_agent()
    result = await document_agent.run(build_agent_prompt(question, deps.retrieval_result), deps=deps)
    return result.output
