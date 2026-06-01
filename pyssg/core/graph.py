"""The dependency graph.

A single graph is the source of truth for the data plane from after Load until
before Emit. It maintains a forward index (by ``src``) and a reverse
index (by ``dst``) so that dirty propagation can walk incoming edges. The
reverse index holds *only* connections declared ``reverse=True``; ``in_edges``
is therefore meaningful only for those edges.
"""

from __future__ import annotations

from pyssg.core.dependency import Connection, Dependency
from pyssg.core.node import Node
from pyssg.core.types import ConnectionKind, NodeId


class DependencyGraph:
    """Forward + reverse indexed graph of nodes and connections."""

    __slots__ = ("_in", "_nodes", "_out")

    def __init__(self) -> None:
        self._nodes: dict[NodeId, Node] = {}
        # Forward edges keyed by source. Includes placeholder edges (dst=None).
        self._out: dict[NodeId, list[Connection]] = {}
        # Reverse edges keyed by destination -- ONLY reverse=True, dst not None.
        self._in: dict[NodeId, list[Connection]] = {}

    # -- nodes -----------------------------------------------------------------

    def add_node(self, node: Node) -> None:
        self._nodes[node.id] = node

    def get(self, nid: NodeId) -> Node | None:
        return self._nodes.get(nid)

    def nodes(self) -> list[Node]:
        return list(self._nodes.values())

    def __contains__(self, nid: object) -> bool:
        return nid in self._nodes

    def remove(self, nid: NodeId) -> None:
        """Remove a node and every edge incident to it (both directions)."""
        self._nodes.pop(nid, None)
        # Drop this node's outgoing edges, cleaning their reverse-index entries.
        for conn in self._out.pop(nid, []):
            if conn.reverse and conn.dst is not None:
                self._discard(self._in.get(conn.dst), conn)
        # Drop incoming reverse edges, cleaning the peers' forward entries.
        for conn in self._in.pop(nid, []):
            self._discard(self._out.get(conn.src), conn)

    # -- edges -----------------------------------------------------------------

    def connect(self, c: Connection) -> None:
        """Record a connection in the forward (and, if reverse, reverse) index."""
        self._out.setdefault(c.src, []).append(c)
        if c.reverse and c.dst is not None:
            self._in.setdefault(c.dst, []).append(c)

    def disconnect(self, c: Connection) -> None:
        """Remove a previously recorded connection (by identity)."""
        self._discard(self._out.get(c.src), c)
        if c.reverse and c.dst is not None:
            self._discard(self._in.get(c.dst), c)

    def out_edges(self, nid: NodeId, kind: ConnectionKind | None = None) -> list[Connection]:
        edges = self._out.get(nid, ())
        if kind is None:
            return list(edges)
        return [c for c in edges if c.kind == kind]

    def in_edges(self, nid: NodeId, kind: ConnectionKind | None = None) -> list[Connection]:
        """Incoming reverse edges (only ``reverse=True`` edges)."""
        edges = self._in.get(nid, ())
        if kind is None:
            return list(edges)
        return [c for c in edges if c.kind == kind]

    def connection_of(self, nid: NodeId, dep: Dependency) -> Connection | None:
        """The forward connection of ``nid`` carrying ``dep``."""
        for conn in self._out.get(nid, ()):
            if conn.dependency == dep:
                return conn
        return None

    # -- internals -------------------------------------------------------------

    @staticmethod
    def _discard(edges: list[Connection] | None, c: Connection) -> None:
        """Remove ``c`` from ``edges`` by identity (connections are mutable)."""
        if edges is None:
            return
        for i, existing in enumerate(edges):
            if existing is c:
                del edges[i]
                return
