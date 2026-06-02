"""``obsidian`` preset: publish an Obsidian vault as a site.

A pure factory that returns a :class:`~pyssg.Config` wired for an Obsidian vault:
the PKM Markdown pipeline (wikilinks, embeds, tags), vault-noise excludes,
attachment handling and selective publishing, plus a default theme. The basic
user writes a one-line ``pyssg.config.py``::

    from pyssg.presets import obsidian
    config = obsidian(site={"title": "My Garden"})

Unlike :func:`pyssg.presets.docs` / :func:`pyssg.presets.blog`, the Obsidian
support lives in :mod:`pyssg.contrib.obsidian` (a peripheral adapter); this preset
only composes that pipeline with a theme, so it still merely *declares facts*.

Publishing is a **denylist** by default (``publish_required=False``): every note
is rendered unless its frontmatter sets ``publish: false``, which suits a
whole-vault wiki. Pass ``publish_required=True`` for an allowlist, where a note is
rendered only when it sets ``publish: true``.

Hugo-style ``_index.md`` section pages are routed to their directory root by
default (``section_index=True``), so a migrated vault gets section landing pages
without explicit permalinks.

Vault layout note: when the vault root itself is the content directory
(``content_dir="."``), add the output directory to ``exclude`` (e.g.
``exclude=["dist"]``) so the build does not re-ingest its own output.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pyssg.config import Config
from pyssg.contrib.obsidian import obsidian_plugins
from pyssg.presets._common import site_title
from pyssg.themes import theme_path

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence
    from pathlib import Path

    from pyssg.plugins.api import Plugin


def obsidian(
    *,
    site: dict[str, object] | None = None,
    base_url: str = "",
    content_dir: str = "content",
    output_dir: str = "dist",
    layout: str | Path | None = None,
    include: Sequence[str] | None = None,
    exclude: Sequence[str] | None = None,
    publish_required: bool = False,
    publish_key: str = "publish",
    section_index: bool = True,
    highlight_style: str = "default",
    rss_title: str | None = None,
    extra_plugins: Iterable[Plugin] | None = None,
) -> Config:
    """Build a :class:`Config` for an Obsidian vault.

    ``layout`` defaults to the built-in ``docs`` theme. ``include`` / ``exclude``
    are content-relative glob filters (the vault-noise defaults from
    :data:`~pyssg.contrib.obsidian.DEFAULT_VAULT_EXCLUDE` are always applied on top
    of ``exclude``). ``publish_required`` toggles allowlist vs denylist publishing
    (default denylist). ``section_index`` routes ``_index.md`` to its directory
    root. ``extra_plugins`` are appended after the defaults. ``rss_title`` defaults
    to the site title.
    """
    plugins = obsidian_plugins(
        include=include,
        exclude=exclude,
        publish_required=publish_required,
        publish_key=publish_key,
        section_index=section_index,
        highlight_style=highlight_style,
        rss_title=rss_title if rss_title is not None else site_title(site),
    )
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
