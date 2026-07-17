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

## Phase 7 — Retrieval

Goal: a user question returns ranked, relevant source passages.

- [X] `retrieval/queries.py` — pgvector semantic search over `document_chunks`
- [X] `retrieval/queries.py` — Postgres full-text search over `search_vector`
- [X] `retrieval/fusion.py` — Reciprocal Rank Fusion in Python
- [X] `retrieval/retriever.py` — query → fused ranked passages + neighbor chunks
- [X] Unit tests: fusion ranking, query assembly (mock DB)
- [X] Integration test (optional, `@pytest.mark.integration`): real query against ingested corpus
- [X] Verify: test queries from [client-brief](client-brief.md) return relevant chunks (manual or scripted)

## Phase 8 — LLM agent & grounding

- [X] `assistant/instructions.md` — product contract (cite everything, refuse to invent, no stock picks)
- [X] PydanticAI agent with typed deps (`DocumentAgentDeps`) and output (`GroundedAnswer`)
- [X] Agent tools: `search_filings`, `read_chunk`, `read_surrounding_chunks`
- [X] `chat/orchestrator.py` — one turn: retrieve → agent → validate → stream → persist
- [X] `grounding/validator.py` — every citation maps to a retrieved passage; fail closed on violation
- [X] `chat/streaming.py` — AI SDK-compatible stream (text deltas + citation metadata parts)
- [X] Persist `message_citations` linked to assistant messages
- [X] Unit tests: citation validation, grounding enforcement, message conversion
- [X] Verify against [client-brief example questions](client-brief.md#example-analyst-questions):
  - [X] Answers cite specific filings and pages
  - [X] Under-specified questions get "not enough evidence" responses
  - [X] Question 10 (generative AI margins) refuses to infer beyond filings

## Phase 9 — Trust UI: citations & source passages

Goal: analysts can verify every claim in one click — this is what makes the product usable.

- [X] Citation chips/links on assistant messages (company, filing type, date, page/section)
- [X] Source passage panel — show underlying excerpt for selected citation
- [X] Empty states (no threads, no corpus match)
- [X] Error states (auth expired, retrieval failure, grounding failure, network/CORS)
- [X] Loading/streaming status during assistant run
- [X] Verify: click a citation → see the exact passage from the filing

## Phase 10 — Structured evidence & answer verification

Goal: answers are built from a verified evidence table before final prose, so numeric and comparative answers are trustworthy.

- [X] `assistant/evidence.py` — typed evidence rows for company, filing year, metric, value, unit, source chunk, and quote
- [X] Evidence extraction step — convert retrieved passages into structured facts before final answer generation
- [X] Coverage check — identify requested companies, years, segments, products, and metrics; flag missing evidence
- [X] Deterministic calculations — growth rates, operating margins, and period comparisons computed in code
- [X] Answer planner — produce a cited evidence table and interpretation outline before final response
- [X] Grounding validator upgrade — every numeric claim maps to a structured evidence row or calculation
- [X] Chat orchestrator update — retrieve → extract evidence → calculate/verify → final agent answer → validate → persist
- [X] Unit tests: evidence extraction models, coverage checks, calculations, numeric claim validation
- [X] Verify: Apple revenue mix answer uses complete 2021-2025 product table
- [X] Verify: Microsoft cloud answer distinguishes revenue growth, operating income growth, and operating margin percentage

## Phase 10A — Reliability and chat UX repair

Goal: the assistant recovers missing evidence before refusing, and the chat interface feels stable enough for analyst testing.

**Backend reliability**

- [X] Evidence-aware retrieval retry — when structured evidence has coverage gaps, run targeted full-text recovery searches before answering
- [X] Targeted query builder — derive company, years, segments/products, and financial metrics from the question
- [X] Merge recovered passages into the existing retrieval result without duplicate chunks
- [X] Unit tests: Microsoft Intelligent Cloud 2022-2025 recovery finds revenue and operating income evidence
- [X] Verify: Microsoft cloud answer no longer gives false "not enough evidence" when filings contain the segment table

**Frontend chat UX**

- [X] Backend `DELETE /chat/threads/{thread_id}` for owned threads
- [X] Frontend delete chat action in the thread sidebar
- [X] Previous chat navigation remains responsive while not streaming
- [X] User prompt appears exactly once after send, without duplicate/ghost messages
- [X] Error state preserves the typed prompt when send fails
- [X] Unit/build checks for chat API and UI changes

## Phase 11 — Frontend integration & analyst UI

Goal: turn the working chat into a polished internal analyst tool with reusable components, clear source verification, stable chat flows, and a disciplined black-and-white visual system.

**Design system foundation**

- [X] Define reusable layout primitives: app shell, collapsible sidebar, main chat column, source panel
- [X] Define reusable chat primitives: message bubble, assistant answer block, citation chip, status step, empty state, error banner
- [X] Define visual tokens for the black-and-white interface: surfaces, borders, text hierarchy, focus states, spacing, and compact data labels
- [X] Standardize icon buttons, menus, tooltips, and destructive actions using shadcn/ui patterns
- [X] Verify responsive behavior for desktop, tablet, and narrow laptop widths

**Navigation and account UX**

- [X] Collapsible thread sidebar with open/closed states and keyboard-accessible toggle
- [X] Conversation list with active state, loading skeleton, empty state, refresh, delete, and new chat action
- [X] User/account area pinned to the bottom of the sidebar
- [X] Logout action in user/account menu
- [X] Preserve current thread state when navigating, deleting, refreshing, or collapsing the sidebar

**Chat interaction**

- [X] Replace basic message rendering with polished user and assistant message components
- [X] Render assistant answers with readable markdown-style structure for headings, bullets, tables, and evidence summaries
- [X] Add waiting/status timeline for retrieval, ranking, evidence extraction, drafting, validation, and saving
- [X] Improve composer ergonomics: autosize textarea, Enter-to-send, Shift+Enter newline, disabled/sending states
- [X] Add useful starter prompts for empty chats based on the client brief
- [X] Preserve prompt text on errors and prevent duplicate/ghost messages

**Citations and source review**

- [X] Citation chips show company, filing type, filing year, section/page/chunk, and selected state
- [X] Source passage panel supports open/close, selected excerpt, surrounding context, and SEC filing link
- [X] Highlight or clearly separate the exact quoted passage from surrounding context
- [X] Add citation-focused empty state and missing-source error state
- [X] Verify: click a citation → source panel opens to the exact supporting passage

**Quality gates**

- [X] Component-level TypeScript/build checks for sidebar, composer, message rendering, and citation panel
- [X] Frontend build and lint pass
- [X] Local production preview smoke test: frontend shell serves successfully
- [X] Accessibility pass: keyboard navigation, focus rings, aria labels, color contrast, reduced motion
- [X] Final visual review checklist completed for the implemented shell

## 12. Pilot readiness

Goal: 5 senior analysts can use it for a week and report >=3 hours saved per analyst per week.

- [X] README "Running locally" section — copy-paste commands for backend + frontend + env vars
- [X] Seed or document how to ingest/update the corpus
- [ ] Smoke-test all 10 example questions from the client brief
- [X] Confirm chat history persists across sessions
- [X] Confirm ~40-user scale assumptions (no hardcoded single-user shortcuts)
- [X] Basic structured logging on backend (`structlog`) for debugging failed turns
- [ ] Review latency: streaming starts within a few seconds for typical queries

## 13. Deployment and launch

Goal: deploy Document Copilot on Railway with Supabase as the production database/auth provider, then verify analysts can use the live app end to end.

**Railway project setup**

- [ ] Create a Railway project named `document-copilot` (currently `selfless-eagerness`; rename in Railway Project Settings -> General)
- [X] Connect the GitHub repository to Railway
- [X] Create separate Railway services for `backend` and `frontend`
- [ ] Confirm Railway deploys from the intended branch
- [ ] Decide whether production deploys should run automatically on every push or only from manual promotion
- [ ] Add Railway project/team access only for people who need production access

**Backend service**

- [X] Configure backend root directory as `backend`
- [X] Confirm Railway detects the Python/uv project correctly
- [X] Set backend start command: `uv run --no-dev uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- [X] Set backend health check path to `/health`
- [X] Confirm backend deploy logs show app startup without missing env vars
- [X] Open backend production URL and verify `/health` returns `{"status":"ok"}`
- [ ] Run Alembic migrations against production Supabase before production smoke testing
- [ ] Confirm production backend can connect to Supabase Postgres
- [ ] Confirm production backend can verify Supabase Auth bearer tokens

**Frontend service**

- [X] Configure frontend root directory as `frontend`
- [X] Confirm Railway detects the Node/pnpm project correctly
- [X] Set frontend build command: `pnpm install --frozen-lockfile && pnpm build`
- [X] Set frontend start command: `pnpm preview --host 0.0.0.0 --port $PORT`
- [X] Confirm frontend deploy logs show a successful Vite production build
- [X] Open frontend production URL and verify the login page loads
- [X] Confirm frontend points to the production backend URL, not localhost

**Production environment variables**

- [X] Backend: set `SUPABASE_URL`
- [X] Backend: set `SUPABASE_ANON_KEY`
- [X] Backend: set `SUPABASE_SERVICE_ROLE_KEY`
- [X] Backend: set `DATABASE_URL` using the direct Supabase database connection string
- [X] Backend: set `OPENAI_API_KEY`
- [X] Backend: set `OPENAI_EMBEDDING_MODEL`
- [X] Backend: set `OPENAI_EMBEDDING_DIMENSIONS`
- [X] Backend: set `OPENAI_CHAT_MODEL`
- [X] Backend: set `ALLOWED_ORIGINS` to the production frontend Railway domain
- [X] Frontend: set `VITE_API_BASE_URL` to the production backend Railway domain
- [X] Frontend: set `VITE_SUPABASE_URL`
- [X] Frontend: set `VITE_SUPABASE_ANON_KEY`
- [X] Verify no service-role key, database URL, or OpenAI key is exposed in frontend variables or client bundle

**Supabase production settings**

- [ ] Add the production frontend Railway URL to Supabase Auth redirect/site URLs
- [ ] Confirm email auth settings match pilot expectations
- [ ] Confirm production database has the latest Alembic schema
- [ ] Confirm `pgvector` extension exists in production
- [ ] Confirm source documents and chunks exist in production Supabase
- [ ] Confirm retrieval indexes exist: vector HNSW index and full-text GIN index
- [ ] Confirm RLS policies are enabled for user-owned chat data

**Production corpus**

- [ ] Decide whether production uses the existing ingested corpus or a fresh Railway/Supabase ingest
- [ ] Run source-document ingest for production if needed
- [ ] Run chunk/embedding ingest for production if needed
- [ ] Verify expected corpus coverage: AAPL, AMZN, GOOGL, MSFT, NVDA filings for 2021-2025
- [ ] Spot-check one known filing table in production retrieval data

**Production smoke tests**

- [ ] Sign up or sign in with a pilot analyst account
- [ ] Create a new chat thread
- [ ] Ask a simple single-fact question and verify cited answer appears
- [ ] Click a citation and verify the source passage panel opens
- [ ] Reload the page and confirm chat history persists
- [ ] Sign out and sign back in, then confirm the same chat history is visible
- [ ] Create a second user and confirm they cannot see the first user's threads
- [ ] Ask an out-of-corpus question and verify a "not enough evidence" answer, not a crash
- [ ] Trigger or observe a failed-turn log and confirm Railway logs include structured `structlog` fields
- [ ] Confirm no CORS errors appear in browser devtools during chat

**Operational checks**

- [ ] Document where to view Railway deploy logs and runtime logs
- [ ] Document how to manually redeploy backend and frontend
- [ ] Document how to roll back to a previous Railway deployment
- [ ] Document how to rotate compromised Supabase/OpenAI secrets
- [ ] Confirm Railway usage/cost expectations for the pilot
- [ ] Confirm OpenAI usage/cost expectations for the pilot
- [ ] Confirm who owns production incident response during pilot week

**Launch handoff**

- [ ] Add production frontend URL to the project README or pilot notes
- [ ] Add production backend URL and health endpoint to internal handoff notes
- [ ] Write a short pilot tester checklist for the 5 analysts
- [ ] Write known limitations before launch, especially current hard-question retrieval/evidence issues
- [ ] Confirm which Phase 12 items remain open before launch
- [ ] Final go/no-go review before sharing the app with analysts

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

## Future improvement

Goal: keep the chat stable while improving retrieval and structured evidence quality for harder analyst questions.

- [ ] Preserve the fixed behavior where grounding/evidence validation errors do not surface as user-facing chat failures
- [ ] Add regression coverage so timeout fallback continues returning either verified evidence summaries or valid "not enough evidence" responses
- [ ] Investigate recurring 2025 evidence issues, especially year alignment in multi-year filing tables
- [ ] Improve table extraction so latest-year columns from 2025 filings are not shifted into 2024
- [ ] Normalize footnote-labeled metrics such as `Services (1)` / `Services (2)` into one canonical metric when appropriate
- [ ] Distinguish revenue/net sales rows from gross margin and cost rows more reliably
- [ ] Improve fallback answers so they summarize conclusions instead of returning raw evidence dumps
- [ ] Reject unsupported out-of-corpus company/topic questions before answer generation; e.g. a Tesla robotaxi question should return "not enough evidence" instead of unrelated 2025 NVDA/MSFT evidence
- [ ] Add evidence gating that blocks verified summaries when retrieved evidence companies or topics do not match the requested company/topic
- [ ] Fix metric-unit extraction for percentage rows so "as a percentage of revenues" is not labeled as `USD millions`
- [ ] Re-test hard Apple, Microsoft, and NVIDIA comparison questions after retrieval/evidence fixes
