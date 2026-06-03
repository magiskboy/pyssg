"""RSS plugin.

During ``evaluate_collections`` it collects every *document* page and emits an
RSS 2.0 ``<channel>``. Each ``<item>`` carries the document's title, its absolute
link, a ``<guid>`` (the same permalink, marked ``isPermaLink``), an optional
``<pubDate>`` derived from the frontmatter ``date`` and a description taken from
the document's ``excerpt`` meta (empty when absent).

When the i18n plugin is loaded the feed is partitioned per locale: the default
locale is served at ``/feed.xml`` and every other locale at ``/<locale>/feed.xml``,
so a feed never mixes languages. The split is read from each document's
``meta["lang"]`` and from the page URLs themselves (see
:func:`~pyssg.plugins._context.locale_root`), so it needs no ordering against the
i18n pass. A site without i18n has a single ``/feed.xml`` exactly as before.

Ordering is deterministic: when documents declare a frontmatter ``date`` items
sort newest-first (then by url to break ties), otherwise by url; each feed is
capped to the 20 most recent items. As with the sitemap this is a summarizer over
the document set, and ``<pubDate>`` is derived purely from the declared ``date``
(midnight UTC, never a clock), so builds stay byte-identical.

The algorithm lives in :class:`RssPlugin` methods so a site can subclass it to
change the feed URL scheme, the channel title or the per-item markup without
forking the plugin (see ``AGENTS.md`` on plugin design).
"""

from __future__ import annotations

import datetime as dt
from email.utils import format_datetime
from typing import TYPE_CHECKING
from xml.sax.saxutils import escape, quoteattr

from pyssg.core.node import Document, Page
from pyssg.core.types import NodeKind
from pyssg.plugins._context import doc_locale, locale_root

if TYPE_CHECKING:
    from pyssg.core.build import Build
    from pyssg.core.builder import Builder

_PAGE_ID = "page:rss"
_PAGE_URL = "/feed.xml"
_MAX_ITEMS = 20


class _Item:
    """One feed entry plus the sort keys used to order the channel."""

    __slots__ = ("date_key", "description", "link", "pubdate", "title", "url")

    def __init__(
        self,
        *,
        title: str,
        link: str,
        url: str,
        description: str,
        date_key: str,
        pubdate: str = "",
    ) -> None:
        self.title = title
        self.link = link
        self.url = url
        self.description = description
        self.date_key = date_key
        self.pubdate = pubdate


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


def _pubdate(date: object) -> str:
    """Render a frontmatter ``date`` as an RFC-822 ``<pubDate>`` value.

    A bare date is anchored at midnight UTC so the output is deterministic and
    never reads a clock; a naive ``datetime`` is likewise treated as UTC. Returns
    ``""`` when no parseable date is present, in which case ``<pubDate>`` is
    omitted from the item.
    """
    moment: dt.datetime | None = None
    if isinstance(date, dt.datetime):
        moment = date
    elif isinstance(date, dt.date):
        moment = dt.datetime(date.year, date.month, date.day, tzinfo=dt.UTC)
    elif isinstance(date, str):
        try:
            parsed = dt.date.fromisoformat(date[:10])
        except ValueError:
            return ""
        moment = dt.datetime(parsed.year, parsed.month, parsed.day, tzinfo=dt.UTC)
    if moment is None:
        return ""
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=dt.UTC)
    return format_datetime(moment)


def render_rss_xml(*, title: str, link: str, items: list[_Item]) -> str:
    """Build the RSS 2.0 channel XML from a channel title/link and items.

    Each item emits ``<title>``, ``<link>``, ``<guid isPermaLink="true">`` (the
    same permalink) and ``<description>``; ``<pubDate>`` is included only when the
    item carries one.
    """
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
        lines.append(f"      <guid isPermaLink={quoteattr('true')}>{escape(item.link)}</guid>")
        if item.pubdate:
            lines.append(f"      <pubDate>{escape(item.pubdate)}</pubDate>")
        lines.append(f"      <description>{escape(item.description)}</description>")
        lines.append("    </item>")
    lines.append("  </channel>")
    lines.append("</rss>")
    return "\n".join(lines) + "\n"


class RssPlugin:
    """Built-in RSS 2.0 feed generator, one feed per locale.

    Customise by subclassing: override :meth:`make_item` for the per-item markup,
    :meth:`feed_url` for the URL scheme, or :meth:`channel_title` for the channel
    title, while reusing the locale partitioning and emit wiring.
    """

    name = "rss"
    # Bumped from 1.0.0: items now carry guid/pubDate and feeds split per locale.
    cache_version = "1.1.0"
    #: Maximum number of items per feed.
    max_items = _MAX_ITEMS

    def __init__(self, title: str | None = None) -> None:
        self._title = title

    def apply(self, builder: Builder) -> None:
        @builder.hooks.this_compilation.tap(self.name)
        def _wire(build: Build) -> None:
            @build.hooks.evaluate_collections.tap(self.name, after=("nav", "taxonomy"))
            def _eval(b: Build) -> None:
                self.build(b)

    def channel_title(self, build: Build) -> str:
        """Feed ``<title>``: the factory title, else the site title, else ``""``."""
        if self._title is not None:
            return self._title
        config = build.builder.config
        site = config.site if config is not None else {}
        site_title = site.get("title")
        return str(site_title) if isinstance(site_title, str) else ""

    def feed_url(self, locale: str, root: str) -> str:
        """URL of a locale's feed: ``/feed.xml`` at the root, else ``<root>feed.xml``."""
        return f"{root}feed.xml"

    def feed_id(self, locale: str, root: str) -> str:
        """Stable node id for a locale's feed page.

        The root feed keeps the bare ``page:rss`` id (so a single-locale site is
        unchanged); other locales are namespaced by locale code.
        """
        return _PAGE_ID if root == "/" else f"{_PAGE_ID}:{locale}"

    def make_item(self, doc: Document, page: Page, base_url: str) -> _Item:
        """Build one feed item from a document and its routed page."""
        title = str(doc.meta.get("title") or page.url)
        excerpt = doc.meta.get("excerpt")
        return _Item(
            title=title,
            link=f"{base_url}{page.url}",
            url=page.url,
            description=str(excerpt) if isinstance(excerpt, str) else "",
            date_key=_date_key(doc.meta.get("date")),
            pubdate=_pubdate(doc.meta.get("date")),
        )

    def _order(self, items: list[_Item]) -> list[_Item]:
        if any(it.date_key for it in items):
            # Newest first; url is a stable tie-breaker. Sort ascending by
            # (date, url) then reverse so url stays ascending within equal dates.
            items.sort(key=lambda it: (it.date_key, it.url))
            items.reverse()
        else:
            items.sort(key=lambda it: it.url)
        return items[: self.max_items]

    def build(self, build: Build) -> None:
        """Group document pages by locale and (re)materialize one feed per locale."""
        config = build.builder.config
        base_url = config.base_url if config is not None else ""
        title = self.channel_title(build)

        # locale -> (items, representative member URL for root detection).
        per_locale: dict[str, list[_Item]] = {}
        sample_url: dict[str, str] = {}
        for node in build.graph.nodes():
            if not (isinstance(node, Page) and node.generated_from):
                continue
            doc = build.graph.get(node.generated_from[0])
            if not isinstance(doc, Document):
                continue
            locale = doc_locale(doc)
            per_locale.setdefault(locale, []).append(self.make_item(doc, node, base_url))
            sample_url.setdefault(locale, node.url)

        owned: set[str] = set()
        for locale, items in per_locale.items():
            root = locale_root(locale, sample_url[locale])
            pid = self.feed_id(locale, root)
            xml = render_rss_xml(title=title, link=base_url, items=self._order(items))
            _set_feed_page(build, pid, self.feed_url(locale, root), xml)
            owned.add(pid)

        # Drop feed pages from a previous evaluation (e.g. a locale that lost all
        # its documents) so the finalize page-set diff deletes their stale output.
        for node in list(build.graph.nodes()):
            if (node.id == _PAGE_ID or node.id.startswith(f"{_PAGE_ID}:")) and node.id not in owned:
                build.graph.remove(node.id)


def _set_feed_page(build: Build, pid: str, url: str, xml: str) -> None:
    meta: dict[str, object] = {"title": "RSS", "content_html": xml}
    existing = build.graph.get(pid)
    if isinstance(existing, Page):
        existing.url = url
        existing.template = None
        existing.meta = meta
    else:
        build.graph.add_node(Page(id=pid, kind=NodeKind.PAGE, url=url, template=None, meta=meta))


def build_rss(build: Build, title: str | None = None) -> None:
    """Materialize the RSS feed(s). Thin wrapper around :meth:`RssPlugin.build`."""
    RssPlugin(title).build(build)


def rss(title: str | None = None) -> RssPlugin:
    """Factory used in ``pyssg.config.py``."""
    return RssPlugin(title)
