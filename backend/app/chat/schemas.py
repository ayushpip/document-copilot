"""Pydantic schemas for the chat shell API."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

MessageRole = Literal["system", "user", "assistant"]


class ChatThreadCreate(BaseModel):
    title: str | None = Field(default=None, max_length=120)


class ChatThreadResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str | None
    created_at: datetime
    updated_at: datetime


class ChatMessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    chat_thread_id: UUID
    role: MessageRole
    content: str


class AiSdkMessage(BaseModel):
    role: MessageRole
    content: str


class ChatStreamRequest(BaseModel):
    thread_id: UUID
    messages: list[AiSdkMessage] = Field(min_length=1)
