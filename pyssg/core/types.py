"""Foundational data-plane types.

Stdlib only. These are the vocabulary shared by every other core
module: stable logical identity (``NodeId``), per-aspect hashing keys
(``Aspect``/``Digest``), the fixed phase ladder (``Phase``), and the node/edge
kind enumerations.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, IntEnum

# Stable logical identity of a node: frontmatter id / slug, falling back to
# path. Deliberately NOT a content hash (would change on edit) and NOT
# hard-bound to the path (would break on rename).
type NodeId = str

# Name of one hashed facet of a node, e.g. "raw" | "frontmatter" | "body" |
# "title" | "url" | "exists" | "outline" | "rendered_html" | "block.<id>" ...
# Each node hashes facets independently for early-cutoff.
type Aspect = str

# Hex digest produced by the aspect hasher.
type Digest = str


class Phase(IntEnum):
    """Node lifecycle phases.

    Order is the re-entry depth: a smaller value is *deeper* and therefore more
    expensive to recompute. A change marks a node ``dirty-from(P)``; results up
    to ``P - 1`` stay valid and work restarts at ``P``.
    """

    LOAD = 0
    PARSE = 1
    RESOLVE = 2
    COLLECT = 3
    GENERATE = 4
    RENDER = 5
    OPTIMIZE = 6
    EMIT = 7


class NodeKind(Enum):
    """Kind of graph node."""

    MARKDOWN = "markdown"
    DATA = "data"
    DIRECTORY = "directory"
    EXCALIDRAW = "excalidraw"
    ASSET = "asset"
    PAGE = "page"


class ConnectionKind(Enum):
    """Kind of resolved relation between nodes."""

    CONTAINMENT = "containment"
    LINK = "link"
    EMBED = "embed"
    ASSET_REF = "asset_ref"
    TEMPLATE = "template"
    DATA_REF = "data_ref"
    COLLECTION = "collection"
    GENERATED_FROM = "generated_from"


@dataclass(slots=True, frozen=True)
class SourceSpan:
    """Half-inclusive source location for a parsed construct."""

    start_line: int
    start_col: int
    end_line: int
    end_col: int
