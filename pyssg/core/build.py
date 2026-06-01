"""Per-build scope: ``Build`` (Compilation) and its hooks.

A ``Build`` is created fresh for each (re)build and owns the graph and nodes of
that build. Long-lived state (cache, registries) lives on the ``Builder`` and is
reached through ``self.builder`` so the cache survives across a watch session.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import TYPE_CHECKING

from pyssg.core.dependency import Connection, Dependency
from pyssg.core.graph import DependencyGraph
from pyssg.core.hook import AsyncSeriesHook, BailHook, SyncHook, WaterfallHook
from pyssg.core.incremental.cache import Cache
from pyssg.core.incremental.hashing import digest
from pyssg.core.node import Node, Page
from pyssg.core.registry import Registry
from pyssg.core.types import Aspect, ConnectionKind, Digest, NodeId, Phase

if TYPE_CHECKING:
    from pyssg.core.builder import Builder


class AssetStage(IntEnum):
    """Numeric buckets for ``process_assets`` taps.

    Rule: minify before HASH; HASH before REPORT. Plugins declare only a stage;
    they never need to know about each other.
    """

    ADDITIONS = 100
    OPTIMIZE = 200
    OPTIMIZE_SIZE = 300
    HASH = 400
    DEV_TOOLING = 500
    REPORT = 900


@dataclass(slots=True)
class BuildStats:
    """Per-build counters; ``changed_outputs`` feeds live-reload."""

    touched_per_phase: dict[Phase, int] = field(default_factory=dict)
    cache_hits: int = 0
    changed_outputs: set[str] = field(default_factory=set)
    elapsed_ms: float = 0.0


@dataclass(slots=True)
class ResolveContext:
    """Context handed to resolvers.

    Minimal in M2; resolution helpers (``by_slug``, ``placeholder``, ...) are
    added with the resolver plugins in M3/M6.
    """

    build: Build
    origin: NodeId


@dataclass(slots=True)
class ParserSlot:
    """Tap points for one parser kind."""

    before_parse: SyncHook[Node] = field(default_factory=SyncHook)
    after_parse: SyncHook[Node] = field(default_factory=SyncHook)


@dataclass(slots=True)
class BuildHooks:
    """Hooks scoped to a single build."""

    load_node: BailHook[[str], Node] = field(default_factory=BailHook)
    parse: SyncHook[Node] = field(default_factory=SyncHook)
    resolve: BailHook[[Dependency, ResolveContext], Connection] = field(default_factory=BailHook)
    evaluate_collections: SyncHook[Build] = field(default_factory=SyncHook)
    # Per-document content rewrite chain run at finalize: (html, doc) -> html.
    # Tapped by wikilink / link_resolver to resolve references against the whole
    # graph once every document is parsed.
    finalize_content: WaterfallHook[str] = field(default_factory=WaterfallHook)
    # Whole-build content expansion run after finalize_content (transclusion,
    # which embeds other documents' finalized content).
    expand_content: SyncHook[Build] = field(default_factory=SyncHook)
    generate: SyncHook[Node] = field(default_factory=SyncHook)
    route: WaterfallHook[str] = field(default_factory=WaterfallHook)
    transform: WaterfallHook[object] = field(default_factory=WaterfallHook)
    render_page: WaterfallHook[str] = field(default_factory=WaterfallHook)
    process_assets: SyncHook[Node] = field(default_factory=SyncHook)
    emit: AsyncSeriesHook[Node] = field(default_factory=AsyncSeriesHook)
    after_emit: AsyncSeriesHook[Build] = field(default_factory=AsyncSeriesHook)


class Build:
    """The per-build compilation.

    For an incremental watch session this same object persists across rebuild
    passes, carrying the graph plus the bookkeeping the incremental
    engine needs: committed per-aspect hashes (for early-cutoff), the path->node
    map (for FS events), and which pages each document generated (page-set diff).
    """

    __slots__ = (
        "_emitted",
        "_generated_pages",
        "_known_pages",
        "_pages_of",
        "_path_to_id",
        "_prev_hashes",
        "builder",
        "graph",
        "hooks",
        "site_data",
        "stats",
    )

    def __init__(self, builder: Builder) -> None:
        self.builder = builder
        self.graph = DependencyGraph()
        self.hooks = BuildHooks()
        self.stats = BuildStats()
        # Per-rebuild scratch for site-wide derived data (nav menu, tag index,
        # ...) that the `evaluate_collections` hook fills and templates read.
        self.site_data: dict[str, object] = {}
        # Pages accumulated by `generate` taps (the hook is a SyncHook, so
        # generators publish pages by side effect rather than by return).
        self._generated_pages: list[Page] = []
        # Incremental bookkeeping (persists across passes within a session).
        self._prev_hashes: dict[NodeId, dict[Aspect, Digest]] = {}
        self._path_to_id: dict[str, NodeId] = {}
        self._pages_of: dict[NodeId, list[NodeId]] = {}
        self._emitted: dict[NodeId, str] = {}
        # All page ids whose output existed after the previous finalize, so the
        # next finalize can delete outputs for pages that have since vanished.
        self._known_pages: set[NodeId] = set()

    # Registries live on the long-lived Builder; expose them here so plugins can
    # write `build.parsers.for_(...)`.
    @property
    def loaders(self) -> Registry[str, BailHook[[str], Node]]:
        return self.builder.loaders

    @property
    def parsers(self) -> Registry[str, ParserSlot]:
        return self.builder.parsers

    @property
    def resolvers(
        self,
    ) -> Registry[str, BailHook[[Dependency, ResolveContext], Connection]]:
        return self.builder.resolvers

    @property
    def cache(self) -> Cache:
        return self.builder.cache

    @property
    def plugin_set_version(self) -> Digest:
        """Digest of the plugin set + their cache versions."""
        config = self.builder.config
        plugins = config.plugins if config is not None else []
        return digest([[p.name, p.cache_version] for p in plugins])

    def pipeline_version(self, phase: Phase) -> Digest:
        """Version of the code chain for ``phase``.

        Simplified in M4: the plugin set defines the pipeline, so bumping any
        plugin's ``cache_version`` busts the relevant cache entries.
        """
        return digest(phase.name, self.plugin_set_version)

    def relevant_config(self, phase: Phase) -> Digest:
        """Digest of the config keys that affect ``phase``."""
        config = self.builder.config
        if config is None or phase is not Phase.RENDER:
            return digest(phase.name)
        return digest(phase.name, config.base_url, config.site)

    def create_connection(
        self,
        *,
        src: NodeId,
        dst: NodeId | None,
        kind: ConnectionKind,
        dependency: Dependency,
        sensitive_to: frozenset[Aspect] = frozenset(),
        restart_phase: Phase = Phase.RENDER,
        reverse: bool = False,
    ) -> Connection:
        """Declare and register a resolved edge.

        This is the plugin's *declaration* point; the engine owns what the
        ``sensitive_to`` / ``restart_phase`` / ``reverse`` facts mean for
        invalidation.
        """
        conn = Connection(
            src=src,
            dst=dst,
            kind=kind,
            dependency=dependency,
            sensitive_to=sensitive_to,
            restart_phase=restart_phase,
            reverse=reverse,
        )
        self.graph.connect(conn)
        return conn

    def emit_page(self, page: Page) -> None:
        """Register a page produced by a generator."""
        self._generated_pages.append(page)

    def take_generated_pages(self) -> list[Page]:
        """Return and clear the pages accumulated since the last call."""
        pages = self._generated_pages
        self._generated_pages = []
        return pages

    # -- incremental bookkeeping ----------------------------------------------

    def prev_hashes(self, nid: NodeId) -> dict[Aspect, Digest]:
        """Per-aspect hashes committed by the previous stable build."""
        return self._prev_hashes.get(nid, {})

    def commit_hashes(self, nid: NodeId) -> None:
        """Snapshot a node's current hashes as the new baseline."""
        node = self.graph.get(nid)
        if node is not None:
            self._prev_hashes[nid] = dict(node.hashes)

    def forget_node(self, nid: NodeId) -> None:
        """Drop all incremental bookkeeping for a removed node."""
        self._prev_hashes.pop(nid, None)
        self._pages_of.pop(nid, None)
        self._emitted.pop(nid, None)

    def register_path(self, path: str, nid: NodeId) -> None:
        self._path_to_id[path] = nid

    def id_of_path(self, path: str) -> NodeId | None:
        return self._path_to_id.get(path)

    def forget_path(self, path: str) -> None:
        self._path_to_id.pop(path, None)

    def set_pages_of(self, did: NodeId, page_ids: list[NodeId]) -> None:
        self._pages_of[did] = page_ids

    def pages_of(self, did: NodeId) -> list[NodeId]:
        return self._pages_of.get(did, [])

    def record_emit(self, pid: NodeId, output_rel: str) -> None:
        self._emitted[pid] = output_rel

    def emitted_output(self, pid: NodeId) -> str | None:
        return self._emitted.get(pid)

    def known_pages(self) -> set[NodeId]:
        return self._known_pages

    def set_known_pages(self, pages: set[NodeId]) -> None:
        self._known_pages = pages
