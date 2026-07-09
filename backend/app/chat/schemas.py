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
    citations: list["ChatCitationResponse"] = Field(default_factory=list)


class ChatCitationResponse(BaseModel):
    chunk_id: UUID
    company: str
    filing_type: str
    filing_year: int
    filing_url: str | None
    filing_date: str | None = None
    report_date: str | None = None
    section: str | None = None
    chunk_index: int
    content: str
    neighbor_chunks: list[str] = Field(default_factory=list)


class AiSdkMessage(BaseModel):
    role: MessageRole
    content: str


class ChatStreamRequest(BaseModel):
    thread_id: UUID
    messages: list[AiSdkMessage] = Field(min_length=1)
