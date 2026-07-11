from uuid import uuid4

import pytest

from app.assistant.evidence import (
    EvidenceValidationError,
    build_answer_plan,
    build_evidence_brief,
    extract_evidence,
    format_answer_plan,
    format_evidence_brief,
    validate_numeric_claims,
)
from app.retrieval import RetrievedPassage, RetrievalFilters, RetrievalResult, RetrievalSettings


def make_result(content: str) -> RetrievalResult:
    return RetrievalResult(
        query="Compare Microsoft cloud revenue growth and operating margins from 2023-2025.",
        passages=[
            RetrievedPassage(
                chunk_id=uuid4(),
                source_document_id=uuid4(),
                company="MSFT",
                filing_year=2025,
                filing_type="10-K",
                filing_url=None,
                chunk_index=84,
                content=content,
                metadata={},
                rank=1,
                fused_score=0.1,
            )
        ],
        settings=RetrievalSettings(),
        filters=RetrievalFilters(company="MSFT"),
    )


def test_extract_evidence_preserves_grouped_segment_context() -> None:
    result = make_result(
        """
Segment revenue, cost of revenue, operating expenses, and operating income were as follows during the periods presented:

|  | 2025 | 2024 | 2023 |
| --- | --- | --- | --- |
| Intelligent Cloud |  |  |  |
| Revenue | 106,265 | 87,464 | 72,944 |
| Operating Income | 44,589 | 37,813 | 28,411 |
"""
    )

    rows = extract_evidence(result)

    assert {row.metric for row in rows} == {"Intelligent Cloud Revenue", "Intelligent Cloud Operating Income"}
    assert next(row for row in rows if row.metric == "Intelligent Cloud Revenue" and row.filing_year == 2025).value == 106_265
    assert (
        next(row for row in rows if row.metric == "Intelligent Cloud Operating Income" and row.filing_year == 2025).value
        == 44_589
    )


def test_extract_evidence_handles_flattened_docling_table_assignments() -> None:
    result = make_result(
        """
(In millions, except percentages), 1 = 2024. (In millions, except percentages), 2 = 2023.
Revenue, 1 = . Revenue, 2 = .
Intelligent Cloud, 1 = 105,362. Intelligent Cloud, 2 = 87,907.
Operating Income, 1 = . Operating Income, 2 = .
Intelligent Cloud, 1 = 49,584. Intelligent Cloud, 2 = 37,884.
"""
    )

    rows = extract_evidence(result)

    assert next(row for row in rows if row.metric == "Intelligent Cloud Revenue" and row.filing_year == 2024).value == 105_362
    assert (
        next(row for row in rows if row.metric == "Intelligent Cloud Operating Income" and row.filing_year == 2024).value
        == 49_584
    )


def test_build_evidence_brief_calculates_growth_and_margin() -> None:
    result = make_result(
        """
|  | 2025 | 2024 |
| --- | --- | --- |
| Intelligent Cloud |  |  |
| Revenue | 106,265 | 87,464 |
| Operating Income | 44,589 | 37,813 |
"""
    )

    brief = build_evidence_brief("Compare Microsoft cloud revenue growth and operating margins from 2024-2025.", result)
    labels = {calculation.label: calculation.value for calculation in brief.calculations}

    assert labels["MSFT Intelligent Cloud Revenue growth 2024-2025"] == 21.5
    assert labels["MSFT intelligent cloud operating margin 2025"] == 42.0
    assert not brief.coverage_gaps


def test_build_evidence_brief_flags_missing_requested_years() -> None:
    result = make_result(
        """
|  | 2025 | 2024 |
| --- | --- | --- |
| Intelligent Cloud |  |  |
| Revenue | 106,265 | 87,464 |
"""
    )

    brief = build_evidence_brief("Compare Microsoft cloud revenue growth from 2023-2025.", result)

    assert [gap.value for gap in brief.coverage_gaps] == ["2023"]


def test_build_answer_plan_flags_requested_company_and_product_gaps() -> None:
    result = make_result(
        """
|  | 2025 |
| --- | --- |
| Intelligent Cloud |  |
| Revenue | 106,265 |
"""
    )

    plan = build_answer_plan("Compare Apple iPhone revenue and Microsoft cloud revenue in 2025.", result)
    gaps = {(gap.dimension, gap.value) for gap in plan.evidence_brief.coverage_gaps}

    assert ("company", "AAPL") in gaps
    assert ("segment_or_product", "iphone") in gaps
    assert any(item.startswith("State coverage gaps clearly") for item in plan.interpretation_outline)


def test_build_answer_plan_flags_conflicting_values() -> None:
    result = make_result(
        """
|  | 2024 |
| --- | --- |
| Intelligent Cloud |  |
| Revenue | 105,362 |

(In millions), 1 = 2024.
Intelligent Cloud, 1 = .
Revenue, 1 = 87,464.
"""
    )

    plan = build_answer_plan("Compare Microsoft Intelligent Cloud revenue in 2024.", result)

    assert plan.evidence_brief.conflicts
    assert any("conflicting extracted values" in item for item in plan.interpretation_outline)


def test_build_evidence_brief_skips_calculations_from_conflicting_values() -> None:
    result = make_result(
        """
|  | 2025 | 2024 | 2023 |
| --- | --- | --- | --- |
| Intelligent Cloud |  |  |
| Revenue | 106,265 | 105,362 | 72,944 |

(In millions), 1 = 2024.
Intelligent Cloud, 1 = .
Revenue, 1 = 87,464.
"""
    )

    brief = build_evidence_brief("Compare Microsoft Intelligent Cloud revenue growth from 2024-2025.", result)

    assert brief.conflicts
    assert not any("Intelligent Cloud Revenue growth" in calculation.label for calculation in brief.calculations)


def test_build_evidence_brief_does_not_calculate_across_different_source_filings() -> None:
    old_basis_chunk_id = uuid4()
    recast_basis_chunk_id = uuid4()
    result = RetrievalResult(
        query="Compare Microsoft Intelligent Cloud revenue growth from 2022-2025.",
        passages=[
            RetrievedPassage(
                chunk_id=old_basis_chunk_id,
                source_document_id=uuid4(),
                company="MSFT",
                filing_year=2024,
                filing_type="10-K",
                filing_url=None,
                chunk_index=22,
                content=(
                    "|  | 2023 | 2022 |\n"
                    "| --- | --- | --- |\n"
                    "| Intelligent Cloud |  |  |\n"
                    "| Revenue | 87,907 | 74,965 |\n"
                    "| Operating Income | 37,884 | 33,203 |"
                ),
                metadata={},
                rank=1,
                fused_score=0.1,
            ),
            RetrievedPassage(
                chunk_id=recast_basis_chunk_id,
                source_document_id=uuid4(),
                company="MSFT",
                filing_year=2025,
                filing_type="10-K",
                filing_url=None,
                chunk_index=21,
                content=(
                    "|  | 2025 | 2024 |\n"
                    "| --- | --- | --- |\n"
                    "| Intelligent Cloud |  |  |\n"
                    "| Revenue | 106,265 | 87,464 |\n"
                    "| Operating Income | 44,589 | 37,813 |"
                ),
                metadata={},
                rank=2,
                fused_score=0.1,
            ),
        ],
        settings=RetrievalSettings(),
        filters=RetrievalFilters(company="MSFT"),
    )

    brief = build_evidence_brief("Compare Microsoft Intelligent Cloud revenue growth from 2022-2025.", result)
    labels = {calculation.label for calculation in brief.calculations}

    assert "MSFT Intelligent Cloud Revenue growth 2022-2023" in labels
    assert "MSFT Intelligent Cloud Revenue growth 2024-2025" in labels
    assert "MSFT Intelligent Cloud Revenue growth 2023-2024" not in labels
    assert any("no single source filing" in conflict for conflict in brief.conflicts)


def test_build_evidence_brief_only_keeps_totals_when_question_needs_mix_context() -> None:
    result = make_result(
        """
|  | 2025 |
| --- | --- |
| iPhone | 209,586 |
| Total net sales | 416,161 |
"""
    )

    trend_brief = build_evidence_brief("Compare iPhone revenue trend in 2025.", result)
    mix_brief = build_evidence_brief("Compare iPhone revenue mix in 2025.", result)

    assert {row.metric for row in trend_brief.rows} == {"iPhone"}
    assert {row.metric for row in mix_brief.rows} == {"iPhone", "Total net sales"}


def test_format_evidence_brief_includes_source_chunks_and_calculations() -> None:
    result = make_result(
        """
|  | 2025 | 2024 |
| --- | --- | --- |
| Intelligent Cloud |  |  |
| Revenue | 106,265 | 87,464 |
"""
    )
    brief = build_evidence_brief("Compare Microsoft cloud revenue growth from 2024-2025.", result)

    formatted = format_evidence_brief(brief)

    assert "Intelligent Cloud Revenue" in formatted
    assert "Deterministic calculations" in formatted
    assert str(brief.rows[0].source_chunk_id) in formatted


def test_format_answer_plan_includes_interpretation_outline() -> None:
    result = make_result(
        """
|  | 2025 | 2024 |
| --- | --- | --- |
| Intelligent Cloud |  |  |
| Revenue | 106,265 | 87,464 |
"""
    )
    plan = build_answer_plan("Compare Microsoft cloud revenue growth from 2024-2025.", result)

    formatted = format_answer_plan(plan)

    assert "Interpretation outline" in formatted
    assert "Use deterministic calculations" in formatted


def test_validate_numeric_claims_accepts_evidence_and_calculated_values() -> None:
    result = make_result(
        """
|  | 2025 | 2024 |
| --- | --- | --- |
| Intelligent Cloud |  |  |
| Revenue | 106,265 | 87,464 |
| Operating Income | 44,589 | 37,813 |
"""
    )
    brief = build_evidence_brief("Compare Microsoft cloud revenue growth and operating margins from 2024-2025.", result)

    validate_numeric_claims(
        "Revenue was $106,265 million and operating margin was approximately 42.0%.",
        brief,
    )


def test_validate_numeric_claims_accepts_scaled_absolute_changes() -> None:
    result = make_result(
        """
|  | 2025 | 2024 |
| --- | --- | --- |
| Intelligent Cloud |  |  |
| Revenue | 106,265 | 87,464 |
| Operating Income | 44,589 | 37,813 |
"""
    )
    brief = build_evidence_brief("Compare Microsoft cloud revenue growth and operating margins from 2024-2025.", result)

    validate_numeric_claims(
        "Revenue increased by about $18.8 billion and operating income increased by about $6.8 billion.",
        brief,
    )


def test_validate_numeric_claims_rejects_unsupported_values() -> None:
    result = make_result(
        """
|  | 2025 | 2024 |
| --- | --- | --- |
| Intelligent Cloud |  |  |
| Revenue | 106,265 | 87,464 |
"""
    )
    brief = build_evidence_brief("Compare Microsoft cloud revenue growth from 2024-2025.", result)

    with pytest.raises(EvidenceValidationError):
        validate_numeric_claims("Revenue was $123,456 million.", brief)
