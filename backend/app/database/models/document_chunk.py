from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import Computed, ForeignKey, Integer, Text, Uuid
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.database.message_citation import MessageCitation
    from app.database.source_document import SourceDocument


class DocumentChunk(Base):
    """Chunk of a document with embedding."""

    __tablename__ = "document_chunks"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    source_document_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("source_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[Vector | None] = mapped_column(Vector(1536), nullable=True)
    search_vector: Mapped[str] = mapped_column(
        TSVECTOR,
        Computed("to_tsvector('english', content)", persisted=True),
        nullable=False,
    )

    source_document: Mapped["SourceDocument"] = relationship("SourceDocument", back_populates="chunks")
    message_citations: Mapped[list["MessageCitation"]] = relationship(
        "MessageCitation",
        back_populates="chunk",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<DocumentChunk(id={self.id}, source_document_id={self.source_document_id}, chunk_index={self.chunk_index})>"
