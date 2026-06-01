"""Dependency diffing.

When a node is reparsed its set of ``Dependency`` may change. Diffing old vs new
yields connections to add/remove, and the consequences are *bidirectional* -- the
trickiest part of incremental correctness:

- A removed edge: the old ``dst`` loses an incoming edge; if it was a reverse
  edge (e.g. a backlink) the old ``dst`` must re-render.
- An added edge: the node needs RESOLVE; the new ``dst`` gains an incoming edge
  and, if reverse, must re-render. A ``dst`` that does not exist yet becomes a
  placeholder.

In M5 the markdown pipeline emits no link dependencies (links arrive in M6), so
these run as no-ops over real builds; they are implemented and unit-tested here
so the machinery is ready and correct.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pyssg.core.build import ResolveContext
from pyssg.core.types import Phase

if TYPE_CHECKING:
    from pyssg.core.build import Build
    from pyssg.core.dependency import Dependency
    from pyssg.core.incremental.invalidation import WorkList
    from pyssg.core.types import NodeId


def apply_dep_diff(build: Build, nid: NodeId, new_deps: list[Dependency], work: WorkList) -> None:
    """Reconcile a node's dependencies, propagating both directions."""
    node = build.graph.get(nid)
    if node is None:
        return
    old = set(node.dependencies)
    new = set(new_deps)

    for dep in old - new:  # removed dependencies
        conn = build.graph.connection_of(nid, dep)
        if conn is None:
            continue
        build.graph.disconnect(conn)
        if conn.dst is not None and conn.reverse:
            work.add(conn.dst, Phase.RENDER)  # lost a backlink -> re-render

    if new - old:  # any added dependency needs resolving
        work.add(nid, Phase.RESOLVE)

    node.dependencies = list(new_deps)


def resolve_pending(build: Build, nids: list[NodeId], work: WorkList) -> None:
    """Resolve dependencies that have no connection yet.

    For each given node, run the ``resolve`` bail hook on every dependency that
    lacks a connection; register the edge and, if it is reverse, mark the
    destination for re-render.
    """
    for nid in nids:
        node = build.graph.get(nid)
        if node is None:
            continue
        for dep in node.dependencies:
            if build.graph.connection_of(nid, dep) is not None:
                continue
            conn = build.hooks.resolve.call(dep, ResolveContext(build, nid))
            if conn is None:
                continue
            build.graph.connect(conn)
            if conn.dst is not None and conn.reverse:
                work.add(conn.dst, Phase.RENDER)
