"""RSS plugin.

During ``evaluate_collections`` it collects every *document* page and emits a
single virtual page at ``/feed.xml`` holding an RSS 2.0 ``<channel>``. Each
``<item>`` carries the document's title, its absolute link and a description
taken from the document's ``excerpt`` meta (empty when absent).

Ordering is deterministic: when documents declare a frontmatter ``date`` items
sort newest-first (then by url to break ties), otherwise by url; the feed is
capped to the 20 most recent items. As with the sitemap this is a
summarizer over the whole document set, and it reads only declared inputs (no
clock), so builds stay byte-identical.
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

_PAGE_ID = "page:rss"
_PAGE_URL = "/feed.xml"
_MAX_ITEMS = 20


class _Item:
    """One feed entry plus the sort keys used to order the channel."""

    __slots__ = ("date_key", "description", "link", "title", "url")

    def __init__(self, *, title: str, link: str, url: str, description: str, date_key: str) -> None:
        self.title = title
        self.link = link
        self.url = url
        self.description = description
        self.date_key = date_key


def _date_key(date: object) -> str:
    """Normalize a frontmatter ``date`` to a sortable ``YYYY-MM-DD`` string.

    Returns ``""`` when no usable date is present, which sorts before any real
    date and -- because the channel is then reversed -- lands such items last.
    """
    if isinstance(date, dt.date):
        return date.isoformat()[:10]
    if isinstance(date, str):
        return date
    return ""


def _items(build: Build) -> list[_Item]:
    """Collect feed items for every document page, ordered and capped."""
    config = build.builder.config
    base_url = config.base_url if config is not None else ""

    items: list[_Item] = []
    has_dates = False
    for node in build.graph.nodes():
        if not (isinstance(node, Page) and node.generated_from):
            continue
        doc = build.graph.get(node.generated_from[0])
        if not isinstance(doc, Document):
            continue
        date_key = _date_key(doc.meta.get("date"))
        if date_key:
            has_dates = True
        title = str(doc.meta.get("title") or node.url)
        excerpt = doc.meta.get("excerpt")
        items.append(
            _Item(
                title=title,
                link=f"{base_url}{node.url}",
                url=node.url,
                description=str(excerpt) if isinstance(excerpt, str) else "",
                date_key=date_key,
            )
        )

    if has_dates:
        # Newest first; url is a stable tie-breaker. Sorting by (date, url)
        # ascending then reversing keeps url ascending only within equal dates.
        items.sort(key=lambda it: (it.date_key, it.url))
        items.reverse()
    else:
        items.sort(key=lambda it: it.url)
    return items[:_MAX_ITEMS]


def render_rss_xml(*, title: str, link: str, items: list[_Item]) -> str:
    """Build the RSS 2.0 channel XML from a channel title/link and items."""
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0">',
        "  <channel>",
        f"    <title>{escape(title)}</title>",
        f"    <link>{escape(link)}</link>",
    ]
    for item in items:
        lines.append("    <item>")
        lines.append(f"      <title>{escape(item.title)}</title>")
        lines.append(f"      <link>{escape(item.link)}</link>")
        lines.append(f"      <description>{escape(item.description)}</description>")
        lines.append("    </item>")
    lines.append("  </channel>")
    lines.append("</rss>")
    return "\n".join(lines) + "\n"


def build_rss(build: Build, title: str | None = None) -> None:
    """Create or update the virtual ``/feed.xml`` page in place."""
    config = build.builder.config
    site = config.site if config is not None else {}
    base_url = config.base_url if config is not None else ""

    channel_title = title
    if channel_title is None:
        site_title = site.get("title")
        channel_title = str(site_title) if isinstance(site_title, str) else ""

    xml = render_rss_xml(title=channel_title, link=base_url, items=_items(build))
    meta: dict[str, object] = {"title": "RSS", "content_html": xml}

    existing = build.graph.get(_PAGE_ID)
    if isinstance(existing, Page):
        existing.url = _PAGE_URL
        existing.template = None
        existing.meta = meta
    else:
        build.graph.add_node(
            Page(id=_PAGE_ID, kind=NodeKind.PAGE, url=_PAGE_URL, template=None, meta=meta)
        )


class RssPlugin:
    """Built-in RSS 2.0 feed generator."""

    name = "rss"
    cache_version = "1.0.0"

    def __init__(self, title: str | None = None) -> None:
        self._title = title

    def apply(self, builder: Builder) -> None:
        @builder.hooks.this_compilation.tap(self.name)
        def _wire(build: Build) -> None:
            @build.hooks.evaluate_collections.tap(self.name, after=("nav", "taxonomy"))
            def _eval(b: Build) -> None:
                build_rss(b, self._title)


def rss(title: str | None = None) -> RssPlugin:
    """Factory used in ``pyssg.config.py``."""
    return RssPlugin(title)
