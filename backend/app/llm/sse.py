from __future__ import annotations

from collections.abc import AsyncIterator


def _flush_sse_data_lines(data_lines: list[str]) -> str | None:
    if not data_lines:
        return None
    payload = "\n".join(data_lines).strip()
    data_lines.clear()
    return payload or None


async def iter_sse_payloads(lines: AsyncIterator[str]) -> AsyncIterator[str]:
    data_lines: list[str] = []
    in_sse_event = False

    async for raw_line in lines:
        line = raw_line.rstrip("\r")
        if not line:
            if not in_sse_event:
                continue
            payload = _flush_sse_data_lines(data_lines)
            in_sse_event = False
            if payload:
                yield payload
            continue

        if line.startswith(":"):
            in_sse_event = True
            continue

        field, separator, value = line.partition(":")
        if separator and field in {"data", "event", "id", "retry"}:
            in_sse_event = True
            if field == "data":
                data_lines.append(value[1:] if value.startswith(" ") else value)
            continue

        if in_sse_event:
            continue

        payload = line.strip()
        if payload:
            yield payload

    if in_sse_event:
        payload = _flush_sse_data_lines(data_lines)
        if payload:
            yield payload
