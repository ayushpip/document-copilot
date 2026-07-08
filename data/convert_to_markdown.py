# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "beautifulsoup4==4.15.0",
#   "docling==2.107.0",
# ]
# ///
from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from bs4 import BeautifulSoup, Tag
from docling.datamodel.base_models import ConversionStatus
from docling.document_converter import DocumentConverter
from docling_core.types.doc import ImageRefMode


DATA_DIR = Path(__file__).resolve().parent
DOWNLOADS_DIR = DATA_DIR / "downloads"
MARKDOWN_DIR = DATA_DIR / "markdown"
MANIFEST_PATH = DOWNLOADS_DIR / "manifest.json"
HIDDEN_IXBRL_TAGS = {"ix:header", "ix:hidden", "ix:references", "ix:resources"}
REMOVE_TAGS = {"script", "style", "meta", "link", "noscript"}
DROP_ATTRIBUTES = {
    "align",
    "class",
    "height",
    "id",
    "onclick",
    "onmouseout",
    "onmouseover",
    "style",
    "valign",
    "width",
}


def markdown_path_for(source_path: Path) -> Path:
    relative_path = source_path.relative_to(DOWNLOADS_DIR)
    return (MARKDOWN_DIR / relative_path).with_suffix(".md")


def load_manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def clean_text(value: str) -> str:
    return " ".join(value.replace("\xa0", " ").split())


def is_year(value: str) -> bool:
    value = value.strip()
    return len(value) == 4 and value.isdigit() and value.startswith("20")


def tag_name(tag: Tag) -> str:
    return tag.name.lower() if tag.name else ""


def is_hidden(tag: Tag) -> bool:
    if tag.attrs is None:
        return False

    style = (tag.get("style") or "").replace(" ", "").lower()
    return "display:none" in style or "visibility:hidden" in style


def clean_table(table: Tag) -> None:
    for cell in table.find_all(["td", "th"]):
        if not clean_text(cell.get_text(" ", strip=True)):
            cell.decompose()
            continue

        # SEC filings often use 3-column visual grids with colspan. Docling
        # expands those spans into repeated Markdown cells, so flatten them.
        cell.attrs.pop("colspan", None)
        cell.attrs.pop("rowspan", None)

    for row in table.find_all("tr"):
        cells = row.find_all(["td", "th"], recursive=False)
        if not cells:
            row.decompose()
            continue

        previous_text = ""
        for cell in list(cells):
            text = clean_text(cell.get_text(" ", strip=True))
            if text and text == previous_text:
                cell.decompose()
                continue
            previous_text = text

    for tag in table.find_all(True):
        for attribute in DROP_ATTRIBUTES:
            tag.attrs.pop(attribute, None)


def clean_sec_html(source_path: Path, clean_root: Path) -> Path:
    soup = BeautifulSoup(source_path.read_text(encoding="utf-8", errors="ignore"), "html.parser")

    for tag in soup.find_all(True):
        if tag.attrs is None:
            continue

        name = tag_name(tag)
        if name in REMOVE_TAGS or name in HIDDEN_IXBRL_TAGS or is_hidden(tag):
            tag.decompose()

    for tag in soup.find_all(True):
        if tag.attrs is None:
            continue

        if tag_name(tag).startswith("ix:"):
            tag.unwrap()

    for table in soup.find_all("table"):
        clean_table(table)

    for tag in soup.find_all(True):
        if tag.attrs is None:
            continue

        for attribute in DROP_ATTRIBUTES:
            tag.attrs.pop(attribute, None)

    cleaned_path = clean_root / source_path.relative_to(DOWNLOADS_DIR)
    cleaned_path.parent.mkdir(parents=True, exist_ok=True)
    cleaned_path.write_text(str(soup), encoding="utf-8")
    return cleaned_path


def split_markdown_table_row(line: str) -> list[str]:
    return [clean_text(cell) for cell in line.strip().strip("|").split("|")]


def markdown_table_row(cells: list[str]) -> str:
    return "| " + " | ".join(cells) + " |"


def is_markdown_table_separator(line: str) -> bool:
    cells = split_markdown_table_row(line)
    return bool(cells) and all(set(cell.replace(" ", "")) <= {"-", ":"} and "-" in cell for cell in cells)


def normalize_financial_table(lines: list[str]) -> list[str]:
    rows = [split_markdown_table_row(line) for line in lines]
    year_row_index = next(
        (
            index
            for index, row in enumerate(rows)
            if len([cell for cell in row if is_year(cell)]) >= 2
        ),
        None,
    )
    if year_row_index is None:
        return lines

    years = [cell for cell in rows[year_row_index] if is_year(cell)]
    if len(years) < 2:
        return lines

    normalized = [
        markdown_table_row([""] + years),
        markdown_table_row(["---"] * (len(years) + 1)),
    ]

    for row in rows[year_row_index + 1 :]:
        if not any(row):
            continue

        label = row[0]
        values = [
            cell
            for cell in row[1:]
            if cell and cell not in {"$", "%"}
        ]

        if not label and not values:
            continue

        normalized.append(markdown_table_row([label] + values[: len(years)] + [""] * max(0, len(years) - len(values))))

    return normalized


def normalize_markdown_tables(markdown_path: Path) -> None:
    lines = markdown_path.read_text(encoding="utf-8").splitlines()
    normalized_lines: list[str] = []
    table_block: list[str] = []

    def flush_table() -> None:
        nonlocal table_block
        if not table_block:
            return

        normalized_lines.extend(normalize_financial_table(table_block))
        table_block = []

    for line in lines:
        if line.strip().startswith("|") and line.strip().endswith("|"):
            if is_markdown_table_separator(line):
                continue

            table_block.append(line)
            continue

        flush_table()
        normalized_lines.append(line)

    flush_table()

    markdown_path.write_text("\n".join(normalized_lines).rstrip() + "\n", encoding="utf-8")


def write_markdown_manifest(source_manifest: dict, filings: list[dict], converted_paths: dict[str, str]) -> None:
    manifest = {
        **source_manifest,
        "source_manifest": str(MANIFEST_PATH.relative_to(DATA_DIR)),
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "converted_format": "markdown",
        "converted_count": len(filings),
        "filings": [],
    }

    for filing in filings:
        source_local_path = filing["local_path"]
        markdown_local_path = converted_paths[source_local_path]
        manifest["filings"].append(
            {
                **filing,
                "source_local_path": source_local_path,
                "local_path": markdown_local_path,
            }
        )

    (MARKDOWN_DIR / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )


def convert_filings(force: bool, limit: int | None = None) -> None:
    source_manifest = load_manifest()
    filings = source_manifest["filings"][:limit] if limit is not None else source_manifest["filings"]
    source_paths = [DOWNLOADS_DIR / filing["local_path"] for filing in filings]

    missing_paths = [path for path in source_paths if not path.exists()]
    if missing_paths:
        missing = "\n".join(str(path.relative_to(DATA_DIR)) for path in missing_paths)
        raise FileNotFoundError(f"Manifest references missing files:\n{missing}")

    if force and MARKDOWN_DIR.exists():
        shutil.rmtree(MARKDOWN_DIR)

    MARKDOWN_DIR.mkdir(parents=True, exist_ok=True)

    converter = DocumentConverter()
    converted_paths: dict[str, str] = {}

    with tempfile.TemporaryDirectory(prefix="docling-cleaned-sec-") as clean_dir:
        clean_root = Path(clean_dir)

        for source_path in source_paths:
            output_path = markdown_path_for(source_path)
            converted_paths[str(source_path.relative_to(DOWNLOADS_DIR))] = str(output_path.relative_to(MARKDOWN_DIR))

            if output_path.exists() and not force:
                print(f"Skipping existing {output_path.relative_to(DATA_DIR)}")
                continue

            output_path.parent.mkdir(parents=True, exist_ok=True)

            print(f"Cleaning {source_path.relative_to(DATA_DIR)}", flush=True)
            cleaned_path = clean_sec_html(source_path, clean_root)

            print(f"Converting {source_path.relative_to(DATA_DIR)}", flush=True)
            result = converter.convert(cleaned_path, raises_on_error=False)

            if result.status != ConversionStatus.SUCCESS:
                raise RuntimeError(f"Docling failed to convert {source_path.relative_to(DATA_DIR)}")

            result.document.save_as_markdown(
                output_path,
                image_mode=ImageRefMode.PLACEHOLDER,
                compact_tables=True,
                include_annotations=False,
            )
            normalize_markdown_tables(output_path)
            print(f"Converted {source_path.relative_to(DATA_DIR)} -> {output_path.relative_to(DATA_DIR)}", flush=True)

    write_markdown_manifest(source_manifest, filings, converted_paths)
    print(f"Wrote {MARKDOWN_DIR.relative_to(DATA_DIR) / 'manifest.json'}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert downloaded SEC HTML filings to Markdown with Docling.")
    parser.add_argument("--force", action="store_true", help="Recreate data/markdown before converting.")
    parser.add_argument("--limit", type=int, help="Convert only the first N filings from the manifest.")
    args = parser.parse_args()

    convert_filings(force=args.force, limit=args.limit)


if __name__ == "__main__":
    main()
