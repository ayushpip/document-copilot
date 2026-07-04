from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.database.document_chunk import DocumentChunk


class SourceDocument(Base, TimestampMixin):
    """Top-level document (SEC filing)."""

    __tablename__ = "source_documents"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    company: Mapped[str] = mapped_column(String, nullable=False, index=True)
    filing_type: Mapped[str] = mapped_column(String, nullable=False)
    filing_year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    filing_url: Mapped[str | None] = mapped_column(String, nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    chunks: Mapped[list["DocumentChunk"]] = relationship(
        "DocumentChunk",
        back_populates="source_document",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<SourceDocument(id={self.id}, company={self.company}, filing_year={self.filing_year})>"
