from app.retrieval import keywords


def test_extract_keywords_uses_stopword_library() -> None:
    extracted = keywords.extract_keywords("What did Apple say about the revenue mix between iPhone and Services?")

    assert "Apple" in extracted
    assert "revenue" in extracted
    assert "iPhone" in extracted
    assert "the" not in [item.lower() for item in extracted]
    assert "and" not in [item.lower() for item in extracted]


def test_fallback_query_plan_infers_company_years_and_filing_type() -> None:
    plan = keywords.fallback_query_plan("Compare Apple 10-K filings from 2021-2023 for Services revenue.")

    assert plan.companies == ["AAPL"]
    assert plan.filing_years == [2021, 2022, 2023]
    assert plan.filing_type == "10-K"
    assert "Services" in plan.full_text_query
    assert "Apple" not in plan.full_text_query
    assert "10-K" not in plan.full_text_query
    assert "2021" not in plan.full_text_query
    assert "2023" not in plan.full_text_query


def test_plan_retrieval_query_falls_back_when_llm_fails(monkeypatch) -> None:
    class BrokenOpenAI:
        def __init__(self, api_key):
            self.api_key = api_key

        @property
        def chat(self):
            raise RuntimeError("planner unavailable")

    monkeypatch.setattr(keywords, "OpenAI", BrokenOpenAI)

    plan = keywords.plan_retrieval_query("Amazon AWS operating income")

    assert plan.semantic_query == "Amazon AWS operating income"
    assert plan.companies == ["AMZN"]
    assert "AWS" in plan.keywords
