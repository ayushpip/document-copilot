from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.database.chat_thread import ChatThread


class User(Base, TimestampMixin):
    """Authenticated user linked to Supabase Auth."""

    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)

    chat_threads: Mapped[list["ChatThread"]] = relationship(
        "ChatThread",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, user_id={self.user_id})>"
