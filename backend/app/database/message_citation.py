from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.database.chat_message import ChatMessage
    from app.database.document_chunk import DocumentChunk


class MessageCitation(Base):
    """Link between a message and the document chunks it cites."""

    __tablename__ = "message_citations"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    chat_message_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("chat_messages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    document_chunk_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("document_chunks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    message: Mapped["ChatMessage"] = relationship("ChatMessage", back_populates="citations")
    chunk: Mapped["DocumentChunk"] = relationship("DocumentChunk", back_populates="message_citations")

    def __repr__(self) -> str:
        return f"<MessageCitation(id={self.id}, message_id={self.chat_message_id}, chunk_id={self.document_chunk_id})>"
