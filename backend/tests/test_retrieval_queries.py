from sqlalchemy.dialects import postgresql

from app.retrieval.queries import full_text_search_statement, semantic_search_statement
from app.retrieval.schemas import RetrievalFilters


def compile_statement(statement) -> str:
    return str(statement.compile(dialect=postgresql.dialect()))


def test_semantic_search_statement_uses_pgvector_and_filters() -> None:
    statement = semantic_search_statement(
        query_embedding=[0.1, 0.2, 0.3],
        limit=5,
        filters=RetrievalFilters(company="aapl", filing_year=2025, filing_type="10-k"),
    )

    compiled = compile_statement(statement)

    assert "document_chunks.embedding <=> %(query_embedding)s" in compiled
    assert "source_documents.company = %(company_1)s" in compiled
    assert "source_documents.filing_year = %(filing_year_1)s" in compiled
    assert "source_documents.filing_type = %(filing_type_1)s" in compiled
    assert "LIMIT %(param_2)s" in compiled


def test_full_text_search_statement_uses_search_vector_and_filters() -> None:
    statement = full_text_search_statement(
        query="Apple revenue mix",
        limit=5,
        filters=RetrievalFilters(company="AAPL"),
    )

    compiled = compile_statement(statement)

    assert "websearch_to_tsquery" in compiled
    assert "document_chunks.search_vector @@ websearch_to_tsquery" in compiled
    assert "ts_rank_cd" in compiled
    assert "ORDER BY ts_rank_cd" in compiled
    assert "source_documents.company = %(company_1)s" in compiled
