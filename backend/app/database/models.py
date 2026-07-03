"""SQLAlchemy models for Document Copilot."""

from typing import List
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    ForeignKey,
    Integer,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin


class User(Base, TimestampMixin):
    """Authenticated user linked to Supabase Auth."""

    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)

    # Relationships
    chat_threads: Mapped[List["ChatThread"]] = relationship("ChatThread", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<User(id={self.id}, user_id={self.user_id})>"


class SourceDocument(Base, TimestampMixin):
    """Top-level document (SEC filing)."""

    __tablename__ = "source_documents"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    company: Mapped[str] = mapped_column(String, nullable=False, index=True)
    filing_type: Mapped[str] = mapped_column(String, nullable=False)  # e.g., "10-K"
    filing_year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    filing_url: Mapped[str | None] = mapped_column(String, nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Relationships
    chunks: Mapped[List["DocumentChunk"]] = relationship("DocumentChunk", back_populates="source_document", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<SourceDocument(id={self.id}, company={self.company}, filing_year={self.filing_year})>"


class DocumentChunk(Base):
    """Chunk of a document with embedding."""

    __tablename__ = "document_chunks"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    source_document_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("source_documents.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[Vector | None] = mapped_column(Vector(1536), nullable=True)

    # Relationships
    source_document: Mapped[SourceDocument] = relationship("SourceDocument", back_populates="chunks")
    message_citations: Mapped[List["MessageCitation"]] = relationship("MessageCitation", back_populates="chunk", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<DocumentChunk(id={self.id}, source_document_id={self.source_document_id}, chunk_index={self.chunk_index})>"


class ChatThread(Base, TimestampMixin):
    """Chat conversation thread for a user."""

    __tablename__ = "chat_threads"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str | None] = mapped_column(String, nullable=True)

    # Relationships
    user: Mapped[User] = relationship("User", back_populates="chat_threads")
    messages: Mapped[List["ChatMessage"]] = relationship("ChatMessage", back_populates="chat_thread", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<ChatThread(id={self.id}, user_id={self.user_id})>"


class ChatMessage(Base):
    """Individual message in a chat thread."""

    __tablename__ = "chat_messages"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    chat_thread_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("chat_threads.id", ondelete="CASCADE"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String, nullable=False)  # "user" or "assistant"
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Relationships
    chat_thread: Mapped[ChatThread] = relationship("ChatThread", back_populates="messages")
    citations: Mapped[List["MessageCitation"]] = relationship("MessageCitation", back_populates="message", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<ChatMessage(id={self.id}, chat_thread_id={self.chat_thread_id}, role={self.role})>"


class MessageCitation(Base):
    """Link between a message and the document chunks it cites."""

    __tablename__ = "message_citations"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    chat_message_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("chat_messages.id", ondelete="CASCADE"), nullable=False, index=True)
    document_chunk_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("document_chunks.id", ondelete="CASCADE"), nullable=False, index=True)

    # Relationships
    message: Mapped[ChatMessage] = relationship("ChatMessage", back_populates="citations")
    chunk: Mapped[DocumentChunk] = relationship("DocumentChunk", back_populates="message_citations")

    def __repr__(self) -> str:
        return f"<MessageCitation(id={self.id}, message_id={self.chat_message_id}, chunk_id={self.document_chunk_id})>"

