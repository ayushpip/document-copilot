"""Chat shell API routes."""

from collections.abc import Iterable
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import CurrentUser, get_current_user
from app.chat import service
from app.chat.orchestrator import run_chat_turn
from app.chat.schemas import ChatCitationResponse, ChatMessageResponse, ChatStreamRequest, ChatThreadCreate, ChatThreadResponse
from app.chat.streaming import stream_text_deltas
from app.database.models import ChatMessage, DocumentChunk
from app.database.session import get_session
from app.grounding import GroundingValidationError


def get_app_user(current_user: CurrentUser, db: Session):
    return service.get_or_create_app_user(db, current_user.user_id)


def citation_neighbor_chunks(db: Session, chunk: DocumentChunk, window: int = 1) -> list[str]:
    statement = (
        select(DocumentChunk.content)
        .where(DocumentChunk.source_document_id == chunk.source_document_id)
        .where(DocumentChunk.chunk_index >= chunk.chunk_index - window)
        .where(DocumentChunk.chunk_index <= chunk.chunk_index + window)
        .where(DocumentChunk.id != chunk.id)
        .order_by(DocumentChunk.chunk_index)
    )
    return list(db.scalars(statement))


def chat_message_response(db: Session, message: ChatMessage) -> ChatMessageResponse:
    citations = []
    for citation in message.citations:
        chunk = citation.chunk
        source_document = chunk.source_document
        metadata = chunk.chunk_metadata or {}
        citations.append(
            ChatCitationResponse(
                chunk_id=chunk.id,
                company=source_document.company,
                filing_type=source_document.filing_type,
                filing_year=source_document.filing_year,
                filing_url=source_document.filing_url,
                filing_date=metadata.get("filing_date"),
                report_date=metadata.get("report_date"),
                section=metadata.get("section"),
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                neighbor_chunks=citation_neighbor_chunks(db, chunk),
            )
        )

    return ChatMessageResponse(
        id=message.id,
        chat_thread_id=message.chat_thread_id,
        role=message.role,
        content=message.content,
        citations=citations,
    )


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
    return [chat_message_response(db, message) for message in messages]


async def stream_chat(
    payload: ChatStreamRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_session),
) -> StreamingResponse:
    user = get_app_user(current_user, db)
    thread = service.get_owned_thread(db, user, payload.thread_id)
    user_message = service.latest_user_message(payload.messages)
    try:
        turn = run_chat_turn(db, thread, user_message.content)
    except GroundingValidationError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Assistant response failed grounding validation.",
        ) from exc
    db.commit()

    def generate() -> Iterable[str]:
        for chunk in stream_text_deltas(turn.assistant_message.content):
            yield chunk

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
