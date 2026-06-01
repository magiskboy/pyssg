"""Phase scheduler.

Runs a phase's work over many nodes. Because every processing unit is pure in
its declared inputs, the order of completion cannot affect results,
which is what makes parallelization sound. This M5 implementation is a
deterministic sequential ``map``; it preserves input order so output is
reproducible, and the interface leaves room to swap in a thread/process pool
later without touching callers.
"""

from __future__ import annotations

from collections.abc import Callable

from pyssg.core.types import NodeId


class Scheduler:
    """Deterministic map over node ids within a single phase."""

    __slots__ = ()

    def map[T](self, ids: list[NodeId], fn: Callable[[NodeId], T]) -> list[T]:
        """Apply ``fn`` to each id, returning results in input order."""
        return [fn(nid) for nid in ids]
