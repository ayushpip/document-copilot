from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from sqlalchemy import select

PROJECT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_DIR / "backend"
sys.path.insert(0, str(BACKEND_DIR))
os.chdir(BACKEND_DIR)


DATA_DIR = Path(__file__).resolve().parent
MARKDOWN_DIR = DATA_DIR / "markdown"
MANIFEST_PATH = MARKDOWN_DIR / "manifest.json"


def load_manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def filing_year(filing: dict) -> int:
    report_date = filing.get("report_date") or filing["filing_date"]
    return int(report_date[:4])


def source_document_exists(session, filing: dict) -> bool:
    from app.database.models.source_document import SourceDocument

    query = (
        select(SourceDocument.id)
        .where(SourceDocument.company == filing["ticker"])
        .where(SourceDocument.filing_type == filing["form"])
        .where(SourceDocument.filing_year == filing_year(filing))
        .where(SourceDocument.filing_url == filing["source_url"])
        .limit(1)
    )
    return session.execute(query).first() is not None


def build_source_document(filing: dict):
    from app.database.models.source_document import SourceDocument

    markdown_path = MARKDOWN_DIR / filing["local_path"]
    if not markdown_path.exists():
        raise FileNotFoundError(f"Missing Markdown file: {markdown_path.relative_to(DATA_DIR)}")

    return SourceDocument(
        company=filing["ticker"],
        filing_type=filing["form"],
        filing_year=filing_year(filing),
        filing_url=filing["source_url"],
        content=markdown_path.read_text(encoding="utf-8"),
    )


def ingest_source_documents(dry_run: bool) -> None:
    from app.database.session import SessionLocal

    manifest = load_manifest()
    filings = manifest["filings"]
    inserted = 0
    skipped = 0

    with SessionLocal() as session:
        for filing in filings:
            label = f"{filing['ticker']} {filing['form']} {filing_year(filing)}"
            if source_document_exists(session, filing):
                skipped += 1
                print(f"Skipping existing {label}")
                continue

            document = build_source_document(filing)
            inserted += 1
            print(f"Inserting {label}")

            if not dry_run:
                session.add(document)

        if dry_run:
            session.rollback()
        else:
            session.commit()

    action = "Would insert" if dry_run else "Inserted"
    print(f"{action} {inserted} source document(s); skipped {skipped}.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Load converted Markdown filings into source_documents.")
    parser.add_argument("--dry-run", action="store_true", help="Check what would be inserted without writing rows.")
    args = parser.parse_args()

    ingest_source_documents(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
