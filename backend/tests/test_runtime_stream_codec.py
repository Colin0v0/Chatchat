import json

from app.runtime.events import completed_event, meta_event, output_text_delta_event, reasoning_delta_event
from app.runtime.stream_codec import encode_ndjson_event


def test_encode_meta_event_to_legacy_ndjson():
    encoded = encode_ndjson_event(meta_event(conversation_id=1, message_id=2, model="codex:gpt-5.4", run_id=3))

    assert encoded is not None
    payload = json.loads(encoded)
    assert payload["type"] == "meta"
    assert payload["conversation_id"] == 1
    assert payload["run_id"] == 3


def test_encode_delta_events_to_legacy_types():
    token_payload = json.loads(encode_ndjson_event(output_text_delta_event("hello")) or "{}")
    reasoning_payload = json.loads(encode_ndjson_event(reasoning_delta_event("thinking")) or "{}")

    assert token_payload == {"type": "token", "content": "hello"}
    assert reasoning_payload == {"type": "reasoning", "content": "thinking"}


def test_encode_completed_event_to_done():
    encoded = encode_ndjson_event(completed_event(assistant_message_id=11, content="done"))

    assert encoded is not None
    payload = json.loads(encoded)
    assert payload["type"] == "done"
    assert payload["assistant_message_id"] == 11
