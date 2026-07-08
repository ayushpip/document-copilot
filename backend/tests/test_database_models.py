from app.database.chat_message import ChatMessage
from app.database.chat_thread import ChatThread
from app.database.document_chunk import DocumentChunk
from app.database.message_citation import MessageCitation
from app.database.source_document import SourceDocument
from app.database.user import User


def test_models_are_available_from_separate_modules() -> None:
    assert User.__tablename__ == "users"
    assert SourceDocument.__tablename__ == "source_documents"
    assert DocumentChunk.__tablename__ == "document_chunks"
    assert "metadata" in DocumentChunk.__table__.columns
    assert ChatThread.__tablename__ == "chat_threads"
    assert ChatMessage.__tablename__ == "chat_messages"
    assert MessageCitation.__tablename__ == "message_citations"
