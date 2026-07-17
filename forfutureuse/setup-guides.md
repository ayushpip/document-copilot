# Future Setup Guides

This file captures the setup decisions and prerequisites to reuse. It intentionally does not repeat every command for this finished app; use it as a checklist before starting a new project.

## Accounts Needed

- GitHub account and repository.
- Supabase project for Auth and Postgres.
- OpenAI API project/key for embeddings and chat.
- Railway project for deployment.

## Local Tools Needed

- Python 3.12 or newer.
- uv for Python dependency management and script running.
- Node.js 20 or newer.
- pnpm for frontend dependency management.
- Git.
- Optional: Railway CLI for deployments and variable checks.

## Supabase Setup Pattern

Use Supabase for:

- email auth;
- Postgres database;
- `pgvector` extension;
- row-level security;
- source document/chunk storage;
- chat history and citations.

Collect these values:

- Project URL.
- anon public key.
- service-role secret key.
- direct database connection string.
- database password.

Rules:

- Frontend gets only `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY`.
- Backend gets `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, and `DATABASE_URL`.
- Never expose service-role key, database URL, or OpenAI key to the frontend.
- Use the direct/session database connection for Alembic migrations.

## Backend Setup Pattern

Use:

- FastAPI + Uvicorn;
- Pydantic settings;
- SQLAlchemy models;
- Alembic migrations;
- Supabase client helpers;
- PydanticAI/OpenAI for LLM orchestration;
- pytest and Ruff for quality gates.

Recommended backend modules:

- `app/config.py`: environment settings.
- `app/main.py`: FastAPI app, CORS, health check.
- `app/auth/`: Supabase JWT verification.
- `app/api/`: FastAPI route registration.
- `app/database/`: sessions, models, persistence helpers.
- `app/retrieval/`: vector/full-text search and fusion.
- `app/assistant/`: agent prompts, evidence models, LLM boundary.
- `app/chat/`: turn orchestration and streaming.
- `app/grounding/`: citation/numeric validation.

Deployment reminder:

- Use `uv run --no-dev` in production so dev dependencies do not get installed at runtime.

## Frontend Setup Pattern

Use:

- Vite;
- React;
- TypeScript;
- React Router;
- Supabase JS;
- Tailwind CSS;
- shadcn/Radix UI patterns;
- lucide-react icons;
- ESLint.

Recommended frontend modules:

- `src/lib/env.ts`: validate browser-safe env vars.
- `src/lib/supabase.ts`: Supabase browser client.
- `src/lib/http.ts`: authenticated fetch wrapper.
- `src/lib/api.ts`: backend API calls.
- `src/pages/`: route-level pages.
- `src/components/chat/`: chat UI, message rendering, citations, source panel.
- `src/components/ui/`: generated/reusable UI primitives.

Deployment reminder:

- Vite preview on Railway needs the Railway domain in `preview.allowedHosts`.

## Railway Setup Pattern

Use two services:

- backend service rooted at `backend`;
- frontend service rooted at `frontend`.

Use repo config:

- `backend/railway.json`
- `frontend/railway.json`

Environment variables:

- Backend: Supabase keys, database URL, OpenAI key/model config, allowed origins.
- Frontend: backend URL, Supabase URL, Supabase anon key.

Cost controls:

- Enable Serverless/App Sleep.
- Watch workspace usage.
- Set usage alerts/hard limits where available.
- Avoid running Railway Agent unless intentionally needed.

## Git/GitHub Setup Pattern

- Commit small logical changes.
- Keep `.env` ignored.
- Never commit downloaded corpora unless explicitly intended.
- Push before relying on GitHub autodeploy.
- If deploying locally with `railway up`, still push later so the repo matches production.

