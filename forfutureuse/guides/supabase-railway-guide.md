# Supabase And Railway Guide

Use this pattern when a future project needs hosted auth, Postgres, and low-friction deployment.

## Supabase Pattern

Use Supabase for:

- Auth;
- Postgres;
- pgvector;
- source document/chunk storage;
- user-owned chat state;
- citation records;
- row-level security.

Keep these separate:

- frontend anon key: browser-safe;
- backend anon key: used for some server interactions;
- backend service-role key: secret, server only;
- direct database URL: secret, server/migrations only.

Production checklist:

- Add frontend deployment URL to Supabase Auth site URL and redirect URLs.
- Confirm email auth settings.
- Run Alembic migrations.
- Confirm `vector` extension.
- Confirm RLS policies.
- Confirm corpus coverage and indexes.

## Railway Pattern

Use separate services:

- backend service rooted at `backend`;
- frontend service rooted at `frontend`.

Use config files:

- `backend/railway.json`
- `frontend/railway.json`

Backend production start:

```text
uv run --no-dev uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Frontend production start:

```text
pnpm preview --host 0.0.0.0 --port $PORT
```

Railway env vars:

- Backend: Supabase URL, anon key, service-role key, database URL, OpenAI key, model config, allowed origins.
- Frontend: API base URL, Supabase URL, Supabase anon key.

Cost controls:

- enable Serverless/App Sleep;
- monitor workspace usage;
- avoid unnecessary redeploys;
- avoid Railway Agent unless intentionally using it;
- remove or blank `OPENAI_API_KEY` when you want to make accidental chat usage impossible.

## Deployment Lesson

If Railway is deployed from local using `railway up`, push the matching commits to GitHub after. Otherwise production can be ahead of GitHub and future auto-deploys may revert working config.

