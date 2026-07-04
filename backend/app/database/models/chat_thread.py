from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.database.chat_message import ChatMessage
    from app.database.user import User


class ChatThread(Base, TimestampMixin):
    """Chat conversation thread for a user."""

    __tablename__ = "chat_threads"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str | None] = mapped_column(String, nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="chat_threads")
    messages: Mapped[list["ChatMessage"]] = relationship(
        "ChatMessage",
        back_populates="chat_thread",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<ChatThread(id={self.id}, user_id={self.user_id})>"
