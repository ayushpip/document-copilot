# Project implementation checklist

This checklist follows the most logical path for Document Copilot:
1. establish infrastructure first,
2. build the backend core,
3. wire in auth,
4. then build ingestion, retrieval, and the analyst UI.

## 1. Local environment
- [X] Install Python 3.12+ and verify with `python --version`
- [X] Install `uv` and verify with `uv --version`
- [X] Install Node.js 20+ and verify with `node --version`
- [X] Install `pnpm` and verify with `pnpm --version`
- [X] Confirm repo is on GitHub and remote is configured

## 2. Supabase setup
- [X] Create a Supabase project for the app
- [X] Collect `PROJECT_URL`, `anon key`, `service_role key`, and direct DB connection string
- [X] Enable email auth only in Supabase Auth settings
- [X] Decide whether email confirmation will be disabled for local dev
- [X] Keep `service_role` secret out of git

## 3. Backend scaffold & database
Goal: a running FastAPI service with a migrated Supabase schema.
- [X] Init backend deps and project layout (backend-setup)
- [X] app/config.py – settings module, fail fast on missing env vars
- [X] app/main.py – FastAPI app, CORS, health check (GET /health)
- [X] SQLAlchemy models in app/database/models/:
  - [X] users
  - [X] source_documents
  - [X] document_chunks (embedding + generated tsvector)
  - [X] chat_threads
  - [X] chat_messages
  - [X] message_citations
- [X] Alembic init + first migration:
  - [X] create extension if not exists vector
  - [X] vector (1536) embedding column
  - [X] generated tsvector column on chunks
  - [X] HNSW index (vector) + GIN index (full-text)
  - [X] RLS policies (users see only their own chats)
- [X] uv run alembic upgrade head against Supabase direct connection
- [X] app/database/supabase.py – user-scoped and service-role clients
- [X] Verify: uv run uvicorn app.main:app --reload → health check returns 200

## Phase 4 — Auth (full stack)

Goal: analysts can sign in with email; backend rejects unauthenticated requests.

**Backend**

- [X] `app/auth/dependencies.py` — verify `Authorization: Bearer <supabase_jwt>`, expose `get_current_user`
- [X] Reject missing/expired tokens with `401` before any chat or retrieval work

**Frontend**

- [X] Scaffold Vite + React + TypeScript + Tailwind + shadcn ([frontend-setup](guides/frontend-setup.md))
- [X] Install `@supabase/supabase-js`, routing, and UI dependencies
- [X] `src/lib/env.ts` — validate `VITE_API_BASE_URL`, `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`
- [X] `src/lib/supabase.ts` — browser Supabase client
- [X] `src/lib/http.ts` + `src/lib/api.ts` — fetch wrapper with automatic bearer token
- [X] Sign-in / sign-up pages (email only, no SSO)
- [X] Protected routes — redirect unauthenticated users to login
- [X] Verify: sign up, sign in, token reaches backend on a test authenticated endpoint

## Phase 5 — Chat shell (vertical slice, stubbed)

Goal: end-to-end chat UI streaming from FastAPI, no real retrieval yet.

**Backend**

- [X] Chat thread CRUD: list threads, create thread, load message history
- [X] `POST /chat/stream` — accepts AI SDK message format, streams a stubbed assistant reply
- [X] Persist user + assistant messages to `chat_messages` after stream completes
- [X] `403` when user accesses another user's thread

**Frontend**

- [X] React Router: login, chat list, chat thread routes
- [X] AI SDK chat primitives pointed at `POST /chat/stream` with Supabase bearer token
- [X] Thread sidebar (past conversations)
- [X] Basic message list + input + streaming indicator
- [X] Verify: create thread, send message, see streamed stub response, reload and see history

## Phase 6 — Ingestion pipeline

Goal: SEC filings in the corpus are parsed, chunked, embedded, and stored in Supabase.

- [X] `ingest/` scripts (or CLI entrypoint) for one-off corpus loading
- [X] HTML → normalized Markdown extraction (preserve page/section metadata)
- [X] Chunking strategy (size + overlap; store chunk index, page, section, ticker, filing type, year)
- [X] Write `source_documents` rows with filing metadata from `manifest.json`
- [X] Write `document_chunks` rows with text + metadata
- [X] OpenAI embedding generation → store `vector(1536)` per chunk
- [X] Generated `tsvector` populated for full-text search
- [X] Idempotent re-run (skip already-ingested documents)
- [X] Unit tests: chunking logic, metadata extraction
- [X] Run ingestion on full sample corpus (25 filings × 5 companies)
- [X] Verify: chunks exist in Supabase; spot-check a known passage (e.g. Apple revenue mix table)

## 7. Retrieval and answer grounding
- [ ] Implement vector search over chunks in Supabase `pgvector`
- [ ] Add full-text / SQL filters for company, filing year, section
- [ ] Build a retrieval pipeline that returns top chunks plus source references
- [ ] Implement a backend endpoint that accepts analyst queries and returns grounded answers
- [ ] Ensure the backend response includes the raw source text and citation details
- [ ] Add safety logic so the model says “I don’t know” when the answer is not in the corpus

## 8. Chat history
- [ ] Create chat history tables and storage in the backend
- [ ] Save analyst conversations and source-backed answers
- [ ] Build a UI for analysts to review their past sessions

## 9. Frontend app
- [ ] Install `@supabase/supabase-js`, routing, and UI dependencies
- [ ] Create a query/chat page and submit questions to the backend
- [ ] Display answers with citations and source passages
- [ ] Add UI for selecting filings, companies, and years
- [ ] Add conversation history / saved chats view

## 10. Validation and client readiness
- [ ] Test all sample questions from the client brief manually
- [ ] Verify answers return cited source passages for every claim
- [ ] Confirm no hallucinations or unsupported inference leaks through
- [ ] Validate login and conversation persistence
- [ ] Validate analyst workflow: ask question, inspect source, save chat
- [ ] Write a quick “pilot checklist” for the first 5 analysts

## 11. Deployment and launch
- [ ] Choose a host for backend and frontend (Railway, Vercel, etc.)
- [ ] Deploy backend, frontend, and connect to Supabase
- [ ] Set production environment variables securely
- [ ] Run final end-to-end smoke tests in production
- [ ] Document deployment steps and handoff notes

---

## Recommended order to build
1. Setup environment + Supabase
2. Build backend data model
3. Add auth
4. Build chat shell
5. Build ingestion
6. Implement retrieval and grounding logic
7. Add chat persistence
8. Build frontend UI and connect it
9. Test against the client brief
10. Deploy and validate
