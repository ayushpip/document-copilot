import os

import pytest

from app.database.session import SessionLocal
from app.retrieval import RetrievalFilters, RetrievalSettings, retrieve_source_passages


pytestmark = pytest.mark.integration


def test_retrieval_returns_relevant_apple_revenue_mix_chunks() -> None:
    if os.getenv("RUN_INTEGRATION_TESTS") != "1":
        pytest.skip("Set RUN_INTEGRATION_TESTS=1 to run real retrieval integration tests.")

    with SessionLocal() as db:
        result = retrieve_source_passages(
            db,
            "Across Apple's 2021-2025 10-Ks, how did the revenue mix between iPhone, Services, Mac, iPad, and Wearables change?",
            filters=RetrievalFilters(company="AAPL"),
            retrieval_settings=RetrievalSettings(candidate_k=25, final_k=5, neighbor_window=1),
        )

    assert result.passages
    assert all(passage.company == "AAPL" for passage in result.passages)
    assert all(passage.filing_type == "10-K" for passage in result.passages)
    assert all(passage.content for passage in result.passages)
    assert all(passage.neighbor_chunks for passage in result.passages)
    assert any(
        term in passage.content.lower()
        for passage in result.passages
        for term in ["iphone", "services", "wearables", "net sales"]
    )
