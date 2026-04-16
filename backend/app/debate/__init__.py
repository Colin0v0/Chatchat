"""Debate package helpers.

This module intentionally avoids eagerly re-exporting symbols from
``app.debate.service`` so stale names in ``__init__`` do not break package
imports when the service surface changes.
"""

from importlib import import_module
from typing import Any


def __getattr__(name: str) -> Any:
    service = import_module(f"{__name__}.service")
    try:
        return getattr(service, name)
    except AttributeError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc


def __dir__() -> list[str]:
    service = import_module(f"{__name__}.service")
    return sorted(set(globals()) | set(dir(service)))
