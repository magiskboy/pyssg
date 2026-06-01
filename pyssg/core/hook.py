"""The hook system (control plane).

Four hook flavors borrowed from tapable, each encoding a different ordering /
value-flow semantic. Taps declare *relative* order via ``stage`` (coarse integer
bucket) plus ``before`` / ``after`` name constraints; before every ``call`` the
taps are topologically sorted, and a constraint cycle raises ``HookOrderError``.
Stdlib only.
"""

from __future__ import annotations

import heapq
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import overload

from pyssg.core.errors import HookOrderError


@dataclass(slots=True)
class Tap[F]:
    """A registered hook callback plus its ordering metadata."""

    name: str
    fn: F
    stage: int = 0
    before: tuple[str, ...] = ()
    after: tuple[str, ...] = ()


def order_taps[F](taps: list[Tap[F]]) -> list[Tap[F]]:
    """Order taps by ascending ``stage``, then topologically within each stage.

    Within a stage, ``after`` means "run me after that named tap" and ``before``
    means "run me before it". Ties break by registration order for determinism
    (build output must not depend on tap insertion races). Unknown
    names in constraints are ignored (tapable semantics). A cycle raises
    ``HookOrderError``.
    """
    by_stage: dict[int, list[Tap[F]]] = {}
    for tap in taps:
        by_stage.setdefault(tap.stage, []).append(tap)
    ordered: list[Tap[F]] = []
    for stage in sorted(by_stage):
        ordered.extend(_topo_within_stage(by_stage[stage]))
    return ordered


def _topo_within_stage[F](taps: list[Tap[F]]) -> list[Tap[F]]:
    n = len(taps)
    name_to_indices: dict[str, list[int]] = {}
    for i, tap in enumerate(taps):
        name_to_indices.setdefault(tap.name, []).append(i)

    # adjacency[a] = {b, ...} means a must run before b.
    adjacency: list[set[int]] = [set() for _ in range(n)]
    indegree = [0] * n

    def add_edge(before_i: int, after_i: int) -> None:
        if after_i not in adjacency[before_i]:
            adjacency[before_i].add(after_i)
            indegree[after_i] += 1

    for i, tap in enumerate(taps):
        for name in tap.after:
            for j in name_to_indices.get(name, ()):
                add_edge(j, i)  # j before i
        for name in tap.before:
            for j in name_to_indices.get(name, ()):
                add_edge(i, j)  # i before j

    # Kahn's algorithm; a min-heap on index keeps it stable by registration order.
    ready = [i for i in range(n) if indegree[i] == 0]
    heapq.heapify(ready)
    result: list[Tap[F]] = []
    while ready:
        i = heapq.heappop(ready)
        result.append(taps[i])
        for j in sorted(adjacency[i]):
            indegree[j] -= 1
            if indegree[j] == 0:
                heapq.heappush(ready, j)

    if len(result) != n:
        stuck = sorted(taps[i].name for i in range(n) if indegree[i] > 0)
        raise HookOrderError(f"cyclic before/after constraints among taps: {stuck}")
    return result


class _HookBase[F]:
    """Shared tap registry + lazy ordering for all hook flavors."""

    def __init__(self) -> None:
        self._taps: list[Tap[F]] = []
        self._ordered: list[Tap[F]] | None = None

    @overload
    def tap(
        self,
        opt: Tap[F],
        fn: None = None,
        *,
        stage: int = 0,
        before: tuple[str, ...] = (),
        after: tuple[str, ...] = (),
    ) -> None: ...

    @overload
    def tap(
        self,
        opt: str,
        fn: F,
        *,
        stage: int = 0,
        before: tuple[str, ...] = (),
        after: tuple[str, ...] = (),
    ) -> None: ...

    @overload
    def tap(
        self,
        opt: str,
        fn: None = None,
        *,
        stage: int = 0,
        before: tuple[str, ...] = (),
        after: tuple[str, ...] = (),
    ) -> Callable[[F], F]: ...

    def tap(
        self,
        opt: str | Tap[F],
        fn: F | None = None,
        *,
        stage: int = 0,
        before: tuple[str, ...] = (),
        after: tuple[str, ...] = (),
    ) -> Callable[[F], F] | None:
        """Register a callback.

        Forms: ``tap(Tap(...))`` (full spec), ``tap("name", fn)`` (direct), or
        ``@tap("name", stage=...)`` (decorator -- returns the function unchanged).
        """
        if isinstance(opt, Tap):
            self._register(opt)
            return None
        if fn is not None:
            self._register(Tap(opt, fn, stage, before, after))
            return None

        def decorator(decorated: F) -> F:
            self._register(Tap(opt, decorated, stage, before, after))
            return decorated

        return decorator

    def _register(self, tap: Tap[F]) -> None:
        self._taps.append(tap)
        self._ordered = None

    def _fns(self) -> list[F]:
        if self._ordered is None:
            self._ordered = order_taps(self._taps)
        return [tap.fn for tap in self._ordered]


class SyncHook[**P](_HookBase[Callable[P, object]]):
    """Series hook: call every tap in order, ignore return values."""

    def call(self, *args: P.args, **kwargs: P.kwargs) -> None:
        for fn in self._fns():
            fn(*args, **kwargs)


class BailHook[**P, R](_HookBase[Callable[P, "R | None"]]):
    """Bail hook: stop at the first tap returning a non-None value."""

    def call(self, *args: P.args, **kwargs: P.kwargs) -> R | None:
        for fn in self._fns():
            result = fn(*args, **kwargs)
            if result is not None:
                return result
        return None


class WaterfallHook[T](_HookBase[Callable[..., T]]):
    """Waterfall hook: thread a value through each tap.

    Each tap receives ``(value, *rest)`` and returns the next value. ``*rest``
    carries unchanged context (e.g. the page being rendered).
    """

    def call(self, value: T, *rest: object) -> T:
        for fn in self._fns():
            value = fn(value, *rest)
        return value


class AsyncSeriesHook[**P](_HookBase[Callable[P, Awaitable[object]]]):
    """Async series hook: await each tap in order (for I/O phases)."""

    async def call(self, *args: P.args, **kwargs: P.kwargs) -> None:
        for fn in self._fns():
            await fn(*args, **kwargs)


# Re-exported so callers don't reach into a deeper module for the field helper.
__all__ = [
    "AsyncSeriesHook",
    "BailHook",
    "SyncHook",
    "Tap",
    "WaterfallHook",
    "order_taps",
]
