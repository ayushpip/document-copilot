from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.assistant import GroundedAnswer, GroundedCitation
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
    monkeypatch.setattr(orchestrator.service, "save_message", fake_save_message)

    with pytest.raises(GroundingValidationError):
        orchestrator.run_chat_turn(FakeDb(), SimpleNamespace(), "Question?", agent_runner=fake_agent_runner)

    assert [message.role for message in saved_messages] == ["user"]


@pytest.mark.anyio
async def test_run_chat_turn_async_uses_async_agent_runner(monkeypatch) -> None:
    retrieval_result = make_retrieval_result()
    saved_messages = []

    def fake_retrieve_source_passages(*args, **kwargs):
        return retrieval_result

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
    monkeypatch.setattr(orchestrator.service, "save_message", fake_save_message)

    turn = await orchestrator.run_chat_turn_async(FakeDb(), SimpleNamespace(), "Question?", agent_runner=fake_agent_runner)

    assert turn.answer.answer == "Apple Services and iPhone sales increased."
    assert [message.role for message in saved_messages] == ["user", "assistant"]
