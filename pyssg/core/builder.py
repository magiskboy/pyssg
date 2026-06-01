"""Long-lived build scope: ``Builder`` (Compiler) and its hooks.

The ``Builder`` is configured once (plugins apply here) and lives across a whole
watch session, holding the registries and -- from M4 -- the persistent cache.
Each (re)build instantiates a fresh ``Build`` that reaches back to this scope.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from pyssg.core.build import (
    AssetStage,
    Build,
    BuildStats,
    ParserSlot,
    ResolveContext,
)
from pyssg.core.dependency import Connection, Dependency
from pyssg.core.hook import AsyncSeriesHook, BailHook, SyncHook, WaterfallHook
from pyssg.core.incremental.cache import Cache, MemoryCache
from pyssg.core.node import Node
from pyssg.core.registry import Registry

if TYPE_CHECKING:
    from pyssg.config import Config
    from pyssg.layout import Layout
    from pyssg.plugins.api import Plugin

# Registry slot type aliases (provisional; refined as M3 wires real invocation).
type LoaderRegistry = Registry[str, BailHook[[str], Node]]
type ParserRegistry = Registry[str, ParserSlot]
type ResolverRegistry = Registry[str, BailHook[[Dependency, ResolveContext], Connection]]
type TransformRegistry = Registry[str, WaterfallHook[object]]
type GeneratorRegistry = Registry[str, SyncHook[Node]]
type OptimizerRegistry = Registry[AssetStage, SyncHook[Node]]


@dataclass(slots=True)
class BuilderHooks:
    """Hooks scoped to the long-lived builder."""

    initialize: SyncHook[[]] = field(default_factory=SyncHook)
    before_run: AsyncSeriesHook[[]] = field(default_factory=AsyncSeriesHook)
    this_compilation: SyncHook[Build] = field(default_factory=SyncHook)
    make: AsyncSeriesHook[Build] = field(default_factory=AsyncSeriesHook)
    after_emit: AsyncSeriesHook[Build] = field(default_factory=AsyncSeriesHook)
    done: SyncHook[BuildStats] = field(default_factory=SyncHook)
    failed: SyncHook[BaseException] = field(default_factory=SyncHook)
    watch_run: AsyncSeriesHook[object] = field(default_factory=AsyncSeriesHook)
    invalidate: SyncHook[list[str]] = field(default_factory=SyncHook)


class Builder:
    """The long-lived compiler."""

    __slots__ = (
        "cache",
        "config",
        "generators",
        "hooks",
        "layout",
        "loaders",
        "optimizers",
        "parsers",
        "resolvers",
        "site_dir",
        "transforms",
    )

    def __init__(
        self,
        config: Config | None = None,
        site_dir: Path | None = None,
        cache: Cache | None = None,
    ) -> None:
        # Site config + resolved layout package. Set before plugins apply so a
        # plugin can read them in `apply()` (e.g. render builds its Jinja env).
        self.config: Config | None = config
        self.layout: Layout | None = None
        # Absolute site root; content/output dirs in config are relative to it.
        self.site_dir: Path = site_dir if site_dir is not None else Path.cwd()
        # Persistent across the watch session, so rebuilds reuse cached work.
        self.cache: Cache = cache if cache is not None else MemoryCache()
        self.hooks = BuilderHooks()
        self.loaders: LoaderRegistry = Registry(lambda _key: BailHook())
        self.parsers: ParserRegistry = Registry(lambda _key: ParserSlot())
        self.resolvers: ResolverRegistry = Registry(lambda _key: BailHook())
        self.transforms: TransformRegistry = Registry(lambda _key: WaterfallHook())
        self.generators: GeneratorRegistry = Registry(lambda _key: SyncHook())
        self.optimizers: OptimizerRegistry = Registry(lambda _key: SyncHook())

    def use(self, plugin: Plugin) -> None:
        """Apply a plugin once at configuration time."""
        plugin.apply(self)

    def create_build(self) -> Build:
        """Start a fresh per-build compilation that reaches back to this scope."""
        return Build(self)
