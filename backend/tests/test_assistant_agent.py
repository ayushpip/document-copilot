from uuid import uuid4

from app.assistant.agent import build_agent_prompt
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
