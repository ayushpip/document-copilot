# Future Use Notes

This folder is a reusable record of how Document Copilot was built and what should be copied into future AI document-analysis projects. It is not a setup manual for this finished app. It is a project memory: architecture, stack choices, ingestion design, implementation order, prompting lessons, and quality gates.

## What This Project Is

Document Copilot is a grounded document assistant for analyst-style questions over SEC filings. The product contract is simple:

- users ask natural-language questions about a curated filing corpus;
- the backend retrieves source passages from stored filings;
- answers should cite the retrieved evidence;
- unsupported questions should return "not enough evidence";
- privileged credentials and OpenAI calls stay on the backend.

The deployed app has:

- a React/Vite frontend on Railway;
- a FastAPI backend on Railway;
- Supabase Auth and Postgres;
- Postgres `pgvector` semantic search plus full-text search;
- OpenAI chat and embedding calls;
- Docling-based SEC filing conversion and chunking.

## Tech Stack Inventory

### Languages

| Language | Where Used | Why |
| --- | --- | --- |
| Python | Backend API, ingestion scripts, retrieval, evidence validation, tests | Strong ecosystem for AI, data processing, database access, and document parsing |
| TypeScript | React frontend | Safer UI code, typed API/client logic, build-time checks |
| SQL | Alembic migrations, retrieval queries, RLS policies, indexes | Precise Postgres schema and search behavior |
| Markdown | Docs, prompts, architecture notes, converted filings | Human-readable source and project memory |
| HTML/CSS | Vite app shell, Tailwind styles, SEC source documents | Browser UI and source input format |

### Backend

| Tool / Library | Where Used | Purpose |
| --- | --- | --- |
| FastAPI | `backend/app/main.py`, API routes | HTTP API, auth boundary, chat endpoints, health check |
| Uvicorn | Local and Railway start command | ASGI server for FastAPI |
| Pydantic v2 | Schemas/settings | Typed request/response models and validation |
| `pydantic-settings` | `backend/app/config.py` | Environment variable loading |
| PydanticAI | `backend/app/assistant/` | Typed LLM orchestration and agent boundary |
| OpenAI Python SDK | chat generation, embeddings | Chat model and embedding API calls |
| SQLAlchemy | database models/session/querying | App-owned DB access and typed table models |
| Alembic | `backend/alembic/` | Database migrations |
| `psycopg[binary]` | Postgres driver | SQLAlchemy connection to Supabase Postgres |
| `pgvector` Python package | SQLAlchemy vector type | `vector(1536)` embedding columns and pgvector queries |
| Supabase Python client | server-side Supabase calls | Auth/user/database helper access |
| `httpx` | outbound HTTP | async/sync HTTP client usage |
| `structlog` | backend logging | Structured production logs |
| `stopwordsiso` | retrieval keyword planning | stopword filtering for query terms |
| `setuptools` | runtime compatibility | provides `pkg_resources` required by `stopwordsiso` |
| `pytest` | `backend/tests/` | backend unit/integration tests |
| Ruff | backend linting | Python code quality checks |
| uv | backend package manager/runner | dependency locking, venv, script execution |

### Ingestion and Documents

| Tool / Library | Where Used | Purpose |
| --- | --- | --- |
| SEC EDGAR submissions API | `data/download.py` | finds and downloads 10-K source filings |
| BeautifulSoup | `data/convert_to_markdown.py` | cleans noisy SEC/iXBRL HTML before conversion |
| Docling | `data/convert_to_markdown.py`, `data/ingest_document_chunks.py` | converts SEC HTML to Markdown and document objects |
| Docling `HybridChunker` | `data/ingest_document_chunks.py` | chunking with table/header awareness |
| `tiktoken` | chunk sizing | OpenAI-compatible token counting |
| OpenAI embeddings | chunk ingest | creates vectors stored in `document_chunks.embedding` |
| Markdown manifests | `data/markdown/manifest.json` | links source filings to converted files and metadata |

### Frontend

| Tool / Library | Where Used | Purpose |
| --- | --- | --- |
| Vite | frontend dev/build/preview | fast React SPA tooling |
| React | frontend UI | app shell, auth pages, chat UI, source panel |
| TypeScript | frontend source | typed UI and API client code |
| React Router | frontend routing | login/chat/thread routes |
| Supabase JS | browser auth | sign-in/sign-up/session management |
| Tailwind CSS | frontend styling | utility-first layout and visual system |
| `@tailwindcss/vite` | Vite integration | Tailwind build plugin |
| shadcn | UI scaffold/registry | generated component patterns |
| Radix UI | UI primitives | accessible menus/dialog-ish primitives through shadcn-style components |
| lucide-react | icons | sidebar/actions/status icons |
| `class-variance-authority` | component variants | button/control styling patterns |
| `clsx` | class composition | conditional classes |
| `tailwind-merge` | class conflict merging | safer Tailwind class composition |
| `tw-animate-css` | animations | small UI animation helpers |
| Geist font | typography | app font via `@fontsource-variable/geist` |
| ESLint | frontend linting | TypeScript/React lint checks |

### Infrastructure

| Service | Where Used | Purpose |
| --- | --- | --- |
| Supabase Auth | frontend + backend | email auth, JWT sessions |
| Supabase Postgres | database | users, chats, source documents, chunks, citations |
| Supabase `pgvector` | database extension | semantic vector search |
| Postgres full-text search | generated `search_vector` + GIN index | lexical retrieval |
| Railway | deployment | separate backend and frontend services |
| Railway Serverless/App Sleep | deployment cost control | reduces idle compute usage |
| Railway variables | production secrets | backend and frontend env vars |
| GitHub | source control | remote repository and Railway source link |

## Design Choices Worth Reusing

- Keep the frontend thin. The browser handles auth session state and rendering; retrieval, grounding, OpenAI calls, and service-role access stay on the backend.
- Use Supabase Auth as the identity source. The frontend sends the Supabase access token to FastAPI, and FastAPI verifies it before doing work.
- Store source documents and chunks in Postgres. This keeps retrieval, citations, chat state, and auditability in one database.
- Use hybrid retrieval. Vector search alone is not enough for exact table/metric questions; full-text search alone misses paraphrases. Fuse both.
- Treat answer generation as a trust problem, not only a chat problem. Retrieval, evidence extraction, calculation, and citation validation need their own tests.
- Deploy frontend and backend as separate services. It keeps browser build concerns away from Python runtime concerns.
- Use config-as-code for Railway service commands. Dashboard settings can drift; `railway.json` made deployment repeatable.

## Hard Lessons From This Build

- Out-of-corpus questions need explicit gating. A Tesla robotaxi question should not return unrelated NVDA/MSFT evidence just because those chunks mention 2025 revenue.
- 2025 filing tables are tricky. Recast/latest-year columns and footnote labels need careful extraction checks.
- Percentage rows must not be labeled as `USD millions`.
- `uv run --no-dev` is important in production. Without it, runtime can accidentally pull dev/document-processing dependencies.
- Some libraries hide runtime dependencies. `stopwordsiso` needed `pkg_resources`, so `setuptools` had to become an explicit runtime dependency.
- Vite preview on Railway needs the public Railway host in `preview.allowedHosts`.
- Deployment success does not mean product quality success. The app can be online while retrieval/evidence behavior still needs work.

## Files In This Folder

- [architecture.md](architecture.md): reusable architecture doc with Mermaid diagram.
- [ingestion-pipeline.md](ingestion-pipeline.md): SEC download, Docling conversion, chunking, embeddings, and database loading flow.
- [setup-guides.md](setup-guides.md): what must exist for future projects before implementation starts.
- [future-project-structure.md](future-project-structure.md): a clean checklist/order for future projects based on `docs/todo.md`.
- [prompting-guide.md](prompting-guide.md): how to write better prompts for Codex/AI coding agents based on this project.
- [guides/backend-guide.md](guides/backend-guide.md): backend setup pattern.
- [guides/frontend-guide.md](guides/frontend-guide.md): frontend setup pattern.
- [guides/supabase-railway-guide.md](guides/supabase-railway-guide.md): hosted services, secrets, deployment, and cost-control pattern.
