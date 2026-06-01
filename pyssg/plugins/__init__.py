"""Built-in plugins.

Each plugin is a single module ``pyssg/plugins/<name>.py``. This package
re-exports the factory functions so a config can do
``from pyssg.plugins import markdown, frontmatter, ...`` and call them.
"""

from __future__ import annotations

from pyssg.plugins.asset_copy import asset_copy
from pyssg.plugins.collections import (
    CollectionItem,
    CollectionSpec,
    Pagination,
    collections,
)
from pyssg.plugins.content_meta import content_meta
from pyssg.plugins.directory_loader import directory_loader
from pyssg.plugins.frontmatter import frontmatter
from pyssg.plugins.highlight import highlight
from pyssg.plugins.link_resolver import link_resolver
from pyssg.plugins.markdown import markdown
from pyssg.plugins.mermaid import mermaid
from pyssg.plugins.nav import nav
from pyssg.plugins.permalink import permalink
from pyssg.plugins.render import render
from pyssg.plugins.rss import rss
from pyssg.plugins.sitemap import sitemap
from pyssg.plugins.taxonomy import taxonomy
from pyssg.plugins.transclude import transclude
from pyssg.plugins.wikilink import wikilink

__all__ = [
    "CollectionItem",
    "CollectionSpec",
    "Pagination",
    "asset_copy",
    "collections",
    "content_meta",
    "directory_loader",
    "frontmatter",
    "highlight",
    "link_resolver",
    "markdown",
    "mermaid",
    "nav",
    "permalink",
    "render",
    "rss",
    "sitemap",
    "taxonomy",
    "transclude",
    "wikilink",
]
