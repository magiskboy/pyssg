"""``blog`` preset: a ready-to-use blog.

Like the :mod:`pyssg.presets.docs` preset, this returns a fully populated
:class:`~pyssg.Config` so the basic user writes a one-line ``pyssg.config.py``::

    from pyssg.presets import blog
    config = blog(site={"title": "My Blog"}, base_url="https://example.com")

Convention: posts live under ``content/posts/``. They are collected into a
``posts`` collection, sorted newest-first by their ``date`` frontmatter, and
paginated; page 1 is the site home (``/``) and page N is ``/page/N/``. Override
``posts_route``/``posts_per_page`` to taste, or pass ``extra_plugins`` to append
your own plugins without losing the defaults.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pyssg.config import Config
from pyssg.plugins import (
    CollectionSpec,
    Pagination,
    asset_copy,
    collections,
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


def blog(
    *,
    site: dict[str, object] | None = None,
    base_url: str = "",
    content_dir: str = "content",
    output_dir: str = "dist",
    layout: str | Path | None = None,
    posts_dir: str = "posts",
    posts_route: str = "/",
    posts_per_page: int = 5,
    highlight_style: str = "default",
    rss_title: str | None = None,
    extra_plugins: Iterable[Plugin] | None = None,
    deploy: dict[str, dict[str, object]] | None = None,
) -> Config:
    """Build a :class:`Config` for a blog.

    Posts are documents under ``content/<posts_dir>/``; they are collected,
    sorted newest-first by ``date``, and paginated at ``posts_route`` with
    ``posts_per_page`` per page. ``layout`` defaults to the built-in ``blog``
    theme. ``deploy`` is forwarded verbatim to :attr:`Config.deploy` for the
    ``pyssg deploy`` subcommand.
    """
    posts = CollectionSpec(
        name="posts",
        select=lambda item: item.section == posts_dir,
        sort_key=lambda item: item.date,
        reverse=True,  # newest first
        pagination=Pagination(size=posts_per_page, route=posts_route, template="list.html.j2"),
        title=site_title(site) or "Posts",
    )

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
        collections(posts),
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
        layout=layout if layout is not None else theme_path("blog"),
        base_url=base_url,
        plugins=plugins,
        site=dict(site) if site is not None else {},
        deploy=dict(deploy) if deploy is not None else {},
    )
