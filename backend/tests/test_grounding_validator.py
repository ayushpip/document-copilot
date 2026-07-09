from uuid import uuid4

import pytest

from app.assistant import GroundedAnswer, GroundedCitation
from app.grounding import GroundingValidationError, validate_grounded_answer
from app.retrieval import RetrievedPassage, RetrievalFilters, RetrievalResult, RetrievalSettings


def make_result(chunk_id=None) -> RetrievalResult:
    chunk_id = chunk_id or uuid4()
    return RetrievalResult(
        query="Apple revenue",
        passages=[
            RetrievedPassage(
                chunk_id=chunk_id,
                source_document_id=uuid4(),
                company="AAPL",
                filing_year=2025,
                filing_type="10-K",
                filing_url="https://example.com",
                chunk_index=18,
                content="Services and iPhone net sales increased during 2025.",
                metadata={},
                rank=1,
                fused_score=0.1,
                neighbor_chunks=["Mac net sales also increased."],
            )
        ],
        settings=RetrievalSettings(),
        filters=RetrievalFilters(company="AAPL"),
    )


def test_validate_grounded_answer_accepts_retrieved_quote() -> None:
    result = make_result()
    answer = GroundedAnswer(
        answer="Apple disclosed Services and iPhone sales increased.",
        citations=[
            GroundedCitation(
                chunk_id=result.passages[0].chunk_id,
                claim="Services and iPhone sales increased.",
                supporting_quote="Services and iPhone net sales increased",
            )
        ],
    )

    validate_grounded_answer(answer, result)


def test_validate_grounded_answer_accepts_neighbor_quote() -> None:
    result = make_result()
    answer = GroundedAnswer(
        answer="Apple disclosed Mac sales increased.",
        citations=[
            GroundedCitation(
                chunk_id=result.passages[0].chunk_id,
                claim="Mac sales increased.",
                supporting_quote="Mac net sales also increased.",
            )
        ],
    )

    validate_grounded_answer(answer, result)


def test_validate_grounded_answer_rejects_unknown_chunk_id() -> None:
    result = make_result()
    answer = GroundedAnswer(
        answer="Unsupported.",
        citations=[
            GroundedCitation(
                chunk_id=uuid4(),
                claim="Unsupported.",
                supporting_quote="Services and iPhone net sales increased",
            )
        ],
    )

    with pytest.raises(GroundingValidationError):
        validate_grounded_answer(answer, result)


def test_validate_grounded_answer_rejects_quote_not_in_evidence() -> None:
    result = make_result()
    answer = GroundedAnswer(
        answer="Unsupported.",
        citations=[
            GroundedCitation(
                chunk_id=result.passages[0].chunk_id,
                claim="Unsupported.",
                supporting_quote="Generative AI improved margins.",
            )
        ],
    )

    with pytest.raises(GroundingValidationError):
        validate_grounded_answer(answer, result)


def test_validate_not_enough_evidence_requires_no_citations() -> None:
    result = make_result()
    answer = GroundedAnswer(answer="There is not enough evidence in the retrieved filings.", not_enough_evidence=True)

    validate_grounded_answer(answer, result)
