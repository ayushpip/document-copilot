import json
from uuid import uuid4

from app.assistant import GroundedAnswer, GroundedCitation
from app.chat.streaming import citation_metadata_part, stream_text_deltas


def test_stream_text_deltas_recreates_message() -> None:
    assert "".join(stream_text_deltas("A grounded answer.")) == "A grounded answer."


def test_citation_metadata_part_contains_citations() -> None:
    chunk_id = uuid4()
    answer = GroundedAnswer(
        answer="Answer",
        citations=[
            GroundedCitation(
                chunk_id=chunk_id,
                claim="Claim",
                supporting_quote="Quote",
            )
        ],
    )

    payload = json.loads(citation_metadata_part(answer))

    assert payload["type"] == "citations"
    assert payload["citations"][0]["chunk_id"] == str(chunk_id)
