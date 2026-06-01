"""Unit tests: hook flavors + topo ordering."""

from __future__ import annotations

import asyncio
import unittest

from pyssg.core.errors import HookOrderError
from pyssg.core.hook import (
    AsyncSeriesHook,
    BailHook,
    SyncHook,
    Tap,
    WaterfallHook,
    order_taps,
)


class HookTest(unittest.TestCase):
    def test_sync_hook_calls_all_in_order(self) -> None:
        hook: SyncHook[list[str]] = SyncHook()
        hook.tap("a", lambda acc: acc.append("a"))
        hook.tap("b", lambda acc: acc.append("b"))
        seen: list[str] = []
        hook.call(seen)
        self.assertEqual(seen, ["a", "b"])

    def test_sync_hook_decorator_form(self) -> None:
        hook: SyncHook[list[str]] = SyncHook()

        @hook.tap("one")
        def _one(acc: list[str]) -> None:
            acc.append("one")

        # The decorator returns the function unchanged.
        self.assertEqual(_one.__name__, "_one")
        seen: list[str] = []
        hook.call(seen)
        self.assertEqual(seen, ["one"])

    def test_stage_orders_before_before_after(self) -> None:
        hook: SyncHook[list[str]] = SyncHook()
        hook.tap("late", lambda acc: acc.append("late"), stage=200)
        hook.tap("early", lambda acc: acc.append("early"), stage=100)
        seen: list[str] = []
        hook.call(seen)
        self.assertEqual(seen, ["early", "late"])

    def test_before_after_constraints_within_stage(self) -> None:
        hook: SyncHook[list[str]] = SyncHook()
        # Register in an order that only a topo sort can fix.
        hook.tap("c", lambda acc: acc.append("c"), after=("b",))
        hook.tap("a", lambda acc: acc.append("a"), before=("b",))
        hook.tap("b", lambda acc: acc.append("b"))
        seen: list[str] = []
        hook.call(seen)
        self.assertEqual(seen, ["a", "b", "c"])

    def test_unknown_constraint_name_is_ignored(self) -> None:
        hook: SyncHook[list[str]] = SyncHook()
        hook.tap("a", lambda acc: acc.append("a"), after=("does-not-exist",))
        seen: list[str] = []
        hook.call(seen)
        self.assertEqual(seen, ["a"])

    def test_cycle_raises_hook_order_error(self) -> None:
        hook: SyncHook[list[str]] = SyncHook()
        hook.tap("a", lambda acc: acc.append("a"), before=("b",))
        hook.tap("b", lambda acc: acc.append("b"), before=("a",))
        with self.assertRaises(HookOrderError):
            hook.call([])

    def test_bail_hook_stops_at_first_non_none(self) -> None:
        hook: BailHook[[int], str] = BailHook()
        calls: list[str] = []

        def first(_n: int) -> str | None:
            calls.append("first")
            return None

        def second(n: int) -> str | None:
            calls.append("second")
            return f"got-{n}"

        def third(_n: int) -> str | None:
            calls.append("third")
            return "unreached"

        hook.tap("first", first)
        hook.tap("second", second)
        hook.tap("third", third)
        self.assertEqual(hook.call(7), "got-7")
        self.assertEqual(calls, ["first", "second"])  # third never runs

    def test_bail_hook_returns_none_when_all_none(self) -> None:
        hook: BailHook[[], int] = BailHook()
        hook.tap("a", lambda: None)
        self.assertIsNone(hook.call())

    def test_waterfall_threads_value(self) -> None:
        hook: WaterfallHook[int] = WaterfallHook()
        hook.tap("double", lambda v: v * 2)
        hook.tap("inc", lambda v: v + 1)
        self.assertEqual(hook.call(3), 7)  # (3*2)+1

    def test_waterfall_passes_rest_unchanged(self) -> None:
        hook: WaterfallHook[str] = WaterfallHook()
        hook.tap("suffix", lambda v, tag: f"{v}{tag}")
        self.assertEqual(hook.call("base", "-x"), "base-x")

    def test_async_series_awaits_in_order(self) -> None:
        hook: AsyncSeriesHook[list[str]] = AsyncSeriesHook()

        async def a(acc: list[str]) -> None:
            await asyncio.sleep(0)
            acc.append("a")

        async def b(acc: list[str]) -> None:
            acc.append("b")

        hook.tap("a", a)
        hook.tap("b", b)
        seen: list[str] = []
        asyncio.run(hook.call(seen))
        self.assertEqual(seen, ["a", "b"])

    def test_order_taps_is_stable_for_independent_taps(self) -> None:
        taps = [Tap(name=f"t{i}", fn=lambda: None) for i in range(5)]
        self.assertEqual([t.name for t in order_taps(taps)], ["t0", "t1", "t2", "t3", "t4"])
