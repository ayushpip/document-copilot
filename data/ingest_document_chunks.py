from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import tiktoken
from docling.chunking import HybridChunker
from docling.datamodel.base_models import ConversionStatus
from docling.document_converter import DocumentConverter
from docling_core.transforms.chunker.tokenizer.openai import OpenAITokenizer
from openai import OpenAI
from sqlalchemy import delete, func, select

from convert_to_markdown import DOWNLOADS_DIR, clean_sec_html


PROJECT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_DIR / "backend"
sys.path.insert(0, str(BACKEND_DIR))
os.chdir(BACKEND_DIR)

from app.config import settings  # noqa: E402
from app.database.models.document_chunk import DocumentChunk  # noqa: E402
from app.database.models.source_document import SourceDocument  # noqa: E402
from app.database.session import SessionLocal  # noqa: E402


DATA_DIR = PROJECT_DIR / "data"
MARKDOWN_DIR = DATA_DIR / "markdown"
MANIFEST_PATH = MARKDOWN_DIR / "manifest.json"
DEFAULT_MAX_TOKENS = 1500


def load_manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def filing_year(filing: dict) -> int:
    report_date = filing.get("report_date") or filing["filing_date"]
    return int(report_date[:4])


def matches_filters(filing: dict, company: str | None, year: int | None) -> bool:
    if company and filing["ticker"].upper() != company.upper():
        return False
    if year and filing_year(filing) != year:
        return False
    return True


def get_source_document(session, filing: dict) -> SourceDocument:
    document = session.scalar(
        select(SourceDocument)
        .where(SourceDocument.company == filing["ticker"])
        .where(SourceDocument.filing_type == filing["form"])
        .where(SourceDocument.filing_year == filing_year(filing))
        .where(SourceDocument.filing_url == filing["source_url"])
    )
    if document is None:
        raise RuntimeError(
            "Missing source_documents row for "
            f"{filing['ticker']} {filing['form']} {filing_year(filing)}. "
            "Run data/ingest_source_documents.py first."
        )
    return document


def existing_chunk_count(session, source_document_id) -> int:
    return session.scalar(
        select(func.count()).select_from(DocumentChunk).where(DocumentChunk.source_document_id == source_document_id)
    )


def clear_existing_chunks(session, source_document_id) -> None:
    session.execute(delete(DocumentChunk).where(DocumentChunk.source_document_id == source_document_id))


def safe_json(value: Any) -> Any:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, list | tuple | set):
        return [safe_json(item) for item in value]
    if isinstance(value, dict):
        return {str(key): safe_json(item) for key, item in value.items()}
    if hasattr(value, "model_dump"):
        return safe_json(value.model_dump(mode="json"))
    if hasattr(value, "__dict__"):
        return {
            key: safe_json(item)
            for key, item in vars(value).items()
            if not key.startswith("_") and key not in {"parent", "children"}
        }
    return str(value)


def chunk_metadata(filing: dict, chunk_index: int, chunk: Any, token_count: int) -> dict:
    meta = safe_json(getattr(chunk, "meta", None))
    headings = meta.get("headings") if isinstance(meta, dict) else None

    return {
        "ticker": filing["ticker"],
        "cik": filing["cik"],
        "filing_type": filing["form"],
        "filing_year": filing_year(filing),
        "filing_date": filing["filing_date"],
        "report_date": filing.get("report_date"),
        "accession_number": filing["accession_number"],
        "primary_document": filing["primary_document"],
        "source_url": filing["source_url"],
        "source_local_path": filing["source_local_path"],
        "markdown_local_path": filing["local_path"],
        "chunk_index": chunk_index,
        "chunker": "docling.HybridChunker",
        "embedding_model": settings.openai_embedding_model,
        "embedding_dimensions": settings.openai_embedding_dimensions,
        "token_count": token_count,
        "section": headings[-1] if headings else None,
        "headings": headings or [],
        "docling_meta": meta,
    }


def make_chunker(max_tokens: int) -> tuple[HybridChunker, OpenAITokenizer]:
    tokenizer = OpenAITokenizer(
        tokenizer=tiktoken.get_encoding("cl100k_base"),
        max_tokens=max_tokens,
    )
    return (
        HybridChunker(
            tokenizer=tokenizer,
            repeat_table_header=True,
            omit_header_on_overflow=True,
            merge_peers=True,
        ),
        tokenizer,
    )


def convert_html_to_docling_document(filing: dict, converter: DocumentConverter, clean_root: Path):
    source_path = DOWNLOADS_DIR / filing["source_local_path"]
    cleaned_path = clean_sec_html(source_path, clean_root)
    result = converter.convert(cleaned_path, raises_on_error=False)
    if result.status != ConversionStatus.SUCCESS:
        raise RuntimeError(f"Docling failed to convert {source_path.relative_to(DATA_DIR)}")
    return result.document


def iter_prepared_chunks(
    filing: dict,
    converter: DocumentConverter,
    chunker: HybridChunker,
    tokenizer: OpenAITokenizer,
    clean_root: Path,
) -> Iterable[tuple[str, dict]]:
    doc = convert_html_to_docling_document(filing, converter, clean_root)
    for index, chunk in enumerate(chunker.chunk(dl_doc=doc)):
        content = chunker.contextualize(chunk=chunk).strip()
        if not content:
            continue
        token_count = tokenizer.count_tokens(content)
        yield content, chunk_metadata(filing, index, chunk, token_count)


def embed_texts(client: OpenAI, texts: list[str]) -> list[list[float]]:
    response = client.embeddings.create(
        model=settings.openai_embedding_model,
        input=texts,
        dimensions=settings.openai_embedding_dimensions,
    )
    return [item.embedding for item in response.data]


def select_filings(company: str | None, year: int | None, limit_docs: int | None) -> list[dict]:
    filings = [
        filing
        for filing in load_manifest()["filings"]
        if matches_filters(filing, company=company, year=year)
    ]
    return filings[:limit_docs] if limit_docs is not None else filings


def ingest_document_chunks(args: argparse.Namespace) -> None:
    filings = select_filings(company=args.company, year=args.year, limit_docs=args.limit_docs)
    if not filings:
        raise RuntimeError("No filings matched the requested filters.")

    converter = DocumentConverter()
    chunker, tokenizer = make_chunker(max_tokens=args.max_tokens)
    openai_client = None if args.skip_embeddings or args.dry_run else OpenAI(api_key=settings.openai_api_key)
    inserted = 0
    skipped_documents = 0

    with tempfile.TemporaryDirectory(prefix="docling-chunk-cleaned-sec-") as clean_dir:
        clean_root = Path(clean_dir)
        with SessionLocal() as session:
            for filing in filings:
                source_document = get_source_document(session, filing)
                existing = existing_chunk_count(session, source_document.id)
                label = f"{filing['ticker']} {filing['form']} {filing_year(filing)}"

                if existing and not args.force:
                    skipped_documents += 1
                    print(f"Skipping {label}; already has {existing} chunk(s).")
                    continue
                if existing and args.force and not args.dry_run:
                    clear_existing_chunks(session, source_document.id)

                prepared_chunks = iter_prepared_chunks(filing, converter, chunker, tokenizer, clean_root)
                if args.limit_chunks is not None:
                    prepared_chunks = (chunk for _, chunk in zip(range(args.limit_chunks), prepared_chunks, strict=False))
                if args.one_chunk:
                    prepared_chunks = (chunk for _, chunk in zip(range(1), prepared_chunks, strict=False))

                chunk_batch = list(prepared_chunks)
                print(f"{label}: prepared {len(chunk_batch)} chunk(s).")
                if args.dry_run:
                    continue
                if not chunk_batch:
                    continue

                contents = [content for content, _ in chunk_batch]
                embeddings = [None] * len(contents) if args.skip_embeddings else embed_texts(openai_client, contents)

                for chunk_index, ((content, metadata), embedding) in enumerate(zip(chunk_batch, embeddings, strict=True)):
                    session.add(
                        DocumentChunk(
                            source_document_id=source_document.id,
                            chunk_index=chunk_index,
                            content=content,
                            chunk_metadata=metadata,
                            embedding=embedding,
                        )
                    )
                    inserted += 1

                if args.one_chunk:
                    break

            if args.dry_run:
                session.rollback()
            else:
                session.commit()

    print(f"Inserted {inserted} chunk(s); skipped {skipped_documents} document(s).")


def main() -> None:
    parser = argparse.ArgumentParser(description="Chunk source filings with Docling and insert document_chunks.")
    parser.add_argument("--company", help="Only process one ticker, e.g. AAPL.")
    parser.add_argument("--year", type=int, help="Only process one filing/report year.")
    parser.add_argument("--limit-docs", type=int, help="Only process the first N matching filings.")
    parser.add_argument("--limit-chunks", type=int, help="Only insert the first N chunks per filing.")
    parser.add_argument("--one-chunk", action="store_true", help="Insert exactly one chunk total, for a cheap smoke test.")
    parser.add_argument("--max-tokens", type=int, default=DEFAULT_MAX_TOKENS, help="Max embedding tokens per chunk.")
    parser.add_argument("--skip-embeddings", action="store_true", help="Insert chunks with NULL embeddings.")
    parser.add_argument("--force", action="store_true", help="Delete and rebuild existing chunks for matching filings.")
    parser.add_argument("--dry-run", action="store_true", help="Chunk locally but do not write rows or call OpenAI.")
    args = parser.parse_args()

    ingest_document_chunks(args)


if __name__ == "__main__":
    main()
