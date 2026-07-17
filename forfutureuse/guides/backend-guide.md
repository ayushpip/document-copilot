# Backend Guide

Use this pattern when a future app needs a trusted API layer for auth, retrieval, LLM calls, and persistence.

## Use This Stack

- Python 3.12+
- uv
- FastAPI
- Uvicorn
- Pydantic v2
- `pydantic-settings`
- SQLAlchemy
- Alembic
- `psycopg[binary]`
- Supabase Python client
- OpenAI SDK
- PydanticAI
- pytest
- Ruff
- structlog

## Folder Shape

```text
backend/
├── app/
│   ├── api/
│   ├── auth/
│   ├── assistant/
│   ├── chat/
│   ├── database/
│   ├── grounding/
│   ├── retrieval/
│   ├── config.py
│   └── main.py
├── alembic/
├── tests/
├── pyproject.toml
└── uv.lock
```

## Rules To Reuse

- `app/main.py` should register the FastAPI app, CORS, `/health`, and API routes.
- `app/config.py` should fail fast on missing required env vars.
- Auth dependencies should reject bad/missing bearer tokens before any retrieval or OpenAI work.
- SQLAlchemy models should be the source of truth for Alembic migrations.
- Alembic migrations should explicitly add Postgres features that autogenerate misses: extensions, generated columns, HNSW indexes, GIN indexes, RLS.
- Keep LLM orchestration separate from retrieval and grounding validation.
- Use typed outputs for grounded answers and citations.
- Add regression tests for every bad answer.

## Production Reminders

- Use `uv run --no-dev` in the production start command.
- Keep `OPENAI_API_KEY`, `DATABASE_URL`, and Supabase service-role key backend-only.
- Log enough structured context to debug failed turns, but never log secrets.
- `/health` should not require auth and should not call external paid APIs.

