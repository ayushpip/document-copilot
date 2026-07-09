from types import SimpleNamespace
from uuid import uuid4

from app.api.chat import chat_message_response


class FakeDb:
    def scalars(self, statement):
        return []


def test_chat_message_response_includes_citation_source_data() -> None:
    chunk_id = uuid4()
    message_id = uuid4()
    thread_id = uuid4()
    source_document_id = uuid4()
    source_document = SimpleNamespace(
        company="AAPL",
        filing_type="10-K",
        filing_year=2025,
        filing_url="https://example.com/aapl-10k",
    )
    chunk = SimpleNamespace(
        id=chunk_id,
        source_document_id=source_document_id,
        source_document=source_document,
        chunk_metadata={"filing_date": "2025-11-01", "section": "MD&A"},
        chunk_index=18,
        content="Services net sales increased.",
    )
    message = SimpleNamespace(
        id=message_id,
        chat_thread_id=thread_id,
        role="assistant",
        content="Grounded answer.",
        citations=[SimpleNamespace(chunk=chunk)],
    )

    response = chat_message_response(FakeDb(), message)

    assert response.citations[0].chunk_id == chunk_id
    assert response.citations[0].company == "AAPL"
    assert response.citations[0].filing_type == "10-K"
    assert response.citations[0].filing_year == 2025
    assert response.citations[0].filing_date == "2025-11-01"
    assert response.citations[0].section == "MD&A"
    assert response.citations[0].chunk_index == 18
    assert response.citations[0].content == "Services net sales increased."
