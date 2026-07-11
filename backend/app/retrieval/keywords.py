from __future__ import annotations

import json
import re

from openai import OpenAI
from stopwordsiso import stopwords

from app.config import settings
from app.retrieval.schemas import RetrievalQueryPlan

WORD_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9&.-]*|\d{4}|[0-9]+(?:\.[0-9]+)?%?")
COMPANY_ALIASES = {
    "AAPL": {"aapl", "apple"},
    "AMZN": {"amzn", "amazon", "aws"},
    "GOOGL": {"googl", "alphabet", "google", "youtube"},
    "MSFT": {"msft", "microsoft", "azure"},
    "NVDA": {"nvda", "nvidia"},
}
FILING_TYPES = {"10-K", "10-Q"}


def _chat_model_name() -> str:
    return settings.openai_chat_model.removeprefix("openai:")


def extract_keywords(query: str, max_keywords: int = 16) -> list[str]:
    """Extract lexical keywords with a library stopword list."""

    stop_words = stopwords("en")
    keywords: list[str] = []
    seen = set()
    for match in WORD_PATTERN.findall(query):
        token = match.strip(".").strip()
        normalized = token.lower()
        if not token or normalized in stop_words:
            continue
        if len(normalized) <= 1 and not normalized.isdigit():
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        keywords.append(token.upper() if token.isupper() else token)
        if len(keywords) >= max_keywords:
            break
    return keywords


def _filter_terms_for_full_text(keywords: list[str], companies: list[str], filing_type: str | None) -> list[str]:
    company_aliases = {
        alias
        for ticker in companies
        for alias in COMPANY_ALIASES.get(ticker.upper(), {ticker.lower()})
    }
    filing_tokens = set()
    if filing_type:
        filing_tokens.add(filing_type.lower())
        filing_tokens.update(filing_type.lower().split("-"))

    filtered = []
    for keyword in keywords:
        normalized = keyword.lower()
        if re.fullmatch(r"20\d{2}", normalized):
            continue
        if normalized in company_aliases or normalized in filing_tokens:
            continue
        filtered.append(keyword)
    return filtered


def full_text_query_from_keywords(keywords: list[str], companies: list[str], filing_type: str | None) -> str:
    filtered = _filter_terms_for_full_text(keywords, companies, filing_type)
    return " ".join(filtered or keywords)


def infer_companies(query: str) -> list[str]:
    normalized_query = query.lower()
    companies = [
        ticker
        for ticker, aliases in COMPANY_ALIASES.items()
        if any(re.search(rf"\b{re.escape(alias)}\b", normalized_query) for alias in aliases)
    ]
    return companies


def infer_years(query: str) -> list[int]:
    years = sorted({int(year) for year in re.findall(r"\b20(?:2[0-9]|1[0-9])\b", query)})
    if len(years) == 2 and re.search(r"\b(?:to|through|-|–|—)\b", query):
        start, end = years
        if start < end and end - start <= 10:
            return list(range(start, end + 1))
    return years


def infer_filing_type(query: str) -> str | None:
    normalized_query = query.upper()
    for filing_type in FILING_TYPES:
        if filing_type in normalized_query:
            return filing_type
    return None


def fallback_query_plan(query: str) -> RetrievalQueryPlan:
    keywords = extract_keywords(query)
    companies = infer_companies(query)
    filing_type = infer_filing_type(query)
    keyword_query = full_text_query_from_keywords(keywords, companies, filing_type) if keywords else query.strip()
    return RetrievalQueryPlan(
        original_query=query.strip(),
        semantic_query=query.strip(),
        full_text_query=keyword_query,
        keywords=keywords,
        companies=companies,
        filing_years=infer_years(query),
        filing_type=filing_type,
    )


def _planner_prompt(query: str) -> str:
    return (
        "Plan retrieval for a SEC filing question. Return compact JSON with these keys only: "
        "semantic_query, full_text_query, keywords, companies, filing_years, filing_type. "
        "Use companies as tickers from AAPL, AMZN, GOOGL, MSFT, NVDA when clear. "
        "Use full_text_query as short keyword-heavy search terms, not a sentence. "
        "Do not answer the question.\n\n"
        f"Question: {query.strip()}"
    )


def plan_retrieval_query(query: str) -> RetrievalQueryPlan:
    """Use an LLM query planner, with deterministic keyword fallback."""

    fallback = fallback_query_plan(query)
    try:
        client = OpenAI(api_key=settings.openai_api_key)
        response = client.chat.completions.create(
            model=_chat_model_name(),
            messages=[
                {
                    "role": "system",
                    "content": "You are a retrieval query planner. Return only valid JSON.",
                },
                {"role": "user", "content": _planner_prompt(query)},
            ],
            response_format={"type": "json_object"},
            temperature=0,
        )
        content = response.choices[0].message.content or "{}"
        payload = json.loads(content)
        companies = [str(company).upper() for company in payload.get("companies") or fallback.companies]
        filing_type = str(payload["filing_type"]).upper() if payload.get("filing_type") else fallback.filing_type
        keywords = list(payload.get("keywords") or fallback.keywords)
        planned_full_text_query = str(payload.get("full_text_query") or fallback.full_text_query)
        full_text_keywords = extract_keywords(planned_full_text_query) or keywords
        return RetrievalQueryPlan(
            original_query=query.strip(),
            semantic_query=str(payload.get("semantic_query") or fallback.semantic_query),
            full_text_query=full_text_query_from_keywords(full_text_keywords, companies, filing_type),
            keywords=keywords,
            companies=companies,
            filing_years=[int(year) for year in payload.get("filing_years") or fallback.filing_years],
            filing_type=filing_type,
        )
    except Exception:
        return fallback
