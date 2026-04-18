import json

from app.runtime.events import completed_event, failed_event, meta_event, status_event
from app.runtime.run_trace import RunTraceRecorder


class _FakeSession:
    def __init__(self):
        self.added: list[object] = []
        self.batches: list[list[object]] = []
        self.commit_count = 0
        self.refresh_count = 0

    def add(self, obj):
        self.added.append(obj)

    def add_all(self, objects):
        self.batches.append(list(objects))

    def commit(self):
        self.commit_count += 1

    def refresh(self, obj):
        self.refresh_count += 1
        if getattr(obj, "id", None) is None:
            obj.id = 41


def test_run_trace_recorder_creates_run_and_buffers_events_in_sequence():
    db = _FakeSession()

    trace = RunTraceRecorder.create(
        db=db,
        conversation_id=7,
        user_id=3,
        request_message_id=11,
        mode="chat",
        model_id="codex:gpt-5.2",
        provider_family="openai",
        reasoning_profile="high",
        metadata={"tool_mode": "knowledge"},
    )

    meta_line = trace.emit(meta_event(conversation_id=7, message_id=11, model="codex:gpt-5.2", run_id=trace.run_id))
    trace.emit(status_event(["Reading notes"]))
    done_lines = trace.persist_completion(
        response_message_id=19,
        terminal_events=[completed_event(assistant_message_id=19, content="done", run_id=trace.run_id)],
    )

    assert trace.run.id == 41
    assert trace.run.status == "completed"
    assert trace.run.response_message_id == 19
    assert trace.run.completed_at is not None
    assert json.loads(trace.run.metadata_json or "{}") == {"tool_mode": "knowledge"}

    meta_payload = json.loads(meta_line or "{}")
    done_payload = json.loads(done_lines[0])
    assert meta_payload["type"] == "meta"
    assert meta_payload["run_id"] == 41
    assert done_payload["type"] == "done"
    assert done_payload["assistant_message_id"] == 19

    assert db.commit_count == 2
    assert len(db.batches) == 1
    persisted_events = db.batches[0]
    assert [event.sequence_no for event in persisted_events] == [1, 2, 3]
    assert [event.event_type for event in persisted_events] == ["meta", "status", "completed"]


def test_run_trace_recorder_persists_failure_event():
    db = _FakeSession()

    trace = RunTraceRecorder.create(
        db=db,
        conversation_id=5,
        user_id=None,
        request_message_id=9,
        mode="chat",
        model_id="claude:claude-opus-4-6",
        provider_family="anthropic",
        reasoning_profile="auto",
    )

    trace.emit(status_event(["Waiting for model"]))
    failure_line = trace.persist_failure(
        error_code="TimeoutError",
        error_message="upstream timeout",
        failure_event=failed_event("upstream timeout"),
    )

    failure_payload = json.loads(failure_line or "{}")
    assert failure_payload == {"type": "error", "message": "upstream timeout"}
    assert trace.run.status == "failed"
    assert trace.run.error_code == "TimeoutError"
    assert trace.run.error_message == "upstream timeout"
    assert trace.run.completed_at is not None

    assert db.commit_count == 2
    assert len(db.batches) == 1
    persisted_events = db.batches[0]
    assert [event.sequence_no for event in persisted_events] == [1, 2]
    assert [event.event_type for event in persisted_events] == ["status", "failed"]


def test_run_trace_recorder_records_raw_ndjson_payloads():
    db = _FakeSession()

    trace = RunTraceRecorder.create(
        db=db,
        conversation_id=None,
        user_id=8,
        request_message_id=None,
        mode="debate",
        model_id="debate:multi-model",
        provider_family="debate",
        reasoning_profile="auto",
        metadata={"action": "next"},
    )

    line = trace.emit_ndjson_line('{"type":"turn_done","turn_id":7}\n')
    done_lines = trace.persist_completion_payloads(
        response_message_id=None,
        terminal_payloads=[{"type": "done", "stage": "opening", "status": "running"}],
    )

    assert json.loads(line) == {"type": "turn_done", "turn_id": 7}
    assert json.loads(done_lines[0]) == {"type": "done", "stage": "opening", "status": "running"}

    persisted_events = db.batches[0]
    assert [event.sequence_no for event in persisted_events] == [1, 2]
    assert [event.event_type for event in persisted_events] == ["turn_done", "done"]


def test_run_trace_recorder_persists_completion_state_without_encoding_lines():
    db = _FakeSession()

    trace = RunTraceRecorder.create(
        db=db,
        conversation_id=3,
        user_id=4,
        request_message_id=8,
        mode="chat",
        model_id="codex:gpt-5.4",
        provider_family="openai",
        reasoning_profile="medium",
    )

    trace.emit(status_event(["Waiting for model"]))
    trace.persist_completion_state(
        response_message_id=12,
        terminal_events=[completed_event(assistant_message_id=12, content="done", run_id=trace.run_id)],
    )

    assert trace.run.status == "completed"
    assert trace.run.response_message_id == 12
    assert db.commit_count == 2
    persisted_events = db.batches[0]
    assert [event.sequence_no for event in persisted_events] == [1, 2]
    assert [event.event_type for event in persisted_events] == ["status", "completed"]
