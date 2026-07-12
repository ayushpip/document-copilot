from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.assistant import GroundedAnswer, GroundedCitation
from app.assistant.evidence import build_answer_plan, build_evidence_brief
from app.chat import orchestrator
from app.database.models import MessageCitation
from app.grounding import GroundingValidationError
from app.retrieval import RetrievedPassage, RetrievalFilters, RetrievalResult, RetrievalSettings


class FakeDb:
    def __init__(self) -> None:
        self.added = []

    def add(self, item) -> None:
        self.added.append(item)


def make_retrieval_result(chunk_id=None) -> RetrievalResult:
    chunk_id = chunk_id or uuid4()
    return RetrievalResult(
        query="Apple revenue",
        passages=[
            RetrievedPassage(
                chunk_id=chunk_id,
                source_document_id=uuid4(),
                company="AAPL",
                filing_year=2025,
                filing_type="10-K",
                filing_url=None,
                chunk_index=18,
                content="Services and iPhone net sales increased during 2025.",
                metadata={},
                rank=1,
                fused_score=0.1,
            )
        ],
        settings=RetrievalSettings(),
        filters=RetrievalFilters(),
    )


def make_numeric_retrieval_result(chunk_id=None) -> RetrievalResult:
    chunk_id = chunk_id or uuid4()
    return RetrievalResult(
        query="Microsoft cloud revenue",
        passages=[
            RetrievedPassage(
                chunk_id=chunk_id,
                source_document_id=uuid4(),
                company="MSFT",
                filing_year=2025,
                filing_type="10-K",
                filing_url=None,
                chunk_index=84,
                content=(
                    "|  | 2025 | 2024 |\n"
                    "| --- | --- | --- |\n"
                    "| Intelligent Cloud |  |  |\n"
                    "| Revenue | 106,265 | 87,464 |\n"
                    "| Operating Income | 44,589 | 37,813 |"
                ),
                metadata={},
                rank=1,
                fused_score=0.1,
            )
        ],
        settings=RetrievalSettings(),
        filters=RetrievalFilters(),
    )


def make_apple_total_net_sales_result(chunk_id=None) -> RetrievalResult:
    chunk_id = chunk_id or uuid4()
    return RetrievalResult(
        query="What was Apple's total net sales in fiscal 2025?",
        passages=[
            RetrievedPassage(
                chunk_id=chunk_id,
                source_document_id=uuid4(),
                company="AAPL",
                filing_year=2025,
                filing_type="10-K",
                filing_url=None,
                chunk_index=31,
                content=(
                    "2025, 1 = 2024. 2025, 2 = 2023. 2025, 3 = . "
                    "Total net sales, 1 = $. Total net sales, 2 = 416,161. "
                    "Total net sales, 3 = $. Total net sales, 4 = 391,035. "
                    "Total net sales, 5 = $. Total net sales, 6 = 383,285."
                ),
                metadata={},
                rank=1,
                fused_score=0.1,
            )
        ],
        settings=RetrievalSettings(),
        filters=RetrievalFilters(company="AAPL", filing_year=2025, filing_type="10-K"),
    )


def test_format_answer_text_appends_citations() -> None:
    chunk_id = uuid4()
    retrieval_result = make_retrieval_result(chunk_id)
    answer = GroundedAnswer(
        answer="Apple disclosed higher Services sales.",
        citations=[
            GroundedCitation(
                chunk_id=chunk_id,
                claim="Services sales were higher.",
                supporting_quote="higher net sales of Services",
            )
        ],
    )

    text = orchestrator.format_answer_text(answer, retrieval_result)

    assert "Apple disclosed higher Services sales." in text
    assert "Citations:" in text
    assert "AAPL 10-K 2025" in text
    assert "chunk 18" in text
    assert str(chunk_id) in text


def test_persist_message_citations_deduplicates_chunks() -> None:
    db = FakeDb()
    chunk_id = uuid4()
    assistant_message = SimpleNamespace(id=uuid4())
    answer = GroundedAnswer(
        answer="Answer",
        citations=[
            GroundedCitation(chunk_id=chunk_id, claim="Claim 1", supporting_quote="Quote 1"),
            GroundedCitation(chunk_id=chunk_id, claim="Claim 2", supporting_quote="Quote 2"),
        ],
    )

    orchestrator.persist_message_citations(db, assistant_message, answer)

    assert len(db.added) == 1
    assert isinstance(db.added[0], MessageCitation)
    assert db.added[0].document_chunk_id == chunk_id


def test_run_chat_turn_fails_closed_when_validation_fails(monkeypatch) -> None:
    retrieval_result = make_retrieval_result()
    saved_messages = []

    def fake_retrieve_source_passages(*args, **kwargs):
        return retrieval_result

    def fake_build_recovered_answer_plan(*args, **kwargs):
        return retrieval_result, build_answer_plan("Question?", retrieval_result)

    def fake_save_message(db, thread, role, content):
        message = SimpleNamespace(id=uuid4(), role=role, content=content)
        saved_messages.append(message)
        return message

    def fake_agent_runner(question, deps):
        return GroundedAnswer(
            answer="Unsupported answer.",
            citations=[
                GroundedCitation(
                    chunk_id=retrieval_result.passages[0].chunk_id,
                    claim="Unsupported.",
                    supporting_quote="This quote is not in evidence.",
                )
            ],
        )

    monkeypatch.setattr(orchestrator, "retrieve_source_passages", fake_retrieve_source_passages)
    monkeypatch.setattr(orchestrator, "build_recovered_answer_plan", fake_build_recovered_answer_plan)
    monkeypatch.setattr(orchestrator.service, "save_message", fake_save_message)

    with pytest.raises(GroundingValidationError):
        orchestrator.run_chat_turn(FakeDb(), SimpleNamespace(), "Question?", agent_runner=fake_agent_runner)

    assert [message.role for message in saved_messages] == ["user"]


def test_run_chat_turn_answers_single_fact_without_final_agent(monkeypatch) -> None:
    question = "What was Apple's total net sales in fiscal 2025?"
    retrieval_result = make_apple_total_net_sales_result()
    saved_messages = []

    def fake_retrieve_source_passages(*args, **kwargs):
        return retrieval_result

    def fake_build_recovered_answer_plan(*args, **kwargs):
        return retrieval_result, build_answer_plan(question, retrieval_result)

    def fake_save_message(db, thread, role, content):
        message = SimpleNamespace(id=uuid4(), role=role, content=content)
        saved_messages.append(message)
        return message

    def agent_should_not_run(question, deps):
        raise AssertionError("simple verified evidence answers should not call the final agent")

    monkeypatch.setattr(orchestrator, "retrieve_source_passages", fake_retrieve_source_passages)
    monkeypatch.setattr(orchestrator, "build_recovered_answer_plan", fake_build_recovered_answer_plan)
    monkeypatch.setattr(orchestrator.service, "save_message", fake_save_message)

    turn = orchestrator.run_chat_turn(FakeDb(), SimpleNamespace(), question, agent_runner=agent_should_not_run)

    assert "total net sales" in turn.answer.answer
    assert "$416.161 billion" in turn.answer.answer
    assert "$416,161 million" in turn.answer.answer
    assert turn.answer.citations
    assert [message.role for message in saved_messages] == ["user", "assistant"]


def test_run_chat_turn_falls_back_to_verified_evidence_when_model_numbers_fail(monkeypatch) -> None:
    question = "Microsoft cloud revenue"
    retrieval_result = make_numeric_retrieval_result()
    evidence_brief = build_evidence_brief(question, retrieval_result)
    saved_messages = []

    def fake_retrieve_source_passages(*args, **kwargs):
        return retrieval_result

    def fake_build_recovered_answer_plan(*args, **kwargs):
        return retrieval_result, build_answer_plan(question, retrieval_result)

    def fake_save_message(db, thread, role, content):
        message = SimpleNamespace(id=uuid4(), role=role, content=content)
        saved_messages.append(message)
        return message

    def fake_agent_runner(question, deps):
        return GroundedAnswer(
            answer="Microsoft Intelligent Cloud revenue was $123,456 million.",
            citations=[
                GroundedCitation(
                    chunk_id=retrieval_result.passages[0].chunk_id,
                    claim="Unsupported number.",
                    supporting_quote="| Revenue | 106,265 | 87,464 |",
                )
            ],
        )

    monkeypatch.setattr(orchestrator, "retrieve_source_passages", fake_retrieve_source_passages)
    monkeypatch.setattr(orchestrator, "build_recovered_answer_plan", fake_build_recovered_answer_plan)
    monkeypatch.setattr(orchestrator.service, "save_message", fake_save_message)

    turn = orchestrator.run_chat_turn(FakeDb(), SimpleNamespace(), question, agent_runner=fake_agent_runner)

    assert "Verified evidence summary" in turn.answer.answer
    assert "106,265" not in turn.answer.answer
    assert "106265" in turn.answer.answer
    assert turn.evidence_brief == evidence_brief
    assert [message.role for message in saved_messages] == ["user", "assistant"]


def test_validate_or_fallback_rejects_false_not_enough_evidence() -> None:
    retrieval_result = make_apple_total_net_sales_result()
    evidence_brief = build_evidence_brief("What was Apple's total net sales in fiscal 2025?", retrieval_result)
    weak_answer = GroundedAnswer(answer="There is not enough evidence.", not_enough_evidence=True)

    answer = orchestrator.validate_or_fallback_answer(weak_answer, retrieval_result, evidence_brief)

    assert not answer.not_enough_evidence
    assert "Verified evidence summary" in answer.answer
    assert "416161" in answer.answer
    assert answer.citations


def test_run_chat_turn_revalidates_after_agent_adds_tool_passages(monkeypatch) -> None:
    initial_result = make_retrieval_result()
    tool_chunk_id = uuid4()
    saved_messages = []

    def fake_retrieve_source_passages(*args, **kwargs):
        return initial_result

    def fake_build_recovered_answer_plan(*args, **kwargs):
        return initial_result, build_answer_plan("Microsoft cloud revenue", initial_result)

    def fake_save_message(db, thread, role, content):
        message = SimpleNamespace(id=uuid4(), role=role, content=content)
        saved_messages.append(message)
        return message

    def fake_agent_runner(question, deps):
        deps.retrieval_result.passages.append(
            RetrievedPassage(
                chunk_id=tool_chunk_id,
                source_document_id=uuid4(),
                company="MSFT",
                filing_year=2025,
                filing_type="10-K",
                filing_url=None,
                chunk_index=84,
                content=(
                    "|  | 2025 | 2024 |\n"
                    "| --- | --- | --- |\n"
                    "| Intelligent Cloud |  |  |\n"
                    "| Revenue | 106,265 | 87,464 |"
                ),
                metadata={},
                rank=2,
                fused_score=0.1,
            )
        )
        return GroundedAnswer(
            answer="Microsoft Intelligent Cloud revenue was $123,456 million.",
            citations=[
                GroundedCitation(
                    chunk_id=tool_chunk_id,
                    claim="Unsupported number.",
                    supporting_quote="| Revenue | 106,265 | 87,464 |",
                )
            ],
        )

    monkeypatch.setattr(orchestrator, "retrieve_source_passages", fake_retrieve_source_passages)
    monkeypatch.setattr(orchestrator, "build_recovered_answer_plan", fake_build_recovered_answer_plan)
    monkeypatch.setattr(orchestrator.service, "save_message", fake_save_message)

    turn = orchestrator.run_chat_turn(FakeDb(), SimpleNamespace(), "Question?", agent_runner=fake_agent_runner)

    assert "Verified evidence summary" in turn.answer.answer
    assert "123456" not in turn.answer.answer
    assert any(passage.chunk_id == tool_chunk_id for passage in turn.retrieval_result.passages)
    assert [message.role for message in saved_messages] == ["user", "assistant"]


@pytest.mark.anyio
async def test_run_chat_turn_async_uses_async_agent_runner(monkeypatch) -> None:
    retrieval_result = make_retrieval_result()
    saved_messages = []

    def fake_retrieve_source_passages(*args, **kwargs):
        return retrieval_result

    def fake_build_recovered_answer_plan(*args, **kwargs):
        return retrieval_result, build_answer_plan("Question?", retrieval_result)

    def fake_save_message(db, thread, role, content):
        message = SimpleNamespace(id=uuid4(), role=role, content=content)
        saved_messages.append(message)
        return message

    async def fake_agent_runner(question, deps):
        return GroundedAnswer(
            answer="Apple Services and iPhone sales increased.",
            citations=[
                GroundedCitation(
                    chunk_id=retrieval_result.passages[0].chunk_id,
                    claim="Services and iPhone sales increased.",
                    supporting_quote="Services and iPhone net sales increased",
                )
            ],
        )

    monkeypatch.setattr(orchestrator, "retrieve_source_passages", fake_retrieve_source_passages)
    monkeypatch.setattr(orchestrator, "build_recovered_answer_plan", fake_build_recovered_answer_plan)
    monkeypatch.setattr(orchestrator.service, "save_message", fake_save_message)

    turn = await orchestrator.run_chat_turn_async(FakeDb(), SimpleNamespace(), "Question?", agent_runner=fake_agent_runner)

    assert turn.answer.answer == "Apple Services and iPhone sales increased."
    assert [message.role for message in saved_messages] == ["user", "assistant"]
