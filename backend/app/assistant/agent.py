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
from app.assistant.evidence import AnswerPlan, EvidenceBrief, format_answer_plan, format_evidence_brief
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
    evidence_brief: EvidenceBrief | None = None
    answer_plan: AnswerPlan | None = None

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


def calculate_growth_percentage(current_value: float, previous_value: float) -> dict:
    """Calculate percentage growth from a previous value to a current value."""

    if previous_value == 0:
        return {"error": "Cannot calculate growth from a zero previous value."}

    growth = ((current_value - previous_value) / previous_value) * 100
    return {
        "current_value": current_value,
        "previous_value": previous_value,
        "growth_percentage": round(growth, 1),
    }


def calculate_margin_percentage(numerator: float, denominator: float) -> dict:
    """Calculate a margin percentage as numerator divided by denominator."""

    if denominator == 0:
        return {"error": "Cannot calculate margin with a zero denominator."}

    margin = (numerator / denominator) * 100
    return {
        "numerator": numerator,
        "denominator": denominator,
        "margin_percentage": round(margin, 1),
    }


def _openai_model_name() -> str:
    return settings.openai_chat_model.removeprefix("openai:")


def create_document_agent() -> Agent[DocumentAgentDeps, GroundedAnswer]:
    model = OpenAIChatModel(_openai_model_name(), provider=OpenAIProvider(api_key=settings.openai_api_key))
    return Agent(
        model,
        output_type=GroundedAnswer,
        deps_type=DocumentAgentDeps,
        system_prompt=_load_instructions(),
        tools=[
            search_filings,
            read_chunk,
            read_surrounding_chunks,
            calculate_growth_percentage,
            calculate_margin_percentage,
        ],
    )


def build_agent_prompt(question: str, retrieval_result: RetrievalResult) -> str:
    evidence_coverage = sorted(
        {(passage.company, passage.filing_year, passage.filing_type) for passage in retrieval_result.passages},
        key=lambda item: (item[0], item[1], item[2]),
    )
    coverage_lines = "\n".join(
        f"- {company} {filing_type} {filing_year}" for company, filing_year, filing_type in evidence_coverage
    )
    passages = "\n\n".join(
        (
            f"Passage {passage.rank}\n"
            f"chunk_id: {passage.chunk_id}\n"
            f"source: {passage.company} {passage.filing_type} {passage.filing_year}, chunk {passage.chunk_index}\n"
            f"content:\n{passage.content}\n"
            f"surrounding_context:\n{chr(10).join(passage.neighbor_chunks) or 'No surrounding context.'}"
        )
        for passage in retrieval_result.passages
    )
    return (
        f"Question:\n{question.strip()}\n\n"
        "Evidence coverage available in this run:\n"
        f"{coverage_lines or 'No evidence coverage.'}\n\n"
        "Analysis requirements:\n"
        "- For comparisons across years, companies, products, or segments, build the answer from the cited evidence "
        "for each relevant period/category that appears in the evidence coverage.\n"
        "- If the question asks about margins and the evidence includes revenue and operating income, calculate "
        "operating margin as operating income divided by revenue; do not use operating income growth as a substitute "
        "for margin percentage. Use the calculator tool for margin and growth calculations.\n"
        "- Check every trend word against the numbers. Do not say a metric steadily improved, consistently grew, "
        "or peaked unless the cited values support that exact wording.\n"
        "- If the retrieved evidence is incomplete for a requested period/category, say what is missing instead of "
        "guessing.\n\n"
        "Retrieved evidence passages:\n"
        f"{passages or 'No passages retrieved.'}\n\n"
        "Answer using only this evidence. Return the structured GroundedAnswer output."
    )


def build_grounded_answer_prompt(question: str, deps: DocumentAgentDeps) -> str:
    evidence_text = format_answer_plan(deps.answer_plan) if deps.answer_plan else None
    if evidence_text is None:
        evidence_text = (
            format_evidence_brief(deps.evidence_brief)
            if deps.evidence_brief
            else "No structured evidence brief was prepared."
        )
    return (
        f"{build_agent_prompt(question, deps.retrieval_result)}\n\n"
        "Structured evidence brief:\n"
        f"{evidence_text}\n\n"
        "Use the structured evidence brief as the preferred source for numeric and comparative claims. "
        "If the structured evidence conflicts with raw passage prose, use the structured evidence and cite its source chunks."
    )


def run_document_agent(question: str, deps: DocumentAgentDeps) -> GroundedAnswer:
    document_agent = create_document_agent()
    result = document_agent.run_sync(build_grounded_answer_prompt(question, deps), deps=deps)
    return result.output


async def run_document_agent_async(question: str, deps: DocumentAgentDeps) -> GroundedAnswer:
    document_agent = create_document_agent()
    result = await document_agent.run(build_grounded_answer_prompt(question, deps), deps=deps)
    return result.output
