"""Keyed registry of processing-unit slots.

A ``Registry[K, V]`` maps a key (glob/ext, NodeKind, dependency.kind, ...) to a
slot value created on demand. Built-in plugins tap the slot returned by
``for_(key)``; the engine owns how those slots are invoked per phase.
"""

from __future__ import annotations

from collections.abc import Callable


class Registry[K, V]:
    """Lazily-populated mapping from key to slot, with ``for_(key)`` access."""

    __slots__ = ("_factory", "_slots")

    def __init__(self, factory: Callable[[K], V]) -> None:
        """``factory`` builds a fresh slot the first time a key is requested."""
        self._factory = factory
        self._slots: dict[K, V] = {}

    def for_(self, key: K) -> V:
        """Return the slot for ``key``, creating it on first access."""
        slot = self._slots.get(key)
        if slot is None:
            slot = self._factory(key)
            self._slots[key] = slot
        return slot

    def keys(self) -> list[K]:
        return list(self._slots)

    def items(self) -> list[tuple[K, V]]:
        return list(self._slots.items())

    def __contains__(self, key: object) -> bool:
        return key in self._slots

    def __len__(self) -> int:
        return len(self._slots)
