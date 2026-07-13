from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
import logging

from pydantic_ai.exceptions import ModelHTTPError
from sqlalchemy.orm import Session

from app.assistant import DocumentAgentDeps, GroundedAnswer, GroundedCitation, run_document_agent, run_document_agent_async
from app.assistant.evidence import EvidenceBrief, EvidenceValidationError, build_answer_plan, validate_numeric_claims
from app.assistant.evidence_retrieval import build_recovered_answer_plan
from app.chat import service
from app.database.models import ChatMessage, ChatThread, MessageCitation
from app.grounding import repair_grounded_answer, validate_grounded_answer
from app.grounding.validator import GroundingValidationError
from app.retrieval import RetrievedPassage, RetrievalFilters, RetrievalResult, RetrievalSettings, retrieve_source_passages

AgentRunner = Callable[[str, DocumentAgentDeps], GroundedAnswer]
AsyncAgentRunner = Callable[[str, DocumentAgentDeps], Awaitable[GroundedAnswer]]
logger = logging.getLogger(__name__)
ASYNC_AGENT_TIMEOUT_SECONDS = 45


@dataclass
class ChatTurnResult:
    user_message: ChatMessage
    assistant_message: ChatMessage
    answer: GroundedAnswer
    retrieval_result: RetrievalResult
    evidence_brief: EvidenceBrief


def _citation_source(citation_chunk_id, passages: dict) -> str:
    passage: RetrievedPassage | None = passages.get(citation_chunk_id)
    if passage is None:
        return f"chunk_id: {citation_chunk_id}"
    return (
        f"{passage.company} {passage.filing_type} {passage.filing_year}, "
        f"chunk {passage.chunk_index}, chunk_id: {citation_chunk_id}"
    )


def format_answer_text(answer: GroundedAnswer, retrieval_result: RetrievalResult | None = None) -> str:
    if answer.not_enough_evidence:
        return answer.answer

    passages = {passage.chunk_id: passage for passage in retrieval_result.passages} if retrieval_result else {}
    citation_lines = [
        f"[{index}] {citation.claim} "
        f"({_citation_source(citation.chunk_id, passages)}, quote: \"{citation.supporting_quote}\")"
        for index, citation in enumerate(answer.citations, start=1)
    ]
    if not citation_lines:
        return answer.answer
    return f"{answer.answer}\n\nCitations:\n" + "\n".join(citation_lines)


def persist_message_citations(db: Session, assistant_message: ChatMessage, answer: GroundedAnswer) -> None:
    seen_chunk_ids = set()
    for citation in answer.citations:
        if citation.chunk_id in seen_chunk_ids:
            continue
        seen_chunk_ids.add(citation.chunk_id)
        db.add(MessageCitation(chat_message_id=assistant_message.id, document_chunk_id=citation.chunk_id))


def _format_calculation_value(value: float, unit: str) -> str:
    separator = "" if unit == "%" else " "
    return f"{value:g}{separator}{unit}"


def _format_money_row(value: float, unit: str) -> str:
    if unit == "USD millions":
        return f"${value / 1000:,.3f} billion (${value:,.0f} million)"
    return _format_calculation_value(value, unit)


def deterministic_grounded_answer(evidence_brief: EvidenceBrief) -> GroundedAnswer | None:
    """Answer simple single-fact numeric questions without a final LLM call."""

    if len(evidence_brief.rows) != 1 or evidence_brief.coverage_gaps or evidence_brief.conflicts:
        return None
    if evidence_brief.calculations:
        return None

    row = evidence_brief.rows[0]
    answer = (
        f"{row.company}'s {row.metric.lower()} in fiscal {row.filing_year} was "
        f"{_format_money_row(row.value, row.unit)}."
    )
    return GroundedAnswer(
        answer=answer,
        citations=[
            GroundedCitation(
                chunk_id=row.source_chunk_id,
                claim=f"{row.company} {row.metric} was {row.value:g} {row.unit} in {row.filing_year}.",
                supporting_quote=row.quote,
            )
        ],
    )


def fallback_grounded_answer(evidence_brief: EvidenceBrief) -> GroundedAnswer | None:
    """Build a conservative answer from verified evidence if the model output fails validation."""

    if not evidence_brief.rows:
        return None

    rows_by_metric: dict[str, list] = defaultdict(list)
    for row in evidence_brief.rows:
        rows_by_metric[row.metric].append(row)

    sections = [
        "Verified evidence summary:",
        "This numeric comparison is based directly on extracted filing evidence and deterministic calculations.",
    ]
    if evidence_brief.conflicts:
        sections.append(
            "Important caveat: the retrieved filings contain conflicting/recast segment values. "
            "Do not read conflicting years as one clean like-for-like trend without checking the basis."
        )

    evidence_lines = []
    for metric, metric_rows in sorted(rows_by_metric.items()):
        values = ", ".join(
            f"{row.filing_year}: {row.value:g} {row.unit} ({row.source_filing_year} filing, chunk {row.source_chunk_index})"
            for row in sorted(metric_rows, key=lambda item: (item.filing_year, item.value))
        )
        evidence_lines.append(f"- {metric}: {values}")
    sections.append("\nEvidence:\n" + "\n".join(evidence_lines[:24]))

    calculation_lines = [
        f"- {calculation.label}: {_format_calculation_value(calculation.value, calculation.unit)}"
        for calculation in evidence_brief.calculations
    ]
    if calculation_lines:
        sections.append("\nSafe calculated comparisons:\n" + "\n".join(calculation_lines[:24]))
    if evidence_brief.conflicts:
        sections.append("\nConflicts/recasts to review:\n" + "\n".join(f"- {conflict}" for conflict in evidence_brief.conflicts[:12]))

    citations = [
        GroundedCitation(
            chunk_id=row.source_chunk_id,
            claim=f"{row.company} {row.metric} was {row.value:g} {row.unit} in {row.filing_year}.",
            supporting_quote=row.quote,
        )
        for row in evidence_brief.rows[:40]
    ]
    return GroundedAnswer(answer="\n".join(sections), citations=citations)


def not_enough_verified_evidence_answer() -> GroundedAnswer:
    """Fail closed with a valid chat answer when the model never returns."""

    return GroundedAnswer(
        answer="There is not enough verified evidence in the retrieved filings to answer reliably.",
        not_enough_evidence=True,
    )


def fallback_or_not_enough_evidence(evidence_brief: EvidenceBrief) -> GroundedAnswer:
    return fallback_grounded_answer(evidence_brief) or not_enough_verified_evidence_answer()


def validate_or_fallback_answer(
    answer: GroundedAnswer,
    retrieval_result: RetrievalResult,
    evidence_brief: EvidenceBrief,
) -> GroundedAnswer:
    if answer.not_enough_evidence and evidence_brief.rows and not evidence_brief.coverage_gaps:
        fallback_answer = fallback_grounded_answer(evidence_brief)
        if fallback_answer is None:
            raise GroundingValidationError("Model claimed not enough evidence despite verified evidence rows.")
        repaired_fallback = repair_grounded_answer(fallback_answer, retrieval_result)
        validate_grounded_answer(repaired_fallback, retrieval_result)
        validate_numeric_claims(repaired_fallback.answer, evidence_brief)
        return repaired_fallback

    try:
        repaired_answer = repair_grounded_answer(answer, retrieval_result)
        validate_grounded_answer(repaired_answer, retrieval_result)
        validate_numeric_claims(repaired_answer.answer, evidence_brief)
        return repaired_answer
    except (GroundingValidationError, EvidenceValidationError):
        fallback_answer = fallback_grounded_answer(evidence_brief)
        if fallback_answer is None:
            raise
        repaired_fallback = repair_grounded_answer(fallback_answer, retrieval_result)
        validate_grounded_answer(repaired_fallback, retrieval_result)
        validate_numeric_claims(repaired_fallback.answer, evidence_brief)
        return repaired_fallback


def _is_context_length_error(exc: Exception) -> bool:
    if not isinstance(exc, ModelHTTPError):
        return False
    body = exc.body if isinstance(exc.body, dict) else {}
    code = str(body.get("code", ""))
    message = str(body.get("message", "")).lower()
    return code == "context_length_exceeded" or "maximum context length" in message


def run_chat_turn(
    db: Session,
    thread: ChatThread,
    question: str,
    *,
    agent_runner: AgentRunner = run_document_agent,
    retrieval_settings: RetrievalSettings | None = None,
) -> ChatTurnResult:
    clean_question = question.strip()
    user_message = service.save_message(db, thread, "user", clean_question)
    retrieval_result = retrieve_source_passages(
        db,
        clean_question,
        filters=RetrievalFilters(),
        retrieval_settings=retrieval_settings or RetrievalSettings(),
    )

    retrieval_result, answer_plan = build_recovered_answer_plan(db, clean_question, retrieval_result)
    evidence_brief = answer_plan.evidence_brief
    deps = DocumentAgentDeps(
        db=db,
        retrieval_result=retrieval_result,
        evidence_brief=evidence_brief,
        answer_plan=answer_plan,
    )
    use_verified_fallback = False
    model_answer = deterministic_grounded_answer(evidence_brief)
    if model_answer is None:
        try:
            model_answer = agent_runner(clean_question, deps)
        except Exception as exc:
            if not _is_context_length_error(exc):
                raise
            logger.warning("Model context limit exceeded; using verified evidence fallback.")
            use_verified_fallback = True
    refreshed_answer_plan = build_answer_plan(clean_question, deps.retrieval_result)
    evidence_brief = refreshed_answer_plan.evidence_brief
    if use_verified_fallback:
        model_answer = fallback_or_not_enough_evidence(evidence_brief)
    answer = validate_or_fallback_answer(model_answer, deps.retrieval_result, evidence_brief)

    assistant_message = service.save_message(db, thread, "assistant", format_answer_text(answer, deps.retrieval_result))
    persist_message_citations(db, assistant_message, answer)

    return ChatTurnResult(
        user_message=user_message,
        assistant_message=assistant_message,
        answer=answer,
        retrieval_result=deps.retrieval_result,
        evidence_brief=evidence_brief,
    )


async def run_chat_turn_async(
    db: Session,
    thread: ChatThread,
    question: str,
    *,
    agent_runner: AsyncAgentRunner = run_document_agent_async,
    retrieval_settings: RetrievalSettings | None = None,
) -> ChatTurnResult:
    clean_question = question.strip()
    user_message = service.save_message(db, thread, "user", clean_question)
    retrieval_result = retrieve_source_passages(
        db,
        clean_question,
        filters=RetrievalFilters(),
        retrieval_settings=retrieval_settings or RetrievalSettings(),
    )

    retrieval_result, answer_plan = build_recovered_answer_plan(db, clean_question, retrieval_result)
    evidence_brief = answer_plan.evidence_brief
    deps = DocumentAgentDeps(
        db=db,
        retrieval_result=retrieval_result,
        evidence_brief=evidence_brief,
        answer_plan=answer_plan,
    )
    use_verified_fallback = False
    model_answer = deterministic_grounded_answer(evidence_brief)
    if model_answer is None:
        try:
            model_answer = await asyncio.wait_for(
                agent_runner(clean_question, deps),
                timeout=ASYNC_AGENT_TIMEOUT_SECONDS,
            )
        except TimeoutError:
            logger.warning("Model answer timed out; using verified evidence fallback.")
            use_verified_fallback = True
        except Exception as exc:
            if not _is_context_length_error(exc):
                raise
            logger.warning("Model context limit exceeded; using verified evidence fallback.")
            use_verified_fallback = True
    refreshed_answer_plan = build_answer_plan(clean_question, deps.retrieval_result)
    evidence_brief = refreshed_answer_plan.evidence_brief
    if use_verified_fallback:
        model_answer = fallback_or_not_enough_evidence(evidence_brief)
    answer = validate_or_fallback_answer(model_answer, deps.retrieval_result, evidence_brief)

    assistant_message = service.save_message(db, thread, "assistant", format_answer_text(answer, deps.retrieval_result))
    persist_message_citations(db, assistant_message, answer)

    return ChatTurnResult(
        user_message=user_message,
        assistant_message=assistant_message,
        answer=answer,
        retrieval_result=deps.retrieval_result,
        evidence_brief=evidence_brief,
    )
