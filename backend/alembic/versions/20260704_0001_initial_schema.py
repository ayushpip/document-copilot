"""Create initial document copilot schema.

Revision ID: 20260704_0001
Revises:
Create Date: 2026-07-04 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
from pgvector.sqlalchemy import Vector
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260704_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index(op.f("ix_users_user_id"), "users", ["user_id"], unique=False)

    op.create_table(
        "source_documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company", sa.String(), nullable=False),
        sa.Column("filing_type", sa.String(), nullable=False),
        sa.Column("filing_year", sa.Integer(), nullable=False),
        sa.Column("filing_url", sa.String(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_source_documents_company"), "source_documents", ["company"], unique=False)
    op.create_index(op.f("ix_source_documents_filing_year"), "source_documents", ["filing_year"], unique=False)

    op.create_table(
        "chat_threads",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_chat_threads_user_id"), "chat_threads", ["user_id"], unique=False)

    op.create_table(
        "document_chunks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_document_id", sa.Uuid(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(1536), nullable=True),
        sa.Column(
            "search_vector",
            postgresql.TSVECTOR(),
            sa.Computed("to_tsvector('english', content)", persisted=True),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["source_document_id"], ["source_documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_document_chunks_source_document_id"), "document_chunks", ["source_document_id"], unique=False)
    op.create_index(
        "ix_document_chunks_embedding_hnsw",
        "document_chunks",
        ["embedding"],
        unique=False,
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )
    op.create_index(
        "ix_document_chunks_search_vector",
        "document_chunks",
        ["search_vector"],
        unique=False,
        postgresql_using="gin",
    )

    op.create_table(
        "chat_messages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("chat_thread_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["chat_thread_id"], ["chat_threads.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_chat_messages_chat_thread_id"), "chat_messages", ["chat_thread_id"], unique=False)

    op.create_table(
        "message_citations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("chat_message_id", sa.Uuid(), nullable=False),
        sa.Column("document_chunk_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["chat_message_id"], ["chat_messages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_chunk_id"], ["document_chunks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_message_citations_chat_message_id"), "message_citations", ["chat_message_id"], unique=False)
    op.create_index(op.f("ix_message_citations_document_chunk_id"), "message_citations", ["document_chunk_id"], unique=False)

    op.execute("ALTER TABLE users ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE chat_threads ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE chat_messages ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE message_citations ENABLE ROW LEVEL SECURITY")

    op.execute(
        """
        CREATE POLICY users_select_own
        ON users
        FOR SELECT
        TO authenticated
        USING (user_id = auth.uid()::text)
        """
    )
    op.execute(
        """
        CREATE POLICY chat_threads_own
        ON chat_threads
        FOR ALL
        TO authenticated
        USING (
            EXISTS (
                SELECT 1 FROM users
                WHERE users.id = chat_threads.user_id
                AND users.user_id = auth.uid()::text
            )
        )
        WITH CHECK (
            EXISTS (
                SELECT 1 FROM users
                WHERE users.id = chat_threads.user_id
                AND users.user_id = auth.uid()::text
            )
        )
        """
    )
    op.execute(
        """
        CREATE POLICY chat_messages_own
        ON chat_messages
        FOR ALL
        TO authenticated
        USING (
            EXISTS (
                SELECT 1
                FROM chat_threads
                JOIN users ON users.id = chat_threads.user_id
                WHERE chat_threads.id = chat_messages.chat_thread_id
                AND users.user_id = auth.uid()::text
            )
        )
        WITH CHECK (
            EXISTS (
                SELECT 1
                FROM chat_threads
                JOIN users ON users.id = chat_threads.user_id
                WHERE chat_threads.id = chat_messages.chat_thread_id
                AND users.user_id = auth.uid()::text
            )
        )
        """
    )
    op.execute(
        """
        CREATE POLICY message_citations_own
        ON message_citations
        FOR ALL
        TO authenticated
        USING (
            EXISTS (
                SELECT 1
                FROM chat_messages
                JOIN chat_threads ON chat_threads.id = chat_messages.chat_thread_id
                JOIN users ON users.id = chat_threads.user_id
                WHERE chat_messages.id = message_citations.chat_message_id
                AND users.user_id = auth.uid()::text
            )
        )
        WITH CHECK (
            EXISTS (
                SELECT 1
                FROM chat_messages
                JOIN chat_threads ON chat_threads.id = chat_messages.chat_thread_id
                JOIN users ON users.id = chat_threads.user_id
                WHERE chat_messages.id = message_citations.chat_message_id
                AND users.user_id = auth.uid()::text
            )
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS message_citations_own ON message_citations")
    op.execute("DROP POLICY IF EXISTS chat_messages_own ON chat_messages")
    op.execute("DROP POLICY IF EXISTS chat_threads_own ON chat_threads")
    op.execute("DROP POLICY IF EXISTS users_select_own ON users")

    op.execute("ALTER TABLE message_citations DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE chat_messages DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE chat_threads DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE users DISABLE ROW LEVEL SECURITY")

    op.drop_index(op.f("ix_message_citations_document_chunk_id"), table_name="message_citations")
    op.drop_index(op.f("ix_message_citations_chat_message_id"), table_name="message_citations")
    op.drop_table("message_citations")

    op.drop_index(op.f("ix_chat_messages_chat_thread_id"), table_name="chat_messages")
    op.drop_table("chat_messages")

    op.drop_index("ix_document_chunks_search_vector", table_name="document_chunks", postgresql_using="gin")
    op.drop_index("ix_document_chunks_embedding_hnsw", table_name="document_chunks", postgresql_using="hnsw")
    op.drop_index(op.f("ix_document_chunks_source_document_id"), table_name="document_chunks")
    op.drop_table("document_chunks")

    op.drop_index(op.f("ix_chat_threads_user_id"), table_name="chat_threads")
    op.drop_table("chat_threads")

    op.drop_index(op.f("ix_source_documents_filing_year"), table_name="source_documents")
    op.drop_index(op.f("ix_source_documents_company"), table_name="source_documents")
    op.drop_table("source_documents")

    op.drop_index(op.f("ix_users_user_id"), table_name="users")
    op.drop_table("users")
