from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.database.chat_thread import ChatThread
    from app.database.message_citation import MessageCitation


class ChatMessage(Base):
    """Individual message in a chat thread."""

    __tablename__ = "chat_messages"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    chat_thread_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("chat_threads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    chat_thread: Mapped["ChatThread"] = relationship("ChatThread", back_populates="messages")
    citations: Mapped[list["MessageCitation"]] = relationship(
        "MessageCitation",
        back_populates="message",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<ChatMessage(id={self.id}, chat_thread_id={self.chat_thread_id}, role={self.role})>"
