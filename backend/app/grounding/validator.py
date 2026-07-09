from __future__ import annotations

from app.assistant.agent import GroundedAnswer
from app.retrieval import RetrievalResult


class GroundingValidationError(ValueError):
    """Raised when an assistant answer is not grounded in retrieved passages."""


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())


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
