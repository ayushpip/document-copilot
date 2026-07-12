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

## 12. Validation and client readiness
- [ ] Test all sample questions from the client brief manually
- [ ] Verify answers return cited source passages for every claim
- [ ] Confirm no hallucinations or unsupported inference leaks through
- [ ] Validate login and conversation persistence
- [ ] Validate analyst workflow: ask question, inspect source, save chat
- [ ] Write a quick “pilot checklist” for the first 5 analysts

## 13. Deployment and launch
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
