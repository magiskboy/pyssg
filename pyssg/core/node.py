"""Graph nodes.

``Node`` is the generic graph vertex; ``Document`` / ``Asset`` / ``Page`` are
subclasses. Heavy payloads (parsed AST, rendered bytes) are kept *lazy and
evictable* so only metadata + per-aspect hashes stay resident -- essential for
large wikis. All node dataclasses are ``kw_only`` so subclasses can add required
fields without the default-ordering trap.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pyssg.core.dependency import Dependency
from pyssg.core.types import Aspect, Digest, NodeId, NodeKind, Phase


@dataclass(slots=True, kw_only=True)
class Node:
    """A vertex in the dependency graph.

    ``state`` is the highest phase whose result is currently valid. ``hashes``
    holds one digest *per aspect* (not a single whole-node hash) -- this is what
    makes early-cutoff possible. ``_ast`` / ``_payload`` are heavy and
    evictable; access them via the ``ast`` / ``payload`` properties.
    """

    id: NodeId
    kind: NodeKind
    source_path: str | None = None
    state: Phase = Phase.LOAD
    meta: dict[str, object] = field(default_factory=dict)
    hashes: dict[Aspect, Digest] = field(default_factory=dict)
    dependencies: list[Dependency] = field(default_factory=list)
    _ast: object | None = field(default=None, repr=False)
    _payload: bytes | str | None = field(default=None, repr=False)

    @property
    def ast(self) -> object | None:
        """Parser-specific AST; may be ``None`` if not yet parsed or evicted."""
        return self._ast

    @ast.setter
    def ast(self, value: object | None) -> None:
        self._ast = value

    @property
    def payload(self) -> bytes | str | None:
        """Rendered HTML / asset bytes; may be ``None`` if evicted."""
        return self._payload

    @payload.setter
    def payload(self, value: bytes | str | None) -> None:
        self._payload = value

    def add_dependency(self, dep: Dependency) -> None:
        """Record a reference request (called by parsers)."""
        self.dependencies.append(dep)


@dataclass(slots=True, kw_only=True)
class Document(Node):
    """A parsed source document (Markdown, data, Excalidraw, ...)."""


@dataclass(slots=True, kw_only=True)
class Asset(Node):
    """Static bytes plus metadata (size, mime). May be copied/optimized."""

    output_path: str | None = None


@dataclass(slots=True, kw_only=True)
class Page(Node):
    """A derived output node.

    ``generated_from`` records provenance (a page may derive from several
    documents, e.g. a paginated list). ``template`` selects the layout.
    """

    url: str
    generated_from: list[NodeId] = field(default_factory=list)
    template: str | None = None
