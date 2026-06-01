"""Dirty propagation with early-cutoff.

The heart of the incremental engine. Three mechanisms combine:

1. Reverse edges + aspect registration: when an aspect of a node changes, only
   incoming edges whose ``sensitive_to`` includes that aspect propagate dirt,
   each at its declared ``restart_phase``.
2. Early-cutoff: after recomputing a node, only aspects that *actually* changed
   propagate. An unchanged output stops the cascade right there.
3. Fixpoint: cutoff guarantees hashes stabilize, so even cyclic graphs converge
   (the ``WorkList`` loop terminates).

Stdlib only.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

from pyssg.core.types import NodeId, Phase

if TYPE_CHECKING:
    from pyssg.core.build import Build


class WorkList:
    """Pending work, keyed by node, holding the *smallest* dirty-from phase.

    A deeper (smaller) phase subsumes a shallower one for the same node:
    if a node is dirty from PARSE and also from RENDER, it must
    restart from PARSE.
    """

    __slots__ = ("_m",)

    def __init__(self, seeds: Iterable[tuple[NodeId, Phase]] | None = None) -> None:
        self._m: dict[NodeId, Phase] = {}
        for nid, phase in seeds or ():
            self.add(nid, phase)

    def add(self, nid: NodeId, from_phase: Phase) -> None:
        current = self._m.get(nid)
        if current is None or from_phase < current:
            self._m[nid] = from_phase

    def drain(self) -> dict[NodeId, Phase]:
        """Return all pending work and clear it (one fixpoint round)."""
        pending = self._m
        self._m = {}
        return pending

    def get(self, nid: NodeId) -> Phase | None:
        return self._m.get(nid)

    def __contains__(self, nid: object) -> bool:
        return nid in self._m

    def __bool__(self) -> bool:
        return bool(self._m)

    def __len__(self) -> int:
        return len(self._m)


def changed_aspects(build: Build, nid: NodeId) -> set[str]:
    """Aspects whose hash differs from the committed baseline."""
    node = build.graph.get(nid)
    if node is None:
        return set()
    prev = build.prev_hashes(nid)
    return {aspect for aspect, h in node.hashes.items() if prev.get(aspect) != h}


def propagate_aspect_changes(build: Build, nid: NodeId, work: WorkList) -> None:
    """Spread dirt from a recomputed node to its dependents, with cutoff.

    Walks incoming reverse edges; an edge propagates only if it is sensitive to
    an aspect that actually changed, restarting the source at the edge's
    ``restart_phase``. If nothing changed, the cascade stops (early-cutoff).
    """
    changed = changed_aspects(build, nid)
    if not changed:
        return  # EARLY-CUTOFF
    for conn in build.graph.in_edges(nid):
        if conn.sensitive_to & changed:
            work.add(conn.src, conn.restart_phase)
    build.commit_hashes(nid)
