from collections.abc import Generator

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.api.chat import delete_chat_thread
from app.auth import CurrentUser
from app.chat import service
from app.chat.schemas import AiSdkMessage
from app.database.models import ChatMessage, ChatThread, User


@pytest.fixture
def db() -> Generator[Session]:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    User.__table__.create(engine)
    ChatThread.__table__.create(engine)
    ChatMessage.__table__.create(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    with session_factory() as session:
        yield session


def test_chat_thread_crud_and_message_history(db: Session) -> None:
    user = service.get_or_create_app_user(db, "supabase-user-id")
    thread = service.create_thread(db, user, "First thread")
    service.save_message(db, thread, "user", "Hello")
    service.save_message(db, thread, "assistant", "Stub reply")
    db.commit()

    threads = service.list_threads(db, user)
    messages = service.load_message_history(db, thread)

    assert [item.id for item in threads] == [thread.id]
    assert [message.role for message in messages] == ["user", "assistant"]
    assert [message.content for message in messages] == ["Hello", "Stub reply"]


def test_get_owned_thread_rejects_other_users_thread(db: Session) -> None:
    owner = service.get_or_create_app_user(db, "owner")
    other_user = service.get_or_create_app_user(db, "other-user")
    thread = service.create_thread(db, owner, "Private thread")
    db.commit()

    with pytest.raises(HTTPException) as exc_info:
        service.get_owned_thread(db, other_user, thread.id)

    assert exc_info.value.status_code == 403


def test_delete_thread_removes_owned_thread(db: Session) -> None:
    user = service.get_or_create_app_user(db, "owner")
    thread = service.create_thread(db, user, "Delete me")
    db.commit()

    service.delete_thread(db, thread)
    db.commit()

    assert service.list_threads(db, user) == []


@pytest.mark.anyio
async def test_delete_chat_thread_endpoint_removes_owned_thread(db: Session) -> None:
    user = service.get_or_create_app_user(db, "owner")
    thread = service.create_thread(db, user, "Delete me")
    db.commit()
    current_user = CurrentUser(user_id="owner", email=None, access_token="token", supabase=object())

    response = await delete_chat_thread(thread.id, current_user=current_user, db=db)

    assert response.status_code == 204
    assert service.list_threads(db, user) == []


def test_latest_user_message_uses_last_user_message() -> None:
    message = service.latest_user_message(
        [
            AiSdkMessage(role="user", content="First"),
            AiSdkMessage(role="assistant", content="Second"),
            AiSdkMessage(role="user", content="Third"),
        ]
    )

    assert message.content == "Third"


def test_latest_user_message_requires_user_message() -> None:
    with pytest.raises(HTTPException) as exc_info:
        service.latest_user_message([AiSdkMessage(role="assistant", content="Only assistant")])

    assert exc_info.value.status_code == 400


def test_stream_stub_reply_chunks_recreate_stub_text() -> None:
    assert "".join(service.stream_stub_reply()) == service.STUB_ASSISTANT_REPLY
