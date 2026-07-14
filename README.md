# Document Copilot

An internal AI chatbot that lets analysts query a corpus of documents in plain English and get sourced, citable answers.

## The client

**Driftwood Capital** — fictional independent investment research firm. Their analysts spend half their week reading 10-Ks and 10-Qs before they can produce any original analysis. Document Copilot eats that intake work so they can skip straight to insight.

Full brief: [docs/client-brief.md](docs/client-brief.md)

## Stack

| Layer              | Choice                                               |
| ------------------ | ---------------------------------------------------- |
| Backend            | Python + FastAPI                                     |
| Frontend           | Vite + React SPA + TypeScript                        |
| Database           | Supabase Postgres (users, chats, documents, chunks)  |
| Migrations         | SQLAlchemy models + Alembic                          |
| Retrieval          | Supabase `pgvector` + Postgres full-text search      |
| Auth               | Supabase Auth (email only)                           |
| Hosting            | Railway                                              |
| LLM + embeddings   | OpenAI                                               |

## Repo layout

```text
document-copilot/
├── AGENTS.md           # agent instructions (read first)
├── README.md           # this file
├── data/               # local corpus + download script (payloads gitignored)
├── docs/
│   └── client-brief.md # the client one-pager
├── backend/            # FastAPI service
└── frontend/           # React SPA (Vite)
```

## Prerequisites

Install these before setting up `backend/` or `frontend/`:

| Tool | Version | Used for | Install |
| ---- | ------- | -------- | ------- |
| [Python](https://www.python.org/downloads/) | 3.12+ | Backend runtime | OS package manager or python.org |
| [uv](https://docs.astral.sh/uv/getting-started/installation/) | latest | Backend deps + `data/download.py` | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| [Node.js](https://nodejs.org/) | 20+ (LTS) | Frontend toolchain | nodejs.org or `nvm install --lts` |
| [pnpm](https://pnpm.io/installation) | latest | Frontend package manager | `corepack enable && corepack prepare pnpm@latest --activate` |

You also need accounts/keys for external services once the app is wired up. Start with [docs/guides/supabase-setup.md](docs/guides/supabase-setup.md) (account + project), then create an [OpenAI API key](https://platform.openai.com/api-keys) when the LLM layer is wired up.

## Running locally

Create local environment files from the examples:

```bash
cd ~/ai_projects/document-copilot
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
```

Fill in the required values:

- `backend/.env`: `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `DATABASE_URL`, `OPENAI_API_KEY`, `OPENAI_EMBEDDING_MODEL`, `OPENAI_EMBEDDING_DIMENSIONS`, `ALLOWED_ORIGINS`
- `frontend/.env`: `VITE_API_BASE_URL`, `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`

Run the backend:

```bash
cd ~/ai_projects/document-copilot/backend
uv --cache-dir /tmp/uv-cache run alembic upgrade head
uv --cache-dir /tmp/uv-cache run uvicorn app.main:app --reload
```

Run the frontend in a second terminal:

```bash
cd ~/ai_projects/document-copilot/frontend
pnpm install
pnpm dev
```

Open the app at the URL printed by Vite, usually:

```text
http://localhost:5173
```

Useful checks:

```bash
cd ~/ai_projects/document-copilot/backend
uv --cache-dir /tmp/uv-cache run pytest
uv --cache-dir /tmp/uv-cache run ruff check .
```

```bash
cd ~/ai_projects/document-copilot/frontend
pnpm lint
pnpm build
```

Detailed setup guides:

- [Supabase](docs/guides/supabase-setup.md) — account, hosted project (dashboard or CLI)
- [Backend](docs/guides/backend-setup.md)
- [Frontend](docs/guides/frontend-setup.md)

## Sample SEC data

Use the standalone downloader to fetch a small local 10-K sample from SEC EDGAR.
Edit the params at the top of `data/download.py`, especially `USER_AGENT`, then run:

```bash
uv run data/download.py
```

By default this downloads the latest 5 10-K filings for AAPL, MSFT, NVDA, AMZN, and GOOGL into year folders under `data/downloads/` and writes a `manifest.json`.
Downloaded files are gitignored; the `data/` folder itself stays in git for the script and notes.
