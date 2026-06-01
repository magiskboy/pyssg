"""Dependency and Connection.

Two distinct concepts, deliberately separated:

- ``Dependency`` is the *intent* to reference something (immutable, hashable,
  cacheable) emitted by a parser before resolution.
- ``Connection`` is the *resolved* relation living in the graph. It carries the
  incremental-invalidation semantics (``sensitive_to`` / ``restart_phase`` /
  ``reverse``) and is the single most important integration point for the
  incremental engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pyssg.core.types import Aspect, ConnectionKind, NodeId, Phase, SourceSpan


@dataclass(slots=True, frozen=True)
class Dependency:
    """An unresolved reference request emitted by a parser.

    Frozen and hashable so it can be cached and diffed across reparses.
    ``meta`` is a tuple of pairs (not a dict) precisely to stay hashable.
    """

    kind: str
    request: str
    loc: SourceSpan | None = None
    meta: tuple[tuple[str, object], ...] = ()


@dataclass(slots=True)
class Connection:
    """A resolved edge in the dependency graph.

    ``dst`` is ``None`` while unresolved (a placeholder, e.g. a broken
    wikilink). ``sensitive_to`` lists which aspects of ``dst`` propagate dirt
    to ``src``; ``restart_phase`` is the phase ``src`` re-enters when they do;
    ``reverse`` indicates whether the edge is indexed for ``in_edges`` lookups
    (backlinks require ``True``).
    """

    src: NodeId
    dst: NodeId | None
    kind: ConnectionKind
    dependency: Dependency
    sensitive_to: frozenset[Aspect] = field(default_factory=frozenset)
    restart_phase: Phase = Phase.RENDER
    reverse: bool = False
