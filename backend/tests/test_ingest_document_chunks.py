from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import sys


PROJECT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_DIR / "data"
if str(DATA_DIR) not in sys.path:
    sys.path.insert(0, str(DATA_DIR))

import ingest_document_chunks as ingest_chunks  # noqa: E402


def sample_filing() -> dict:
    return {
        "ticker": "AAPL",
        "cik": "0000320193",
        "form": "10-K",
        "filing_date": "2024-11-01",
        "report_date": "2024-09-28",
        "accession_number": "0000320193-24-000123",
        "primary_document": "aapl-20240928.htm",
        "source_url": "https://example.com/aapl.htm",
        "source_local_path": "2024/aapl.htm",
        "local_path": "2024/aapl.md",
    }


def test_filing_year_prefers_report_date() -> None:
    assert ingest_chunks.filing_year(sample_filing()) == 2024


def test_matches_filters() -> None:
    filing = sample_filing()

    assert ingest_chunks.matches_filters(filing, company="aapl", year=2024)
    assert not ingest_chunks.matches_filters(filing, company="MSFT", year=2024)
    assert not ingest_chunks.matches_filters(filing, company="AAPL", year=2023)


def test_chunk_metadata_extracts_manifest_and_headings(monkeypatch) -> None:
    monkeypatch.setattr(
        ingest_chunks,
        "settings",
        SimpleNamespace(openai_embedding_model="text-embedding-3-small", openai_embedding_dimensions=1536),
    )
    chunk = SimpleNamespace(meta=SimpleNamespace(headings=["Item 8", "Consolidated Statements of Operations"]))

    metadata = ingest_chunks.chunk_metadata(sample_filing(), chunk_index=3, chunk=chunk, token_count=123)

    assert metadata["ticker"] == "AAPL"
    assert metadata["filing_year"] == 2024
    assert metadata["chunk_index"] == 3
    assert metadata["token_count"] == 123
    assert metadata["section"] == "Consolidated Statements of Operations"
    assert metadata["embedding_dimensions"] == 1536
