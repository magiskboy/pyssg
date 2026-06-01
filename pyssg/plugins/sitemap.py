"""Sitemap plugin.

During ``evaluate_collections`` it scans every *document* page in the graph and
materializes a single virtual page at ``/sitemap.xml`` whose body is a
``urlset`` listing each page's absolute URL (``base_url`` + page url) and an
optional ``<lastmod>`` derived from the document's frontmatter ``date``.

This is the "summarizer fan-in" feature: the output depends on the whole
set of document pages. Recomputation is deterministic (URLs sorted) and reads
only declared inputs (no clock), so two builds are byte-identical and an
incremental rebuild reuses cached output whenever the projection is unchanged.
"""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING
from xml.sax.saxutils import escape

from pyssg.core.node import Document, Page
from pyssg.core.types import NodeKind

if TYPE_CHECKING:
    from pyssg.core.build import Build
    from pyssg.core.builder import Builder

_PAGE_ID = "page:sitemap"
_PAGE_URL = "/sitemap.xml"


def _lastmod(date: object) -> str | None:
    """Format a frontmatter ``date`` as ``YYYY-MM-DD`` for ``<lastmod>``.

    ``datetime``/``date`` are rendered via ISO format; an opaque string is
    passed through verbatim (the user owns its shape); anything else is omitted
    rather than guessed.
    """
    # ``datetime`` is a subclass of ``date``; ``isoformat()[:10]`` yields the
    # date portion for both, so a single branch covers them.
    if isinstance(date, dt.date):
        return date.isoformat()[:10]
    if isinstance(date, str):
        return date
    return None


def _document_urls(build: Build) -> list[tuple[str, str | None]]:
    """Collect ``(absolute_url, lastmod)`` for every document page, url-sorted.

    Virtual pages (tags index, the sitemap/rss pages themselves) carry no
    ``generated_from`` provenance and are skipped, so only real documents enter
    the sitemap.
    """
    config = build.builder.config
    base_url = config.base_url if config is not None else ""

    entries: list[tuple[str, str | None]] = []
    for node in build.graph.nodes():
        if not (isinstance(node, Page) and node.generated_from):
            continue
        doc = build.graph.get(node.generated_from[0])
        if not isinstance(doc, Document):
            continue
        absolute = f"{base_url}{node.url}"
        entries.append((absolute, _lastmod(doc.meta.get("date"))))
    entries.sort(key=lambda e: e[0])
    return entries


def render_sitemap_xml(entries: list[tuple[str, str | None]]) -> str:
    """Build the ``urlset`` XML body from ``(url, lastmod)`` entries."""
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for url, lastmod in entries:
        lines.append("  <url>")
        lines.append(f"    <loc>{escape(url)}</loc>")
        if lastmod is not None:
            lines.append(f"    <lastmod>{escape(lastmod)}</lastmod>")
        lines.append("  </url>")
    lines.append("</urlset>")
    return "\n".join(lines) + "\n"


def build_sitemap(build: Build) -> None:
    """Create or update the virtual ``/sitemap.xml`` page in place."""
    xml = render_sitemap_xml(_document_urls(build))
    meta: dict[str, object] = {"title": "Sitemap", "content_html": xml}

    existing = build.graph.get(_PAGE_ID)
    if isinstance(existing, Page):
        existing.url = _PAGE_URL
        existing.template = None
        existing.meta = meta
    else:
        build.graph.add_node(
            Page(id=_PAGE_ID, kind=NodeKind.PAGE, url=_PAGE_URL, template=None, meta=meta)
        )


class SitemapPlugin:
    """Built-in sitemap.xml generator."""

    name = "sitemap"
    cache_version = "1.0.0"

    def apply(self, builder: Builder) -> None:
        @builder.hooks.this_compilation.tap(self.name)
        def _wire(build: Build) -> None:
            # Run after nav/taxonomy so any virtual document pages they add are
            # already present; we still skip non-document pages by provenance.
            @build.hooks.evaluate_collections.tap(self.name, after=("nav", "taxonomy"))
            def _eval(b: Build) -> None:
                build_sitemap(b)


def sitemap() -> SitemapPlugin:
    """Factory used in ``pyssg.config.py``."""
    return SitemapPlugin()
