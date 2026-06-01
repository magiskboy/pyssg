"""Shared CLI helpers: builder construction, cache, one-shot build."""

from __future__ import annotations

import asyncio
from pathlib import Path

from pyssg.config import load_config
from pyssg.core.build import BuildStats
from pyssg.core.builder import Builder
from pyssg.core.incremental.cache import Cache, FsCache, MemoryCache
from pyssg.core.phases import full_build
from pyssg.layout import load_layout

CACHE_DIRNAME = ".pyssg-cache"


def open_cache(site_dir: Path, no_cache: bool) -> Cache:
    """A persistent ``FsCache`` under the site, or an ephemeral ``MemoryCache``."""
    if no_cache:
        return MemoryCache()
    return FsCache(site_dir / CACHE_DIRNAME)


def make_builder(site_dir: Path, cache: Cache | None = None) -> Builder:
    """Configure a builder from the site's config + layout, apply plugins."""
    site_dir = site_dir.resolve()
    config = load_config(site_dir)
    builder = Builder(config=config, site_dir=site_dir, cache=cache)
    if config.layout is not None:
        # A str layout is relative to the site; an absolute Path (e.g. a built-in
        # theme from pyssg.themes) is used as-is.
        layout_path = config.layout if isinstance(config.layout, Path) else site_dir / config.layout
        builder.layout = load_layout(layout_path)
    for plugin in config.plugins:
        builder.use(plugin)
    builder.hooks.initialize.call()
    return builder


def build_site(site_dir: Path, cache: Cache | None = None) -> BuildStats:
    """Configure a builder and run one full build."""
    builder = make_builder(site_dir, cache)
    build = builder.create_build()
    builder.hooks.this_compilation.call(build)
    stats = asyncio.run(full_build(build))
    builder.hooks.done.call(stats)
    return stats
