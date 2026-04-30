from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from ..storage.models import Run, RunEvent
from .events import CanonicalEvent
from .stream_codec import encode_ndjson_event


class RunTraceRecorder:
    def __init__(self, *, db: Session, run: Run):
        self._db = db
        self.run = run
        self._buffered_events: list[RunEvent] = []

    @classmethod
    def create(
        cls,
        *,
        db: Session,
        conversation_id: int | None,
        user_id: int | None,
        request_message_id: int | None,
        mode: str,
        model_id: str,
        provider_family: str,
        reasoning_profile: str,
        metadata: dict[str, Any] | None = None,
    ) -> "RunTraceRecorder":
        run = Run(
            conversation_id=conversation_id,
            user_id=user_id,
            request_message_id=request_message_id,
            mode=mode,
            model_id=model_id,
            provider_family=provider_family,
            reasoning_profile=reasoning_profile,
            status="running",
            metadata_json=json.dumps(metadata or {}, ensure_ascii=False),
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        return cls(db=db, run=run)

    @property
    def run_id(self) -> int:
        if self.run.id is None:  # pragma: no cover
            raise RuntimeError("Run id is unavailable before persistence.")
        return int(self.run.id)

    def emit(self, event: CanonicalEvent) -> str | None:
        self.record(event)
        return encode_ndjson_event(event)

    def record(self, event: CanonicalEvent) -> None:
        self.record_payload(event_type=event.kind, payload=event.payload)

    def emit_payload(self, *, event_type: str, payload: dict[str, Any]) -> str:
        self.record_payload(event_type=event_type, payload=payload)
        return json.dumps(payload, ensure_ascii=False) + "\n"

    def emit_ndjson_line(self, line: str) -> str:
        normalized = line if line.endswith("\n") else f"{line}\n"
        payload = json.loads(normalized)
        event_type = str(payload.get("type", "event")).strip() or "event"
        self.record_payload(event_type=event_type, payload=payload)
        return normalized

    def record_payload(self, *, event_type: str, payload: dict[str, Any]) -> None:
        self._buffered_events.append(
            RunEvent(
                run_id=self.run_id,
                sequence_no=len(self._buffered_events) + 1,
                event_type=event_type,
                payload_json=json.dumps(payload, ensure_ascii=False),
            )
        )

    def persist_completion(
        self,
        *,
        response_message_id: int | None,
        terminal_events: list[CanonicalEvent],
    ) -> list[str]:
        self.run.response_message_id = response_message_id
        self.run.status = "completed"
        self.run.completed_at = datetime.now(timezone.utc)
        self._db.add(self.run)

        encoded_lines: list[str] = []
        for event in terminal_events:
            self.record(event)
            line = encode_ndjson_event(event)
            if line:
                encoded_lines.append(line)

        self._commit_buffer()
        return encoded_lines

    def persist_completion_state(
        self,
        *,
        response_message_id: int | None,
        terminal_events: list[CanonicalEvent],
    ) -> None:
        self.run.response_message_id = response_message_id
        self.run.status = "completed"
        self.run.completed_at = datetime.now(timezone.utc)
        self._db.add(self.run)

        for event in terminal_events:
            self.record(event)

        self._commit_buffer()

    def persist_completion_payloads(
        self,
        *,
        response_message_id: int | None,
        terminal_payloads: list[dict[str, Any]],
    ) -> list[str]:
        self.run.response_message_id = response_message_id
        self.run.status = "completed"
        self.run.completed_at = datetime.now(timezone.utc)
        self._db.add(self.run)

        encoded_lines: list[str] = []
        for payload in terminal_payloads:
            event_type = str(payload.get("type", "event")).strip() or "event"
            self.record_payload(event_type=event_type, payload=payload)
            encoded_lines.append(json.dumps(payload, ensure_ascii=False) + "\n")

        self._commit_buffer()
        return encoded_lines

    def persist_failure(
        self,
        *,
        error_code: str,
        error_message: str,
        failure_event: CanonicalEvent | None = None,
    ) -> str | None:
        self.run.status = "failed"
        self.run.error_code = error_code
        self.run.error_message = error_message
        self.run.completed_at = datetime.now(timezone.utc)
        self._db.add(self.run)

        encoded_line: str | None = None
        if failure_event is not None:
            self.record(failure_event)
            encoded_line = encode_ndjson_event(failure_event)

        self._commit_buffer()
        return encoded_line

    def persist_failure_payload(
        self,
        *,
        error_code: str,
        error_message: str,
        failure_payload: dict[str, Any] | None = None,
    ) -> str | None:
        self.run.status = "failed"
        self.run.error_code = error_code
        self.run.error_message = error_message
        self.run.completed_at = datetime.now(timezone.utc)
        self._db.add(self.run)

        encoded_line: str | None = None
        if failure_payload is not None:
            event_type = str(failure_payload.get("type", "failed")).strip() or "failed"
            self.record_payload(event_type=event_type, payload=failure_payload)
            encoded_line = json.dumps(failure_payload, ensure_ascii=False) + "\n"

        self._commit_buffer()
        return encoded_line

    def _commit_buffer(self) -> None:
        if self._buffered_events:
            self._db.add_all(self._buffered_events)
        self._db.commit()
        self._buffered_events.clear()
