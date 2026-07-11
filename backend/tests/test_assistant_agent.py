from uuid import uuid4

from app.assistant.agent import build_agent_prompt, calculate_growth_percentage, calculate_margin_percentage
from app.retrieval import RetrievedPassage, RetrievalFilters, RetrievalResult, RetrievalSettings


def test_build_agent_prompt_includes_question_and_chunk_ids() -> None:
    chunk_id = uuid4()
    result = RetrievalResult(
        query="Apple revenue",
        passages=[
            RetrievedPassage(
                chunk_id=chunk_id,
                source_document_id=uuid4(),
                company="AAPL",
                filing_year=2025,
                filing_type="10-K",
                filing_url=None,
                chunk_index=18,
                content="Services net sales increased.",
                metadata={},
                rank=1,
                fused_score=0.1,
            )
        ],
        settings=RetrievalSettings(),
        filters=RetrievalFilters(company="AAPL"),
    )

    prompt = build_agent_prompt("What changed?", result)

    assert "What changed?" in prompt
    assert str(chunk_id) in prompt
    assert "Services net sales increased." in prompt


def test_build_agent_prompt_includes_analysis_guardrails() -> None:
    result = RetrievalResult(
        query="Microsoft cloud margins",
        passages=[],
        settings=RetrievalSettings(),
        filters=RetrievalFilters(company="MSFT"),
    )

    prompt = build_agent_prompt("Compare revenue growth and operating margins.", result)

    assert "operating margin as operating income divided by revenue" in prompt
    assert "do not use operating income growth as a substitute" in prompt
    assert "If the retrieved evidence is incomplete" in prompt


def test_calculate_growth_percentage() -> None:
    result = calculate_growth_percentage(current_value=106_265, previous_value=87_464)

    assert result["growth_percentage"] == 21.5


def test_calculate_margin_percentage() -> None:
    result = calculate_margin_percentage(numerator=44_589, denominator=106_265)

    assert result["margin_percentage"] == 42.0
