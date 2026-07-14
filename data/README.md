# Data

Local data artifacts for development live here.

- `downloads/` holds raw source files fetched from SEC EDGAR, grouped by year.
- `markdown/` holds converted Markdown filings plus `manifest.json`.
- Downloaded payloads are gitignored because the corpus can get large.

## Fetch source filings

From the repo root:

```bash
uv --cache-dir /tmp/uv-cache --project backend run python data/download.py
```

## Convert filings to Markdown

From the repo root:

```bash
uv --cache-dir /tmp/uv-cache --project backend run python data/convert_to_markdown.py
```

## Seed or update the database corpus

Run migrations first:

```bash
cd ~/ai_projects/document-copilot/backend
uv --cache-dir /tmp/uv-cache run alembic upgrade head
```

Load source documents from `data/markdown/manifest.json` into `source_documents`:

```bash
cd ~/ai_projects/document-copilot
uv --cache-dir /tmp/uv-cache --project backend run python data/ingest_source_documents.py --dry-run
uv --cache-dir /tmp/uv-cache --project backend run python data/ingest_source_documents.py
```

Chunk documents and generate embeddings into `document_chunks`:

```bash
cd ~/ai_projects/document-copilot
uv --cache-dir /tmp/uv-cache --project backend run python data/ingest_document_chunks.py --dry-run
uv --cache-dir /tmp/uv-cache --project backend run python data/ingest_document_chunks.py
```

Useful scoped updates:

```bash
uv --cache-dir /tmp/uv-cache --project backend run python data/ingest_document_chunks.py --company AAPL --year 2025 --force
uv --cache-dir /tmp/uv-cache --project backend run python data/ingest_document_chunks.py --company MSFT --limit-docs 1 --dry-run
uv --cache-dir /tmp/uv-cache --project backend run python data/ingest_document_chunks.py --one-chunk --skip-embeddings
```

The source-document ingest skips existing filings. Chunk ingest skips documents that already have chunks unless `--force` is used.
