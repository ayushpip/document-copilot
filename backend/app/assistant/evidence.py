from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable
from uuid import UUID

from pydantic import BaseModel, Field

from app.retrieval import RetrievedPassage, RetrievalResult


YEAR_PATTERN = re.compile(r"\b(20\d{2})\b")
NUMBER_PATTERN = re.compile(r"\(?-?\$?\s*([0-9][0-9,]*(?:\.[0-9]+)?)\s*\)?")
TABLE_SEPARATOR_PATTERN = re.compile(r"^\|\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?$")
KNOWN_FINANCIAL_METRICS = {
    "revenue",
    "operating income",
    "net sales",
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
}


class EvidenceRow(BaseModel):
    """One structured fact extracted from a retrieved filing passage."""

    company: str
    filing_year: int
    filing_type: str
    metric: str
    value: float
    unit: str = "USD millions"
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
    if value.strip().startswith("(") and value.strip().endswith(")"):
        return -number
    return number


def _normalize_metric(metric: str, parent_metric: str | None = None) -> str:
    clean_metric = " ".join(metric.replace("**", "").split())
    if parent_metric:
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
                        source_chunk_id=passage.chunk_id,
                        source_chunk_index=passage.chunk_index,
                        quote=row_line.strip(),
                    )
                )

    return rows


def extract_evidence(retrieval_result: RetrievalResult) -> list[EvidenceRow]:
    """Extract structured numeric evidence from retrieved markdown tables."""

    rows = []
    seen = set()

    for passage in retrieval_result.passages:
        for row in _table_rows_from_passage(passage):
            key = (row.company, row.filing_year, row.metric.lower(), row.value, row.source_chunk_id)
            if key in seen:
                continue
            seen.add(key)
            rows.append(row)

    return rows


def calculate_growth_percentage(current: EvidenceRow, previous: EvidenceRow) -> CalculationRow | None:
    if previous.value == 0:
        return None

    growth = ((current.value - previous.value) / previous.value) * 100
    return CalculationRow(
        label=f"{current.company} {current.metric} growth {previous.filing_year}-{current.filing_year}",
        value=round(growth, 1),
        unit="%",
        formula=f"(({current.value} - {previous.value}) / {previous.value}) * 100",
        source_chunk_ids=[previous.source_chunk_id, current.source_chunk_id],
    )


def calculate_margin_percentage(numerator: EvidenceRow, denominator: EvidenceRow) -> CalculationRow | None:
    if denominator.value == 0:
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
    rows_by_company_metric: dict[tuple[str, str], list[EvidenceRow]] = defaultdict(list)
    rows_by_company_year: dict[tuple[str, int], list[EvidenceRow]] = defaultdict(list)

    for row in rows:
        rows_by_company_metric[(row.company, _canonical_metric(row.metric))].append(row)
        rows_by_company_year[(row.company, row.filing_year)].append(row)

    for metric_rows in rows_by_company_metric.values():
        sorted_rows = sorted(metric_rows, key=lambda row: row.filing_year)
        for previous, current in zip(sorted_rows, sorted_rows[1:], strict=False):
            calculation = calculate_growth_percentage(current, previous)
            if calculation:
                calculations.append(calculation)

    for company_year_rows in rows_by_company_year.values():
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
                if calculation:
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


def _requested_companies(question: str) -> set[str]:
    lower_question = question.lower()
    return {ticker for name, ticker in KNOWN_COMPANIES.items() if re.search(rf"\b{re.escape(name)}\b", lower_question)}


def _requested_terms(question: str) -> set[str]:
    lower_question = question.lower()
    return {term for term in KNOWN_SEGMENTS_AND_PRODUCTS if re.search(rf"\b{re.escape(term)}\b", lower_question)}


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
    gaps.extend(
        CoverageGap(dimension="company", value=company)
        for company in sorted(_requested_companies(question))
        if company not in available_companies
    )

    available_metrics = " ".join(row.metric.lower() for row in rows)
    gaps.extend(
        CoverageGap(dimension="segment_or_product", value=term)
        for term in sorted(_requested_terms(question))
        if term not in available_metrics
    )
    return gaps


def build_evidence_brief(question: str, retrieval_result: RetrievalResult) -> EvidenceBrief:
    rows = extract_evidence(retrieval_result)
    return EvidenceBrief(
        rows=rows,
        calculations=_build_calculations(rows),
        coverage_gaps=_coverage_gaps(question, rows),
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
    if not outline:
        outline.append("No structured numeric evidence was extracted; answer only from cited retrieved passages.")
    return AnswerPlan(evidence_brief=brief, interpretation_outline=outline)


def format_evidence_brief(brief: EvidenceBrief, *, max_rows: int = 80, max_calculations: int = 80) -> str:
    if not brief.rows:
        return "No structured numeric evidence was extracted from the retrieved passages."

    row_lines = [
        "| company | year | metric | value | unit | chunk | quote |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in brief.rows[:max_rows]:
        row_lines.append(
            "| "
            f"{row.company} | {row.filing_year} | {row.metric} | {row.value:g} | {row.unit} | "
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

    return "\n".join([*row_lines, *calculation_lines, *coverage_lines])


def format_answer_plan(plan: AnswerPlan) -> str:
    outline_lines = ["Interpretation outline:"]
    outline_lines.extend(f"- {item}" for item in plan.interpretation_outline)
    return "\n".join([format_evidence_brief(plan.evidence_brief), "", *outline_lines])


def _claim_numbers(text: str) -> list[float]:
    matches = re.finditer(r"(?<![\w-])\$?\(?-?[0-9][0-9,]*(?:\.[0-9]+)?\)?\s*%?", text)
    numbers = []
    for match in matches:
        raw_value = match.group(0).strip()
        if not ("%" in raw_value or "$" in raw_value or "," in raw_value):
            continue
        parsed = _parse_number(raw_value)
        if parsed is None:
            continue
        numbers.append(parsed)
    return numbers


def validate_numeric_claims(answer_text: str, brief: EvidenceBrief, *, tolerance: float = 0.6) -> None:
    """Fail if numeric claims are not present in extracted evidence or deterministic calculations."""

    if not brief.rows:
        return

    allowed_values = {row.value for row in brief.rows}
    allowed_values.update(calculation.value for calculation in brief.calculations)
    allowed_values.update(round(value) for value in list(allowed_values))

    unsupported_numbers = [
        number
        for number in _claim_numbers(answer_text)
        if not any(abs(number - allowed) <= tolerance for allowed in allowed_values)
    ]
    if unsupported_numbers:
        formatted = ", ".join(f"{number:g}" for number in unsupported_numbers)
        raise EvidenceValidationError(f"Numeric claims are not backed by structured evidence: {formatted}")
