from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger("chatchat.runtime")


def ollama_keep_alive_value(seconds: int) -> int:
    return 0 if seconds <= 0 else seconds


def log_ollama_request(
    *,
    kind: str,
    model: str,
    keep_alive: int,
    started_at: float,
    response_payload: dict[str, Any],
) -> None:
    elapsed_ms = (time.perf_counter() - started_at) * 1000
    load_ms = _nanoseconds_to_ms(response_payload.get("load_duration"))
    total_ms = _nanoseconds_to_ms(response_payload.get("total_duration"))
    prompt_eval_count = response_payload.get("prompt_eval_count", "n/a")
    eval_count = response_payload.get("eval_count", "n/a")
    done_reason = response_payload.get("done_reason", "n/a")

    logger.info(
        "[ollama-%s] model=%s keep_alive=%s elapsed_ms=%.1f load_ms=%s total_ms=%s prompt_eval_count=%s eval_count=%s done_reason=%s",
        kind,
        model,
        keep_alive,
        elapsed_ms,
        _format_metric(load_ms),
        _format_metric(total_ms),
        prompt_eval_count,
        eval_count,
        done_reason,
    )


def _nanoseconds_to_ms(value: object) -> float | None:
    if isinstance(value, (int, float)):
        return float(value) / 1_000_000
    return None


def _format_metric(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.1f}"
