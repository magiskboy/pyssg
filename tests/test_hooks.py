"""Unit tests for the hook system."""

from __future__ import annotations

import unittest

from pyssg.hooks import SyncBailHook, SyncHook, SyncWaterfallHook


class SyncHookTest(unittest.TestCase):
    def test_calls_all_taps_in_registration_order(self) -> None:
        hook: SyncHook[list[str]] = SyncHook()
        hook.tap("a", lambda log: log.append("a"))
        hook.tap("b", lambda log: log.append("b"))

        log: list[str] = []
        hook.call(log)

        self.assertEqual(log, ["a", "b"])

    def test_no_taps_is_noop(self) -> None:
        hook: SyncHook[list[str]] = SyncHook()
        log: list[str] = []
        hook.call(log)
        self.assertEqual(log, [])

    def test_stage_orders_taps(self) -> None:
        hook: SyncHook[list[str]] = SyncHook()
        hook.tap("late", lambda log: log.append("late"), stage=10)
        hook.tap("early", lambda log: log.append("early"), stage=-10)
        hook.tap("mid", lambda log: log.append("mid"))

        log: list[str] = []
        hook.call(log)

        self.assertEqual(log, ["early", "mid", "late"])

    def test_same_stage_keeps_registration_order(self) -> None:
        hook: SyncHook[list[str]] = SyncHook()
        hook.tap("first", lambda log: log.append("first"), stage=5)
        hook.tap("second", lambda log: log.append("second"), stage=5)

        log: list[str] = []
        hook.call(log)

        self.assertEqual(log, ["first", "second"])

    def test_tap_after_call_is_picked_up(self) -> None:
        hook: SyncHook[list[str]] = SyncHook()
        hook.tap("a", lambda log: log.append("a"))

        log: list[str] = []
        hook.call(log)
        hook.tap("b", lambda log: log.append("b"))
        hook.call(log)

        self.assertEqual(log, ["a", "a", "b"])


class SyncBailHookTest(unittest.TestCase):
    def test_returns_first_non_none(self) -> None:
        hook: SyncBailHook[str, str] = SyncBailHook()
        hook.tap("skip", lambda value: None)
        hook.tap("handle", lambda value: f"handled:{value}")
        hook.tap("never", lambda value: "should-not-run")

        self.assertEqual(hook.call("x"), "handled:x")

    def test_returns_none_when_no_tap_handles(self) -> None:
        hook: SyncBailHook[str, str] = SyncBailHook()
        hook.tap("skip", lambda value: None)
        self.assertIsNone(hook.call("x"))

    def test_bail_respects_stage(self) -> None:
        hook: SyncBailHook[str, str] = SyncBailHook()
        hook.tap("late", lambda value: "late", stage=10)
        hook.tap("early", lambda value: "early", stage=0)

        self.assertEqual(hook.call("x"), "early")

    def test_stops_at_first_handler(self) -> None:
        seen: list[str] = []

        def first(value: str) -> str:
            seen.append("first")
            return "done"

        def second(value: str) -> str:
            seen.append("second")
            return "late"

        hook: SyncBailHook[str, str] = SyncBailHook()
        hook.tap("first", first)
        hook.tap("second", second)

        self.assertEqual(hook.call("x"), "done")
        self.assertEqual(seen, ["first"])


class SyncWaterfallHookTest(unittest.TestCase):
    def test_threads_value_through_taps(self) -> None:
        hook: SyncWaterfallHook[int] = SyncWaterfallHook()
        hook.tap("double", lambda value: value * 2)
        hook.tap("plus_one", lambda value: value + 1)

        self.assertEqual(hook.call(3), 7)

    def test_none_keeps_previous_value(self) -> None:
        hook: SyncWaterfallHook[int] = SyncWaterfallHook()
        hook.tap("double", lambda value: value * 2)
        hook.tap("noop", lambda value: None)
        hook.tap("plus_one", lambda value: value + 1)

        self.assertEqual(hook.call(3), 7)

    def test_no_taps_returns_input(self) -> None:
        hook: SyncWaterfallHook[int] = SyncWaterfallHook()
        self.assertEqual(hook.call(42), 42)

    def test_extra_args_are_passed_through(self) -> None:
        hook: SyncWaterfallHook[int, int] = SyncWaterfallHook()
        hook.tap("add", lambda value, delta: value + delta)
        hook.tap("add_again", lambda value, delta: value + delta)

        self.assertEqual(hook.call(0, 5), 10)

    def test_stage_orders_pipeline(self) -> None:
        hook: SyncWaterfallHook[str] = SyncWaterfallHook()
        hook.tap("wrap", lambda value: f"[{value}]", stage=10)
        hook.tap("base", lambda value: value.upper(), stage=0)

        self.assertEqual(hook.call("hi"), "[HI]")


if __name__ == "__main__":
    unittest.main()
