from __future__ import annotations

import json
from dataclasses import dataclass
from uuid import uuid4


@dataclass(slots=True)
class StoredRunEvent:
    seq: int
    line: str


def create_run_id() -> str:
    return uuid4().hex


def encode_resumable_event(raw_line: str, *, run_id: str, seq: int) -> str:
    payload = json.loads(raw_line)
    if not isinstance(payload, dict):
        raise TypeError("Run event payload must be a JSON object.")

    payload["run_id"] = run_id
    payload["seq"] = seq
    return json.dumps(payload, ensure_ascii=False) + "\n"
