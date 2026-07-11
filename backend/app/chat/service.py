"""Database-backed chat shell behavior."""

from collections.abc import Iterable
from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.chat.schemas import AiSdkMessage
from app.database.models import ChatMessage, ChatThread, User

STUB_ASSISTANT_REPLY = (
    "This is a stubbed Document Copilot response. Retrieval is not wired up yet, "
    "so I cannot cite filings in this phase."
)


def get_or_create_app_user(db: Session, supabase_user_id: str) -> User:
    user = db.scalar(select(User).where(User.user_id == supabase_user_id))

    if user is not None:
        return user

    user = User(user_id=supabase_user_id)
    db.add(user)
    db.flush()
    return user


def list_threads(db: Session, user: User) -> list[ChatThread]:
    return list(
        db.scalars(
            select(ChatThread)
            .where(ChatThread.user_id == user.id)
            .order_by(desc(ChatThread.updated_at), desc(ChatThread.created_at))
        )
    )


def create_thread(db: Session, user: User, title: str | None = None) -> ChatThread:
    thread = ChatThread(user_id=user.id, title=title or "New chat")
    db.add(thread)
    db.flush()
    return thread


def get_owned_thread(db: Session, user: User, thread_id: UUID) -> ChatThread:
    thread = db.get(ChatThread, thread_id)

    if thread is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat thread not found")

    if thread.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Chat thread access denied")

    return thread


def load_message_history(db: Session, thread: ChatThread) -> list[ChatMessage]:
    return list(
        db.scalars(
            select(ChatMessage)
            .where(ChatMessage.chat_thread_id == thread.id)
            .order_by(ChatMessage.created_at, ChatMessage.id)
        )
    )


def delete_thread(db: Session, thread: ChatThread) -> None:
    db.delete(thread)
    db.flush()


def latest_user_message(messages: Iterable[AiSdkMessage]) -> AiSdkMessage:
    for message in reversed(list(messages)):
        if message.role == "user" and message.content.strip():
            return message

    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A user message is required")


def save_message(db: Session, thread: ChatThread, role: str, content: str) -> ChatMessage:
    now = datetime.now(UTC)
    message = ChatMessage(chat_thread_id=thread.id, role=role, content=content, created_at=now, updated_at=now)
    thread.updated_at = now
    db.add(message)
    db.flush()
    return message


def stream_stub_reply() -> Iterable[str]:
    words = STUB_ASSISTANT_REPLY.split(" ")

    for index, word in enumerate(words):
        yield word if index == 0 else f" {word}"


def persist_assistant_message(thread_id: UUID, content: str) -> None:
    from app.database.session import SessionLocal

    with SessionLocal() as db:
        thread = db.get(ChatThread, thread_id)
        if thread is None:
            return

        save_message(db, thread, "assistant", content)
        db.commit()


__all__ = [
    "STUB_ASSISTANT_REPLY",
    "create_thread",
    "delete_thread",
    "get_or_create_app_user",
    "get_owned_thread",
    "latest_user_message",
    "list_threads",
    "load_message_history",
    "persist_assistant_message",
    "save_message",
    "stream_stub_reply",
]
