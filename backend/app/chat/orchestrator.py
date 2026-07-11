from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.assistant import DocumentAgentDeps, GroundedAnswer, run_document_agent, run_document_agent_async
from app.assistant.evidence import EvidenceBrief, build_answer_plan, validate_numeric_claims
from app.chat import service
from app.database.models import ChatMessage, ChatThread, MessageCitation
from app.grounding import repair_grounded_answer, validate_grounded_answer
from app.retrieval import RetrievedPassage, RetrievalFilters, RetrievalResult, RetrievalSettings, retrieve_source_passages

AgentRunner = Callable[[str, DocumentAgentDeps], GroundedAnswer]
AsyncAgentRunner = Callable[[str, DocumentAgentDeps], Awaitable[GroundedAnswer]]


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

    answer_plan = build_answer_plan(clean_question, retrieval_result)
    evidence_brief = answer_plan.evidence_brief
    deps = DocumentAgentDeps(
        db=db,
        retrieval_result=retrieval_result,
        evidence_brief=evidence_brief,
        answer_plan=answer_plan,
    )
    answer = agent_runner(clean_question, deps)
    answer = repair_grounded_answer(answer, retrieval_result)
    validate_grounded_answer(answer, retrieval_result)
    validate_numeric_claims(answer.answer, evidence_brief)

    assistant_message = service.save_message(db, thread, "assistant", format_answer_text(answer, retrieval_result))
    persist_message_citations(db, assistant_message, answer)

    return ChatTurnResult(
        user_message=user_message,
        assistant_message=assistant_message,
        answer=answer,
        retrieval_result=retrieval_result,
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

    answer_plan = build_answer_plan(clean_question, retrieval_result)
    evidence_brief = answer_plan.evidence_brief
    deps = DocumentAgentDeps(
        db=db,
        retrieval_result=retrieval_result,
        evidence_brief=evidence_brief,
        answer_plan=answer_plan,
    )
    answer = await agent_runner(clean_question, deps)
    answer = repair_grounded_answer(answer, retrieval_result)
    validate_grounded_answer(answer, retrieval_result)
    validate_numeric_claims(answer.answer, evidence_brief)

    assistant_message = service.save_message(db, thread, "assistant", format_answer_text(answer, retrieval_result))
    persist_message_citations(db, assistant_message, answer)

    return ChatTurnResult(
        user_message=user_message,
        assistant_message=assistant_message,
        answer=answer,
        retrieval_result=retrieval_result,
        evidence_brief=evidence_brief,
    )
