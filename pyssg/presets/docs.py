"""``docs`` preset: a ready-to-use documentation site.

A preset is a pure factory that returns a fully populated :class:`~pyssg.Config`,
bundling the right set of built-in plugins in the right apply order plus a
default theme. The basic user writes a one-line ``pyssg.config.py`` and never has
to know which plugins exist or how they must be ordered::

    from pyssg.presets import docs
    config = docs(site={"title": "My Docs"}, base_url="https://example.com")

The preset only *declares facts* (the plugin list and the theme); the engine
still owns every algorithm. Advanced users can build a :class:`Config` by hand
instead, or pass ``extra_plugins`` to append their own without losing the
defaults.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pyssg.config import Config
from pyssg.plugins import (
    asset_copy,
    content_meta,
    directory_loader,
    frontmatter,
    highlight,
    link_resolver,
    markdown,
    mermaid,
    nav,
    permalink,
    render,
    rss,
    sitemap,
    taxonomy,
    transclude,
    wikilink,
)
from pyssg.presets._common import site_title
from pyssg.themes import theme_path

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path

    from pyssg.plugins.api import Plugin


def docs(
    *,
    site: dict[str, object] | None = None,
    base_url: str = "",
    content_dir: str = "content",
    output_dir: str = "dist",
    layout: str | Path | None = None,
    highlight_style: str = "default",
    rss_title: str | None = None,
    extra_plugins: Iterable[Plugin] | None = None,
) -> Config:
    """Build a :class:`Config` for a documentation site.

    ``layout`` defaults to the built-in ``docs`` theme; pass a path to override
    it with a site-local layout. ``extra_plugins`` are appended after the
    defaults (so they run last). ``rss_title`` defaults to the site title.
    """
    plugins: list[Plugin] = [
        directory_loader(),
        frontmatter(),
        markdown(),
        mermaid(),
        highlight(style=highlight_style),
        content_meta(),
        permalink(),
        wikilink(),
        link_resolver(),
        transclude(),
        nav(),
        taxonomy(),
        sitemap(),
        rss(title=rss_title if rss_title is not None else site_title(site)),
        asset_copy(),
        render(),
    ]
    if extra_plugins is not None:
        plugins.extend(extra_plugins)

    return Config(
        content_dir=content_dir,
        output_dir=output_dir,
        layout=layout if layout is not None else theme_path("docs"),
        base_url=base_url,
        plugins=plugins,
        site=dict(site) if site is not None else {},
    )
