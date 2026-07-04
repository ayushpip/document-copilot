# Project implementation checklist

This checklist follows the most logical path for Document Copilot:
1. establish infrastructure and data pipeline first,
2. build the backend core,
3. wire in retrieval and grounding,
4. then build the frontend UI and auth.

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
- [ ] app/database/supabase.py – user-scoped and service-role clients
- [ ] Verify: uv run uvicorn app.main:app -reload → health check returns 200

## 4. Document ingestion + embeddings
- [ ] Download or seed the sample SEC corpus with `data/download.py`
- [ ] Build ingestion logic to parse filings into raw documents
- [ ] Chunk documents with source metadata (company, filing, page, section)
- [ ] Generate embeddings for chunks using OpenAI or chosen model
- [ ] Store documents, chunks, and embeddings in Supabase
- [ ] Add citation metadata so each chunk can be traced back to a source page

## 5. Retrieval and answer grounding
- [ ] Implement vector search over chunks in Supabase `pgvector`
- [ ] Add full-text / SQL filters for company, filing year, section
- [ ] Build a retrieval pipeline that returns top chunks plus source references
- [ ] Implement a backend endpoint that accepts analyst queries and returns grounded answers
- [ ] Ensure the backend response includes the raw source text and citation details
- [ ] Add safety logic so the model says “I don’t know” when the answer is not in the corpus

## 6. Auth and chat history
- [ ] Wire Supabase Auth into the backend and frontend
- [ ] Add email sign-in / sign-up flows in the frontend
- [ ] Create chat history tables and storage in the backend
- [ ] Save analyst conversations and source-backed answers
- [ ] Build a UI for analysts to review their past sessions

## 7. Frontend app
- [ ] Scaffold `frontend/` with Vite + React + TypeScript
- [ ] Install `@supabase/supabase-js`, routing, and UI dependencies
- [ ] Create a login page using Supabase email auth
- [ ] Create a query/chat page and submit questions to the backend
- [ ] Display answers with citations and source passages
- [ ] Add UI for selecting filings, companies, and years
- [ ] Add conversation history / saved chats view

## 8. Validation and client readiness
- [ ] Test all sample questions from the client brief manually
- [ ] Verify answers return cited source passages for every claim
- [ ] Confirm no hallucinations or unsupported inference leaks through
- [ ] Validate login and conversation persistence
- [ ] Validate analyst workflow: ask question, inspect source, save chat
- [ ] Write a quick “pilot checklist” for the first 5 analysts

## 9. Deployment and launch
- [ ] Choose a host for backend and frontend (Railway, Vercel, etc.)
- [ ] Deploy backend, frontend, and connect to Supabase
- [ ] Set production environment variables securely
- [ ] Run final end-to-end smoke tests in production
- [ ] Document deployment steps and handoff notes

---

## Recommended order to build
1. Setup environment + Supabase
2. Build backend data model and ingestion
3. Implement retrieval and grounding logic
4. Add auth and chat persistence
5. Build frontend UI and connect it
6. Test against the client brief
7. Deploy and validate
