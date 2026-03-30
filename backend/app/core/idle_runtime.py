from __future__ import annotations

import logging
from contextlib import contextmanager
from threading import Lock, Timer
from typing import Callable, Generic, Iterator, TypeVar

T = TypeVar("T")
logger = logging.getLogger("chatchat.runtime")


class IdleRuntime(Generic[T]):
    def __init__(
        self,
        *,
        runtime_name: str,
        loader: Callable[[], T],
        unloader: Callable[[T], None],
        idle_timeout_seconds: float,
    ):
        self._runtime_name = runtime_name
        self._loader = loader
        self._unloader = unloader
        self._idle_timeout_seconds = max(0.0, idle_timeout_seconds)
        self._lock = Lock()
        self._instance: T | None = None
        self._active_users = 0
        self._timer: Timer | None = None

    @contextmanager
    def lease(self) -> Iterator[T]:
        instance = self._acquire()
        try:
            yield instance
        finally:
            self._release()

    def unload_now(self) -> None:
        with self._lock:
            self._cancel_timer_locked()
            self._unload_locked(reason="manual")

    def is_loaded(self) -> bool:
        with self._lock:
            return self._instance is not None

    def _acquire(self) -> T:
        with self._lock:
            self._cancel_timer_locked()
            if self._instance is None:
                self._instance = self._load_instance_locked()
            self._active_users += 1
            return self._instance

    def _release(self) -> None:
        with self._lock:
            if self._active_users == 0:
                raise RuntimeError("IdleRuntime release called without an active lease.")

            self._active_users -= 1
            if self._active_users > 0 or self._instance is None:
                return

            if self._idle_timeout_seconds == 0:
                self._unload_locked(reason="idle")
                return

            logger.info(
                "[model-idle] runtime=%s timeout_seconds=%.1f status=scheduled",
                self._runtime_name,
                self._idle_timeout_seconds,
            )
            timer = Timer(self._idle_timeout_seconds, self._expire_if_idle)
            timer.daemon = True
            self._timer = timer
            timer.start()

    def _expire_if_idle(self) -> None:
        with self._lock:
            self._timer = None
            if self._active_users > 0:
                return
            self._unload_locked(reason="idle")

    def _cancel_timer_locked(self) -> None:
        if self._timer is None:
            return
        self._timer.cancel()
        self._timer = None

    def _load_instance_locked(self) -> T:
        logger.info("[model-load] runtime=%s status=start", self._runtime_name)
        try:
            instance = self._loader()
        except Exception:
            logger.exception("[model-load] runtime=%s status=failed", self._runtime_name)
            raise
        logger.info("[model-load] runtime=%s status=done", self._runtime_name)
        return instance

    def _unload_locked(self, *, reason: str) -> None:
        if self._instance is None or self._active_users > 0:
            return

        instance = self._instance
        self._instance = None
        logger.info("[model-unload] runtime=%s reason=%s status=start", self._runtime_name, reason)
        try:
            self._unloader(instance)
        except Exception:
            logger.exception(
                "[model-unload] runtime=%s reason=%s status=failed",
                self._runtime_name,
                reason,
            )
            raise
        logger.info("[model-unload] runtime=%s reason=%s status=done", self._runtime_name, reason)
