import threading
import time
import unittest

from app.core.idle_runtime import IdleRuntime


class IdleRuntimeTests(unittest.TestCase):
    def test_unloads_after_idle_timeout(self):
        events: list[str] = []

        runtime = IdleRuntime(
            runtime_name="test.runtime",
            loader=lambda: events.append("load") or object(),
            unloader=lambda _: events.append("unload"),
            idle_timeout_seconds=0.05,
        )

        with runtime.lease():
            self.assertTrue(runtime.is_loaded())

        time.sleep(0.12)

        self.assertEqual(events, ["load", "unload"])
        self.assertFalse(runtime.is_loaded())

    def test_does_not_unload_while_in_use(self):
        events: list[str] = []
        release_gate = threading.Event()

        runtime = IdleRuntime(
            runtime_name="test.runtime",
            loader=lambda: events.append("load") or object(),
            unloader=lambda _: events.append("unload"),
            idle_timeout_seconds=0.05,
        )

        def hold_lease() -> None:
            with runtime.lease():
                release_gate.wait(timeout=1)

        worker = threading.Thread(target=hold_lease)
        worker.start()

        time.sleep(0.12)
        self.assertEqual(events, ["load"])
        self.assertTrue(runtime.is_loaded())

        release_gate.set()
        worker.join(timeout=1)
        time.sleep(0.12)

        self.assertEqual(events, ["load", "unload"])
        self.assertFalse(runtime.is_loaded())
