from __future__ import annotations

from stopwordsiso import stopwords

from app.assistant.agent import GroundedAnswer, GroundedCitation
from app.retrieval import RetrievalResult


class GroundingValidationError(ValueError):
    """Raised when an assistant answer is not grounded in retrieved passages."""


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())


def _content_words(text: str) -> set[str]:
    stop_words = stopwords("en")
    return {
        word
        for word in _normalize(text).replace(".", " ").replace(",", " ").replace(";", " ").split()
        if len(word) > 2 and word not in stop_words
    }


def _excerpt_windows(text: str, window_size: int = 28) -> list[str]:
    words = text.split()
    return [" ".join(words[index : index + window_size]) for index in range(0, len(words), max(window_size // 2, 1))]


def _best_exact_excerpt(claim: str, passage_text: str) -> str | None:
    claim_words = _content_words(claim)
    windows = _excerpt_windows(passage_text)
    if not windows:
        return None
    if not claim_words:
        return windows[0]

    best_excerpt = None
    best_overlap = 0
    for excerpt in windows:
        overlap = len(claim_words & _content_words(excerpt))
        if overlap > best_overlap:
            best_overlap = overlap
            best_excerpt = excerpt

    return best_excerpt if best_overlap > 0 else None


def repair_grounded_answer(answer: GroundedAnswer, retrieval_result: RetrievalResult) -> GroundedAnswer:
    """Replace fuzzy model quotes with exact excerpts from cited passages when possible."""

    passages = {passage.chunk_id: passage for passage in retrieval_result.passages}
    repaired_citations = []

    for citation in answer.citations:
        passage = passages.get(citation.chunk_id)
        if passage is None:
            repaired_citations.append(citation)
            continue

        evidence_text = " ".join([passage.content, *passage.neighbor_chunks])
        if _normalize(citation.supporting_quote) in _normalize(evidence_text):
            repaired_citations.append(citation)
            continue

        exact_excerpt = _best_exact_excerpt(citation.claim, evidence_text)
        repaired_citations.append(
            GroundedCitation(
                chunk_id=citation.chunk_id,
                claim=citation.claim,
                supporting_quote=exact_excerpt or citation.supporting_quote,
            )
        )

    return GroundedAnswer(
        answer=answer.answer,
        citations=repaired_citations,
        not_enough_evidence=answer.not_enough_evidence,
    )


def validate_grounded_answer(answer: GroundedAnswer, retrieval_result: RetrievalResult) -> None:
    """Fail closed unless every citation maps to retrieved evidence."""

    passages = {passage.chunk_id: passage for passage in retrieval_result.passages}

    if answer.not_enough_evidence:
        if answer.citations:
            raise GroundingValidationError("Not-enough-evidence answers must not include citations.")
        return

    if not answer.citations:
        raise GroundingValidationError("Grounded answers must include at least one citation.")

    for citation in answer.citations:
        passage = passages.get(citation.chunk_id)
        if passage is None:
            raise GroundingValidationError(f"Citation chunk {citation.chunk_id} was not retrieved.")

        evidence_text = _normalize(" ".join([passage.content, *passage.neighbor_chunks]))
        quote = _normalize(citation.supporting_quote)
        if quote not in evidence_text:
            raise GroundingValidationError(f"Citation quote is not present in chunk {citation.chunk_id}.")
