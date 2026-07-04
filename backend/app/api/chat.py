"""Chat shell API routes."""

from collections.abc import Iterable
from uuid import UUID

from fastapi import Depends, FastAPI
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.auth import CurrentUser, get_current_user
from app.chat import service
from app.chat.schemas import ChatMessageResponse, ChatStreamRequest, ChatThreadCreate, ChatThreadResponse
from app.database.session import get_session


def get_app_user(current_user: CurrentUser, db: Session):
    return service.get_or_create_app_user(db, current_user.user_id)


async def list_chat_threads(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> list[ChatThreadResponse]:
    user = get_app_user(current_user, db)
    threads = service.list_threads(db, user)
    return [ChatThreadResponse.model_validate(thread) for thread in threads]


async def create_chat_thread(
    payload: ChatThreadCreate,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> ChatThreadResponse:
    user = get_app_user(current_user, db)
    thread = service.create_thread(db, user, payload.title)
    db.commit()
    db.refresh(thread)
    return ChatThreadResponse.model_validate(thread)


async def read_chat_messages(
    thread_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> list[ChatMessageResponse]:
    user = get_app_user(current_user, db)
    thread = service.get_owned_thread(db, user, thread_id)
    messages = service.load_message_history(db, thread)
    return [ChatMessageResponse.model_validate(message) for message in messages]


async def stream_chat(
    payload: ChatStreamRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> StreamingResponse:
    user = get_app_user(current_user, db)
    thread = service.get_owned_thread(db, user, payload.thread_id)
    user_message = service.latest_user_message(payload.messages)
    service.save_message(db, thread, "user", user_message.content.strip())
    db.commit()

    def generate() -> Iterable[str]:
        chunks = list(service.stream_stub_reply())
        for chunk in chunks:
            yield chunk

        service.persist_assistant_message(payload.thread_id, "".join(chunks))

    return StreamingResponse(generate(), media_type="text/plain")


def register_chat_routes(app: FastAPI) -> None:
    app.add_api_route("/chat/threads", list_chat_threads, methods=["GET"], response_model=list[ChatThreadResponse], tags=["chat"])
    app.add_api_route("/chat/threads", create_chat_thread, methods=["POST"], response_model=ChatThreadResponse, tags=["chat"])
    app.add_api_route(
        "/chat/threads/{thread_id}/messages",
        read_chat_messages,
        methods=["GET"],
        response_model=list[ChatMessageResponse],
        tags=["chat"],
    )
    app.add_api_route("/chat/stream", stream_chat, methods=["POST"], tags=["chat"])


__all__ = ["register_chat_routes"]
