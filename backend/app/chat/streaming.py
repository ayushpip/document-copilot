from __future__ import annotations

import json
from collections.abc import Iterable

from app.assistant.agent import GroundedAnswer


def stream_text_deltas(text: str) -> Iterable[str]:
    """Yield stable text deltas for the existing plain-text chat client."""

    words = text.split(" ")
    for index, word in enumerate(words):
        yield word if index == 0 else f" {word}"


def citation_metadata_part(answer: GroundedAnswer) -> str:
    """Return an AI SDK-style metadata part for clients that opt into parsing it."""

    payload = {
        "type": "citations",
        "citations": [
            {
                "chunk_id": str(citation.chunk_id),
                "claim": citation.claim,
                "supporting_quote": citation.supporting_quote,
            }
            for citation in answer.citations
        ],
    }
    return json.dumps(payload)
