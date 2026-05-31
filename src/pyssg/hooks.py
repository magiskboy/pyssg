"""Hook system inspired by webpack's Tapable.

The kernel provides only three synchronous hook types, enough to cover every
SSG need:

- ``SyncHook``         : fire an event, ignore return values.
- ``SyncBailHook``     : stop at the first tap returning a non-``None`` value.
- ``SyncWaterfallHook``: pipeline flow, each tap's result feeds the next.

Every tap carries a ``stage`` (default 0). Taps run in ascending stage order;
within the same stage registration order is preserved (stable sort).

Hooks take positional arguments and are parameterized with ``TypeVarTuple`` for
concise, natural signatures: ``SyncHook[Source, Build]`` instead of
``ParamSpec``'s double-bracket syntax.
"""

from __future__ import annotations

from collections.abc import Callable


class _TapRegistry[F]:
    """Stores and orders taps; shared by every hook type."""

    __slots__ = ("_taps", "_counter", "_dirty")

    def __init__(self) -> None:
        self._taps: list[tuple[int, int, str, F]] = []
        self._counter = 0
        self._dirty = False

    def add(self, name: str, fn: F, stage: int) -> None:
        self._taps.append((stage, self._counter, name, fn))
        self._counter += 1
        self._dirty = True

    def functions(self) -> list[F]:
        if self._dirty:
            self._taps.sort(key=lambda tap: (tap[0], tap[1]))
            self._dirty = False
        return [tap[3] for tap in self._taps]

    @property
    def has_taps(self) -> bool:
        return bool(self._taps)


class SyncHook[*Ts]:
    """Call every tap in turn; return values are ignored."""

    __slots__ = ("_registry",)

    def __init__(self) -> None:
        self._registry: _TapRegistry[Callable[[*Ts], object]] = _TapRegistry()

    def tap(self, name: str, fn: Callable[[*Ts], object], *, stage: int = 0) -> None:
        self._registry.add(name, fn, stage)

    @property
    def has_taps(self) -> bool:
        return self._registry.has_taps

    def call(self, *args: *Ts) -> None:
        for fn in self._registry.functions():
            fn(*args)


class SyncBailHook[R, *Ts]:
    """Return the result of the first tap that yields a non-``None`` value."""

    __slots__ = ("_registry",)

    def __init__(self) -> None:
        self._registry: _TapRegistry[Callable[[*Ts], R | None]] = _TapRegistry()

    def tap(self, name: str, fn: Callable[[*Ts], R | None], *, stage: int = 0) -> None:
        self._registry.add(name, fn, stage)

    def call(self, *args: *Ts) -> R | None:
        for fn in self._registry.functions():
            result = fn(*args)
            if result is not None:
                return result
        return None


class SyncWaterfallHook[T, *Ts]:
    """Pipeline flow: the seed value is threaded through and mutated by taps.

    A tap returning ``None`` means "no change" and keeps the previous value
    (mirroring webpack's waterfall semantics for ``undefined``).
    """

    __slots__ = ("_registry",)

    def __init__(self) -> None:
        self._registry: _TapRegistry[Callable[[T, *Ts], T | None]] = _TapRegistry()

    def tap(
        self,
        name: str,
        fn: Callable[[T, *Ts], T | None],
        *,
        stage: int = 0,
    ) -> None:
        self._registry.add(name, fn, stage)

    def call(self, value: T, *args: *Ts) -> T:
        for fn in self._registry.functions():
            result = fn(value, *args)
            if result is not None:
                value = result
        return value
