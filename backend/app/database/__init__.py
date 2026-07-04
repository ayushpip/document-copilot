"""Database module for Document Copilot."""

from app.database.base import Base, TimestampMixin
from app.database.models import (
    ChatMessage,
    ChatThread,
    DocumentChunk,
    MessageCitation,
    SourceDocument,
    User,
)
from app.database.supabase import create_service_role_client, create_user_client
from app.database.session import SessionLocal, engine, get_session

__all__ = [
    "Base",
    "TimestampMixin",
    "User",
    "SourceDocument",
    "DocumentChunk",
    "ChatThread",
    "ChatMessage",
    "MessageCitation",
    "create_service_role_client",
    "create_user_client",
    "engine",
    "SessionLocal",
    "get_session",
]
