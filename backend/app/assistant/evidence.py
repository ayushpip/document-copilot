from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable
from uuid import UUID

from pydantic import BaseModel, Field

from app.retrieval import RetrievedPassage, RetrievalResult


YEAR_PATTERN = re.compile(r"\b(20\d{2})\b")
NUMBER_PATTERN = re.compile(r"\(?-?\$?\s*([0-9][0-9,]*(?:\.[0-9]+)?)\s*\)?")
ASSIGNMENT_PATTERN = re.compile(r"([^.,]+?),\s*(\d+)\s*=\s*([^.]*)\.")
FLATTENED_ASSIGNMENT_PATTERN = re.compile(
    r"(?P<label>.+?),\s*(?P<index>\d+)\s*=\s*(?P<value>.*?)(?=\.\s+[^.]+?,\s*\d+\s*=|$)",
    re.DOTALL,
)
TABLE_SEPARATOR_PATTERN = re.compile(r"^\|\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?$")
PROSE_REVENUE_VALUE_PATTERN = re.compile(
    r"\b(?P<label>Data Center|Gaming|Professional Visualization|Automotive)\s+revenue\s+"
    r"for fiscal year (?P<year>20\d{2}) was \$(?P<value>[0-9]+(?:\.[0-9]+)?)\s*(?P<scale>billion|million)",
    re.IGNORECASE,
)
PROSE_TOTAL_REVENUE_VALUE_PATTERN = re.compile(
    r"(?:^|[.\n]\s*)Revenue\s+for fiscal year (?P<year>20\d{2}) was "
    r"\$(?P<value>[0-9]+(?:\.[0-9]+)?)\s*(?P<scale>billion|million)",
    re.IGNORECASE,
)
PROSE_REVENUE_GROWTH_PATTERN = re.compile(
    r"\b(?P<label>Data Center|Gaming|Professional Visualization|Automotive)\s+revenue\s+"
    r"for fiscal year (?P<year>20\d{2}) was (?P<direction>up|down) (?P<value>[0-9]+(?:\.[0-9]+)?)%",
    re.IGNORECASE,
)
PROSE_REVENUE_VALUE_AND_GROWTH_PATTERN = re.compile(
    r"\b(?P<label>Data Center|Gaming|Professional Visualization|Automotive)\s+revenue\s+"
    r"for fiscal year (?P<year>20\d{2}) was \$[0-9]+(?:\.[0-9]+)?\s*(?:billion|million), "
    r"(?P<direction>up|down) (?P<value>[0-9]+(?:\.[0-9]+)?)%",
    re.IGNORECASE,
)
KNOWN_FINANCIAL_METRICS = {
    "revenue",
    "total revenue",
    "operating income",
    "net sales",
    "total net sales",
    "sales",
    "gross margin",
    "cost of revenue",
    "operating expenses",
}
KNOWN_COMPANIES = {
    "apple": "AAPL",
    "aapl": "AAPL",
    "microsoft": "MSFT",
    "msft": "MSFT",
    "amazon": "AMZN",
    "amzn": "AMZN",
    "alphabet": "GOOGL",
    "google": "GOOGL",
    "googl": "GOOGL",
    "nvidia": "NVDA",
    "nvda": "NVDA",
}
KNOWN_SEGMENTS_AND_PRODUCTS = {
    "iphone",
    "services",
    "mac",
    "ipad",
    "wearables",
    "intelligent cloud",
    "server products and cloud services",
    "azure",
    "data center",
    "gaming",
}
KNOWN_REQUESTED_METRICS = KNOWN_SEGMENTS_AND_PRODUCTS | KNOWN_FINANCIAL_METRICS


class EvidenceRow(BaseModel):
    """One structured fact extracted from a retrieved filing passage."""

    company: str
    filing_year: int
    filing_type: str
    metric: str
    value: float
    unit: str = "USD millions"
    source_filing_year: int
    source_chunk_id: UUID
    source_chunk_index: int
    quote: str = Field(min_length=1)


class CalculationRow(BaseModel):
    """One deterministic calculation derived from structured evidence rows."""

    label: str
    value: float
    unit: str
    formula: str
    source_chunk_ids: list[UUID]


class CoverageGap(BaseModel):
    """A requested evidence dimension that was not found in extracted rows."""

    dimension: str
    value: str


class EvidenceBrief(BaseModel):
    """Evidence and calculations available to the final answer agent."""

    rows: list[EvidenceRow] = Field(default_factory=list)
    calculations: list[CalculationRow] = Field(default_factory=list)
    coverage_gaps: list[CoverageGap] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)

    @property
    def has_evidence(self) -> bool:
        return bool(self.rows)


class AnswerPlan(BaseModel):
    """Structured evidence and guidance supplied to the final answer agent."""

    evidence_brief: EvidenceBrief
    interpretation_outline: list[str] = Field(default_factory=list)


class EvidenceValidationError(ValueError):
    """Raised when an answer's numeric claims are not backed by structured evidence."""


def _split_markdown_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _is_table_row(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith("|") and stripped.endswith("|") and not TABLE_SEPARATOR_PATTERN.match(stripped)


def _parse_number(value: str) -> float | None:
    match = NUMBER_PATTERN.search(value)
    if match is None:
        return None

    number = float(match.group(1).replace(",", ""))
    stripped_value = value.strip()
    if stripped_value.startswith("-"):
        return -number
    if stripped_value.startswith("(") and stripped_value.endswith(")"):
        return -number
    return number


def _normalize_metric(metric: str, parent_metric: str | None = None) -> str:
    clean_metric = " ".join(metric.replace("**", "").split())
    if parent_metric:
        if parent_metric.lower() in KNOWN_FINANCIAL_METRICS:
            return f"{clean_metric} {parent_metric}".strip()
        return f"{parent_metric} {clean_metric}".strip()
    return clean_metric


def _year_headers(cells: Iterable[str]) -> list[int | None]:
    headers = []
    for cell in cells:
        match = YEAR_PATTERN.search(cell)
        headers.append(int(match.group(1)) if match else None)
    return headers


def _nearby_table_context(lines: list[str], table_start: int) -> str:
    context_lines = []
    for line in reversed(lines[max(0, table_start - 8) : table_start]):
        clean_line = line.strip()
        if clean_line:
            context_lines.append(clean_line)
        if len(context_lines) >= 4:
            break
    return " ".join(reversed(context_lines)).lower()


def _infer_parent_metric(cells: list[str], current_parent_metric: str | None) -> str | None:
    first_cell = cells[0].strip().lower() if cells else ""
    if first_cell and all(not _parse_number(cell) for cell in cells[1:]):
        return " ".join(cells[0].strip().split())
    return current_parent_metric


def _table_rows_from_passage(passage: RetrievedPassage) -> list[EvidenceRow]:
    lines = passage.content.splitlines()
    rows = []
    index = 0

    while index < len(lines):
        if not _is_table_row(lines[index]):
            index += 1
            continue

        table_start = index
        table_lines = []
        while index < len(lines) and (_is_table_row(lines[index]) or TABLE_SEPARATOR_PATTERN.match(lines[index].strip())):
            if _is_table_row(lines[index]):
                table_lines.append(lines[index])
            index += 1

        if len(table_lines) < 2:
            continue

        header_cells = _split_markdown_row(table_lines[0])
        years = _year_headers(header_cells)
        if not any(years):
            continue

        parent_metric = None
        context = _nearby_table_context(lines, table_start)
        unit = "USD millions" if "in millions" in context or "$" in context else "numeric"

        for row_line in table_lines[1:]:
            cells = _split_markdown_row(row_line)
            if len(cells) < 2:
                continue

            parent_metric = _infer_parent_metric(cells, parent_metric)
            if cells[0].strip().lower() in KNOWN_FINANCIAL_METRICS and all(not _parse_number(cell) for cell in cells[1:]):
                continue

            metric = _normalize_metric(cells[0], parent_metric)
            if not metric:
                continue

            for cell_index, cell in enumerate(cells[1:], start=1):
                if cell_index >= len(years) or years[cell_index] is None:
                    continue
                value = _parse_number(cell)
                if value is None:
                    continue
                rows.append(
                    EvidenceRow(
                        company=passage.company,
                        filing_year=years[cell_index] or passage.filing_year,
                        filing_type=passage.filing_type,
                        metric=metric,
                        value=value,
                        unit=unit,
                        source_filing_year=passage.filing_year,
                        source_chunk_id=passage.chunk_id,
                        source_chunk_index=passage.chunk_index,
                        quote=row_line.strip(),
                    )
                )

    return rows


def _flattened_rows_from_passage(passage: RetrievedPassage, text: str) -> list[EvidenceRow]:
    rows = []
    year_by_index: dict[str, int] = {}
    section_label: str | None = None
    current_metric: str | None = None
    value_counts: dict[str, int] = defaultdict(int)

    for match in ASSIGNMENT_PATTERN.finditer(text):
        label = " ".join(match.group(1).split())
        raw_value = match.group(3).strip()
        clean_value = raw_value.strip("$ ").strip()
        label_lower = label.lower()
        ordered_years = [year for _, year in sorted(year_by_index.items(), key=lambda item: int(item[0]))]

        year_match = YEAR_PATTERN.fullmatch(clean_value)
        if year_match:
            year_by_index[match.group(2)] = int(year_match.group(1))
            continue

        value = _parse_number(raw_value)
        if value is None:
            if label_lower in KNOWN_FINANCIAL_METRICS:
                current_metric = label
            elif clean_value in {"", "."}:
                section_label = label
            continue

        if "%" in raw_value or not ordered_years:
            continue

        if label_lower in KNOWN_FINANCIAL_METRICS:
            metric = _normalize_metric(label, section_label)
        elif current_metric:
            metric = _normalize_metric(label, current_metric)
        else:
            continue

        value_index = value_counts[metric]
        if value_index >= len(ordered_years):
            continue
        value_counts[metric] += 1

        rows.append(
            EvidenceRow(
                company=passage.company,
                filing_year=ordered_years[value_index],
                filing_type=passage.filing_type,
                metric=metric,
                value=value,
                unit="USD millions",
                source_filing_year=passage.filing_year,
                source_chunk_id=passage.chunk_id,
                source_chunk_index=passage.chunk_index,
                quote=match.group(0).strip(),
            )
        )

    return rows


def _docling_assignment_rows_from_passage(passage: RetrievedPassage, text: str) -> list[EvidenceRow]:
    """Extract rows from Docling's flattened `Label, n = value.` table format."""

    assignments = [
        (
            " ".join(match.group("label").strip(" .").split()),
            int(match.group("index")),
            match.group("value").strip().rstrip(".").strip(),
            match.group(0).strip().rstrip("."),
        )
        for match in FLATTENED_ASSIGNMENT_PATTERN.finditer(text)
    ]
    if not assignments:
        return []

    indexed_years: dict[int, int] = {}
    header_years: list[int] = []
    for label, index, raw_value, _quote in assignments[:20]:
        label_year = YEAR_PATTERN.fullmatch(label)
        value_year = YEAR_PATTERN.fullmatch(raw_value)
        if value_year:
            indexed_years[index] = int(value_year.group(0))
        if label_year and value_year:
            header = int(label_year.group(0))
            if not header_years:
                header_years = [header]
            header_years.append(int(value_year.group(0)))

    rows = []
    current_metric: str | None = None
    index = 0
    while index < len(assignments):
        label = assignments[index][0]
        run = []
        while index < len(assignments) and assignments[index][0] == label:
            run.append(assignments[index])
            index += 1

        if YEAR_PATTERN.fullmatch(label):
            continue

        label_lower = label.lower()
        numeric_values = [
            (assignment_index, raw_value, parsed_value, quote)
            for _label, assignment_index, raw_value, quote in run
            if "%" not in raw_value
            for parsed_value in [_parse_number(raw_value)]
            if parsed_value is not None
        ]
        if not numeric_values:
            if label_lower in KNOWN_FINANCIAL_METRICS:
                current_metric = label
            continue

        if label_lower in KNOWN_FINANCIAL_METRICS:
            metric = _normalize_metric(label)
        elif current_metric:
            metric = _normalize_metric(label, current_metric)
        elif header_years:
            metric = _normalize_metric(label)
        else:
            continue

        if header_years and len(numeric_values) == len(header_years):
            year_value_pairs = [
                (year, raw_value, parsed_value, quote)
                for year, (_assignment_index, raw_value, parsed_value, quote) in zip(
                    header_years, numeric_values, strict=False
                )
            ]
        else:
            year_value_pairs = [
                (indexed_years[assignment_index], raw_value, parsed_value, quote)
                for assignment_index, raw_value, parsed_value, quote in numeric_values
                if assignment_index in indexed_years
            ]

        for year, raw_value, parsed_value, quote in year_value_pairs:
            rows.append(
                EvidenceRow(
                    company=passage.company,
                    filing_year=year,
                    filing_type=passage.filing_type,
                    metric=metric,
                    value=parsed_value,
                    unit="USD millions" if "$" in raw_value or "sales" in metric.lower() or "revenue" in metric.lower() else "numeric",
                    source_filing_year=passage.filing_year,
                    source_chunk_id=passage.chunk_id,
                    source_chunk_index=passage.chunk_index,
                    quote=quote,
                )
            )

    return rows


def _scale_to_millions(value: float, scale: str) -> float:
    return value * 1000 if scale.lower() == "billion" else value


def _prose_rows_from_passage(passage: RetrievedPassage, text: str) -> list[EvidenceRow]:
    rows = []
    for match in PROSE_REVENUE_VALUE_PATTERN.finditer(text):
        label = " ".join(match.group("label").split())
        rows.append(
            EvidenceRow(
                company=passage.company,
                filing_year=int(match.group("year")),
                filing_type=passage.filing_type,
                metric=f"{label} Revenue",
                value=_scale_to_millions(float(match.group("value")), match.group("scale")),
                unit="USD millions",
                source_filing_year=passage.filing_year,
                source_chunk_id=passage.chunk_id,
                source_chunk_index=passage.chunk_index,
                quote=match.group(0).strip(),
            )
        )

    for match in PROSE_TOTAL_REVENUE_VALUE_PATTERN.finditer(text):
        rows.append(
            EvidenceRow(
                company=passage.company,
                filing_year=int(match.group("year")),
                filing_type=passage.filing_type,
                metric="Total Revenue",
                value=_scale_to_millions(float(match.group("value")), match.group("scale")),
                unit="USD millions",
                source_filing_year=passage.filing_year,
                source_chunk_id=passage.chunk_id,
                source_chunk_index=passage.chunk_index,
                quote=match.group(0).strip(),
            )
        )

    for match in PROSE_REVENUE_GROWTH_PATTERN.finditer(text):
        direction = -1 if match.group("direction").lower() == "down" else 1
        rows.append(
            EvidenceRow(
                company=passage.company,
                filing_year=int(match.group("year")),
                filing_type=passage.filing_type,
                metric=f"{' '.join(match.group('label').split())} Revenue growth",
                value=direction * float(match.group("value")),
                unit="%",
                source_filing_year=passage.filing_year,
                source_chunk_id=passage.chunk_id,
                source_chunk_index=passage.chunk_index,
                quote=match.group(0).strip(),
            )
        )

    for match in PROSE_REVENUE_VALUE_AND_GROWTH_PATTERN.finditer(text):
        direction = -1 if match.group("direction").lower() == "down" else 1
        rows.append(
            EvidenceRow(
                company=passage.company,
                filing_year=int(match.group("year")),
                filing_type=passage.filing_type,
                metric=f"{' '.join(match.group('label').split())} Revenue growth",
                value=direction * float(match.group("value")),
                unit="%",
                source_filing_year=passage.filing_year,
                source_chunk_id=passage.chunk_id,
                source_chunk_index=passage.chunk_index,
                quote=match.group(0).strip(),
            )
        )

    return rows


def extract_evidence(retrieval_result: RetrievalResult) -> list[EvidenceRow]:
    """Extract structured numeric evidence from retrieved markdown tables."""

    rows = []
    seen = set()

    for passage in retrieval_result.passages:
        passage_rows = _table_rows_from_passage(passage)
        for text in [passage.content, *passage.neighbor_chunks]:
            passage_rows.extend(_docling_assignment_rows_from_passage(passage, text))
            passage_rows.extend(_flattened_rows_from_passage(passage, text))
            passage_rows.extend(_prose_rows_from_passage(passage, text))

        for row in passage_rows:
            key = (row.company, row.filing_year, row.metric.lower(), row.value)
            if key in seen:
                continue
            seen.add(key)
            rows.append(row)

    return rows


def _filter_relevant_rows(question: str, rows: list[EvidenceRow]) -> list[EvidenceRow]:
    filtered_rows = rows
    companies = requested_companies(question)
    years = requested_years(question)
    terms = requested_terms(question)
    lower_question = question.lower()
    include_total_rows = any(term in lower_question for term in ("mix", "share", "total", "percentage of", "proportion"))
    segment_terms = terms & KNOWN_SEGMENTS_AND_PRODUCTS
    metric_terms = terms & KNOWN_FINANCIAL_METRICS
    exact_total_metric_terms = {
        term
        for term in ("total net sales", "total revenue")
        if term in terms and not any(word in lower_question for word in ("percentage", "proportion", "mix", "share", "portion"))
    }

    if companies:
        filtered_rows = [row for row in filtered_rows if row.company in companies]
    if years:
        filtered_rows = [row for row in filtered_rows if row.filing_year in years]
    if terms:
        relevant_rows = [
            row
            for row in filtered_rows
            if (
                exact_total_metric_terms
                and _canonical_metric(row.metric) in exact_total_metric_terms
            )
            or (
                not exact_total_metric_terms
                and segment_terms
                and any(term in row.metric.lower() for term in segment_terms)
                and (
                    not metric_terms
                    or any(term in row.metric.lower() for term in metric_terms)
                    or _canonical_metric(row.metric) in segment_terms
                )
            )
            or (
                not exact_total_metric_terms
                and segment_terms
                and include_total_rows
                and row.metric.lower() in {"total net sales", "total revenue"}
            )
            or (
                not exact_total_metric_terms
                and not segment_terms
                and (
                    any(term in row.metric.lower() for term in terms)
                    or (include_total_rows and row.metric.lower() in {"total net sales", "total revenue"})
                )
            )
        ]
        filtered_rows = relevant_rows

    return filtered_rows


def calculate_growth_percentage(current: EvidenceRow, previous: EvidenceRow) -> CalculationRow | None:
    if previous.value == 0 or current.unit == "%" or previous.unit == "%" or current.unit != previous.unit:
        return None

    growth = ((current.value - previous.value) / previous.value) * 100
    return CalculationRow(
        label=f"{current.company} {current.metric} growth {previous.filing_year}-{current.filing_year}",
        value=round(growth, 1),
        unit="%",
        formula=f"(({current.value} - {previous.value}) / {previous.value}) * 100",
        source_chunk_ids=[previous.source_chunk_id, current.source_chunk_id],
    )


def calculate_absolute_change(current: EvidenceRow, previous: EvidenceRow) -> CalculationRow:
    change = current.value - previous.value
    return CalculationRow(
        label=f"{current.company} {current.metric} change {previous.filing_year}-{current.filing_year}",
        value=round(change, 1),
        unit=current.unit,
        formula=f"{current.value} - {previous.value}",
        source_chunk_ids=[previous.source_chunk_id, current.source_chunk_id],
    )


def calculate_margin_percentage(numerator: EvidenceRow, denominator: EvidenceRow) -> CalculationRow | None:
    if denominator.value == 0 or numerator.unit == "%" or denominator.unit == "%":
        return None

    margin = (numerator.value / denominator.value) * 100
    metric_prefix = _canonical_metric(numerator.metric).removesuffix(" operating income").strip()
    label_metric = f"{metric_prefix} operating margin" if metric_prefix else "operating margin"
    return CalculationRow(
        label=f"{numerator.company} {label_metric} {numerator.filing_year}",
        value=round(margin, 1),
        unit="%",
        formula=f"({numerator.value} / {denominator.value}) * 100",
        source_chunk_ids=[numerator.source_chunk_id, denominator.source_chunk_id],
    )


def _canonical_metric(metric: str) -> str:
    metric = metric.lower().replace("(1)", "").replace("(2)", "").replace("(3)", "")
    return " ".join(metric.split())


def _build_calculations(rows: list[EvidenceRow]) -> list[CalculationRow]:
    calculations = []
    seen_calculations = set()
    conflicted_keys = {
        (row.company, row.filing_year, _canonical_metric(row.metric), row.source_filing_year)
        for row in rows
        if len(
            {
                candidate.value
                for candidate in rows
                if candidate.company == row.company
                and candidate.filing_year == row.filing_year
                and _canonical_metric(candidate.metric) == _canonical_metric(row.metric)
                and candidate.source_filing_year == row.source_filing_year
            }
        )
        > 1
    }
    rows_by_company_metric_source: dict[tuple[str, str, int], list[EvidenceRow]] = defaultdict(list)
    rows_by_company_year_source: dict[tuple[str, int, int], list[EvidenceRow]] = defaultdict(list)

    for row in rows:
        if (row.company, row.filing_year, _canonical_metric(row.metric), row.source_filing_year) in conflicted_keys:
            continue
        rows_by_company_metric_source[(row.company, _canonical_metric(row.metric), row.source_filing_year)].append(row)
        rows_by_company_year_source[(row.company, row.filing_year, row.source_filing_year)].append(row)

    for metric_rows in rows_by_company_metric_source.values():
        sorted_rows = sorted(metric_rows, key=lambda row: row.filing_year)
        for previous, current in zip(sorted_rows, sorted_rows[1:], strict=False):
            if current.filing_year != previous.filing_year + 1:
                continue
            for calculation in [
                calculate_growth_percentage(current, previous),
                calculate_absolute_change(current, previous),
            ]:
                if calculation and calculation.label not in seen_calculations:
                    seen_calculations.add(calculation.label)
                    calculations.append(calculation)

    for company_year_rows in rows_by_company_year_source.values():
        income_rows = [row for row in company_year_rows if _canonical_metric(row.metric).endswith("operating income")]
        revenue_rows = [row for row in company_year_rows if _canonical_metric(row.metric).endswith("revenue")]
        for operating_income in income_rows:
            income_metric = _canonical_metric(operating_income.metric).removesuffix(" operating income").strip()
            revenue = next(
                (
                    row
                    for row in revenue_rows
                    if _canonical_metric(row.metric).removesuffix(" revenue").strip() == income_metric
                ),
                None,
            )
            if revenue:
                calculation = calculate_margin_percentage(operating_income, revenue)
                if calculation and calculation.label not in seen_calculations:
                    seen_calculations.add(calculation.label)
                    calculations.append(calculation)

    return calculations


def _requested_years(question: str) -> set[int]:
    years = {int(match.group(1)) for match in YEAR_PATTERN.finditer(question)}
    range_match = re.search(r"\b(20\d{2})\s*[-–]\s*(20\d{2})\b", question)
    if range_match:
        start_year = int(range_match.group(1))
        end_year = int(range_match.group(2))
        years.update(range(start_year, end_year + 1))
    return years


def requested_companies(question: str) -> set[str]:
    lower_question = question.lower()
    return {ticker for name, ticker in KNOWN_COMPANIES.items() if re.search(rf"\b{re.escape(name)}\b", lower_question)}


def requested_terms(question: str) -> set[str]:
    lower_question = question.lower()
    terms = {term for term in KNOWN_REQUESTED_METRICS if re.search(rf"\b{re.escape(term)}\b", lower_question)}
    if "operating margin" in lower_question:
        terms.update({"revenue", "operating income"})
    return terms


def requested_years(question: str) -> set[int]:
    return _requested_years(question)


def _coverage_gaps(question: str, rows: list[EvidenceRow]) -> list[CoverageGap]:
    gaps = []
    requested_years = _requested_years(question)
    available_years = {row.filing_year for row in rows}
    gaps.extend(
        CoverageGap(dimension="filing_year", value=str(year))
        for year in sorted(requested_years)
        if year not in available_years
    )

    available_companies = {row.company for row in rows}
    gaps.extend(CoverageGap(dimension="company", value=company) for company in sorted(requested_companies(question)) if company not in available_companies)

    available_metrics = " ".join(row.metric.lower() for row in rows)
    gaps.extend(
        CoverageGap(dimension="segment_or_product", value=term)
        for term in sorted(requested_terms(question))
        if term not in available_metrics
    )
    return gaps


def _evidence_conflicts(rows: list[EvidenceRow]) -> list[str]:
    values_by_key: dict[tuple[str, int, str], set[float]] = defaultdict(set)
    for row in rows:
        values_by_key[(row.company, row.filing_year, _canonical_metric(row.metric))].add(row.value)

    conflicts = [
        f"{company} {metric} {year} has multiple extracted values: "
        f"{', '.join(f'{value:g}' for value in sorted(values))}"
        for (company, year, metric), values in sorted(values_by_key.items())
        if len(values) > 1
    ]
    rows_by_company_metric: dict[tuple[str, str], list[EvidenceRow]] = defaultdict(list)
    for row in rows:
        rows_by_company_metric[(row.company, _canonical_metric(row.metric))].append(row)

    for (company, metric), metric_rows in sorted(rows_by_company_metric.items()):
        sources_by_year: dict[int, set[int]] = defaultdict(set)
        for row in metric_rows:
            sources_by_year[row.filing_year].add(row.source_filing_year)
        for previous_year, current_year in zip(sorted(sources_by_year), sorted(sources_by_year)[1:], strict=False):
            if current_year != previous_year + 1:
                continue
            common_sources = sources_by_year[previous_year] & sources_by_year[current_year]
            if not common_sources:
                conflicts.append(
                    f"{company} {metric} {previous_year}-{current_year} has no single source filing covering both years"
                )

    return conflicts


def build_evidence_brief(question: str, retrieval_result: RetrievalResult) -> EvidenceBrief:
    rows = _filter_relevant_rows(question, extract_evidence(retrieval_result))
    return EvidenceBrief(
        rows=rows,
        calculations=_build_calculations(rows),
        coverage_gaps=_coverage_gaps(question, rows),
        conflicts=_evidence_conflicts(rows),
    )


def build_answer_plan(question: str, retrieval_result: RetrievalResult) -> AnswerPlan:
    brief = build_evidence_brief(question, retrieval_result)
    outline = []
    if brief.rows:
        outline.append("Use the structured evidence rows for numeric figures; do not copy unsupported numbers from prose.")
    if brief.calculations:
        outline.append("Use deterministic calculations for growth rates and margins before writing trend language.")
    if brief.coverage_gaps:
        outline.append("State coverage gaps clearly instead of filling missing years, companies, segments, or products.")
    if brief.conflicts:
        outline.append("Explain conflicting extracted values or filing recasts before comparing trends.")
    if not outline:
        outline.append("No structured numeric evidence was extracted; answer only from cited retrieved passages.")
    return AnswerPlan(evidence_brief=brief, interpretation_outline=outline)


def format_evidence_brief(brief: EvidenceBrief, *, max_rows: int = 80, max_calculations: int = 80) -> str:
    if not brief.rows:
        return "No structured numeric evidence was extracted from the retrieved passages."

    row_lines = [
        "| company | year | metric | value | unit | source filing | chunk | quote |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in brief.rows[:max_rows]:
        row_lines.append(
            "| "
            f"{row.company} | {row.filing_year} | {row.metric} | {row.value:g} | {row.unit} | {row.source_filing_year} filing | "
            f"{row.source_chunk_id} | {row.quote} |"
        )

    calculation_lines = []
    if brief.calculations:
        calculation_lines = [
            "",
            "Deterministic calculations:",
            "| label | value | unit | formula | source chunks |",
            "| --- | --- | --- | --- | --- |",
        ]
        for calculation in brief.calculations[:max_calculations]:
            calculation_lines.append(
                "| "
                f"{calculation.label} | {calculation.value:g} | {calculation.unit} | {calculation.formula} | "
                f"{', '.join(str(chunk_id) for chunk_id in calculation.source_chunk_ids)} |"
            )

    coverage_lines = []
    if brief.coverage_gaps:
        coverage_lines = ["", "Coverage gaps:"]
        coverage_lines.extend(f"- Missing {gap.dimension}: {gap.value}" for gap in brief.coverage_gaps)

    conflict_lines = []
    if brief.conflicts:
        conflict_lines = ["", "Evidence conflicts or recasts:"]
        conflict_lines.extend(f"- {conflict}" for conflict in brief.conflicts)

    return "\n".join([*row_lines, *calculation_lines, *coverage_lines, *conflict_lines])


def format_answer_plan(plan: AnswerPlan) -> str:
    outline_lines = ["Interpretation outline:"]
    outline_lines.extend(f"- {item}" for item in plan.interpretation_outline)
    return "\n".join([format_evidence_brief(plan.evidence_brief), "", *outline_lines])


def _claim_numbers(text: str) -> list[tuple[float, bool]]:
    matches = re.finditer(r"(?<![\w-])\$?\(?-?[0-9][0-9,]*(?:\.[0-9]+)?\)?\s*%?", text)
    numbers = []
    for match in matches:
        raw_value = match.group(0).strip()
        if not ("%" in raw_value or "$" in raw_value or "," in raw_value):
            continue
        parsed = _parse_number(raw_value)
        if parsed is None:
            continue
        numbers.append((parsed, "%" in raw_value))
    return numbers


def _allowed_numeric_values(brief: EvidenceBrief) -> tuple[set[float], set[float]]:
    money_values = {row.value for row in brief.rows if row.unit != "%"}
    percent_values = {row.value for row in brief.rows if row.unit == "%"}
    percent_values.update(calculation.value for calculation in brief.calculations if calculation.unit == "%")
    money_values.update(calculation.value for calculation in brief.calculations if calculation.unit != "%")

    scaled_money_values = set(money_values)
    for value in money_values:
        scaled_money_values.add(round(value))
        scaled_money_values.add(round(value / 1000, 1))
        scaled_money_values.add(round(value * 1000, 1))

    scaled_percent_values = set(percent_values)
    for value in percent_values:
        scaled_percent_values.add(round(value))

    return scaled_money_values, scaled_percent_values


def validate_numeric_claims(answer_text: str, brief: EvidenceBrief, *, tolerance: float = 0.6) -> None:
    """Fail if numeric claims are not present in extracted evidence or deterministic calculations."""

    if not brief.rows:
        return

    money_values, percent_values = _allowed_numeric_values(brief)

    unsupported_numbers = [
        number
        for number, is_percent in _claim_numbers(answer_text)
        if not any(abs(number - allowed) <= tolerance for allowed in (percent_values if is_percent else money_values))
    ]
    if unsupported_numbers:
        formatted = ", ".join(f"{number:g}" for number in unsupported_numbers)
        raise EvidenceValidationError(f"Numeric claims are not backed by structured evidence: {formatted}")
