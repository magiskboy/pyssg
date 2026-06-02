"""Shared CLI helpers: builder construction, cache, one-shot build."""

from __future__ import annotations

import asyncio
import warnings
from pathlib import Path

from pyssg.config import Config, load_config
from pyssg.core.build import BuildStats
from pyssg.core.builder import Builder
from pyssg.core.incremental.cache import Cache, FsCache, MemoryCache
from pyssg.core.phases import full_build
from pyssg.core.types import Phase
from pyssg.layout import Layout, load_layout

CACHE_DIRNAME = ".pyssg-cache"


def build_stats_payload(stats: BuildStats) -> dict[str, object]:
    """Machine-readable summary of a build, for ``--json`` consumers.

    A pure function of ``stats``: it derives the page count, cache-hit count and
    per-phase touch counts, so the same build always yields the same payload.
    The shape is the stable contract integrations (e.g. the Obsidian adapter)
    parse instead of scraping human-readable log lines.
    """
    phases = {
        phase.name.lower(): count
        for phase in Phase
        if (count := stats.touched_per_phase.get(phase))
    }
    return {
        "pages": len(stats.changed_outputs),
        "cache_hits": stats.cache_hits,
        "phases": phases,
    }


def _warn_unknown_theme_options(config: Config, layout: Layout | None) -> None:
    """Warn (non-fatally) about ``Config.theme`` keys the active theme ignores.

    The theme configuration API resolves options as ``layout defaults <-
    Config.theme``; a site may set any key and it is still passed to templates.
    But a key the theme's ``layout.toml`` ``[options]`` does not declare is most
    often a typo, so it is surfaced here as a warning rather than silently doing
    nothing. The values are still forwarded -- themes are allowed to read
    freeform extras -- so this never blocks a build.
    """
    if not config.theme:
        return
    declared = set(layout.options) if layout is not None else set()
    unknown = sorted(key for key in config.theme if key not in declared)
    if not unknown:
        return
    where = "the layout's [options]" if layout is not None else "any layout (none is configured)"
    warnings.warn(
        f"Config.theme sets option(s) not declared by {where}: "
        f"{', '.join(unknown)}. They are still passed to templates as `theme.*`; "
        "check for typos against the theme's layout.toml.",
        stacklevel=2,
    )


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
    _warn_unknown_theme_options(config, builder.layout)
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
