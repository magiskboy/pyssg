"""Rss plugin: generate an RSS 2.0 feed from a collection.

Taps ``generate`` and appends one ``Output``. Standard library only.

It reads ``build.meta["collections"][collection]`` (built by the Collections
plugin), so a feed is just "the newest N pages of a collection as XML". Channel
metadata comes from ``site`` options; item links use ``site["base_url"]``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from email.utils import format_datetime
from pathlib import Path
from xml.sax.saxutils import escape

from pyssg.build import Build
from pyssg.builder import Builder
from pyssg.content import URL, absolute_url, collections, site
from pyssg.models import Output, Source
from pyssg.schema import FieldSpec

# Rss reads collections (built in collect) and runs in generate.
_GENERATE_STAGE = 100


class Rss:
    def __init__(
        self,
        *,
        collection: str,
        path: str = "feed.xml",
        title: str | None = None,
        description: str | None = None,
        limit: int = 20,
    ) -> None:
        self._collection = collection
        self._path = path
        self._title = title
        self._description = description
        self._limit = limit

    def apply(self, builder: Builder) -> None:
        builder.schema.declare(FieldSpec("date", type="date", example="2026-01-31"))
        builder.hooks.generate.tap("Rss", self._generate, stage=_GENERATE_STAGE)

    def _generate(self, build: Build) -> None:
        collection = collections(build).get(self._collection)
        if collection is None:
            return

        options = site(build)
        base_url = str(options.get("base_url", ""))
        channel_title = self._title or str(options.get("title", self._collection))
        channel_desc = self._description or str(options.get("tagline", channel_title))
        channel_link = base_url or "/"

        items = "\n".join(
            _item(page, base_url) for page in collection.pages[: self._limit]
        )
        document = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<rss version="2.0">\n'
            "  <channel>\n"
            f"    <title>{escape(channel_title)}</title>\n"
            f"    <link>{escape(channel_link)}</link>\n"
            f"    <description>{escape(channel_desc)}</description>\n"
            + items
            + "\n  </channel>\n</rss>\n"
        )
        build.outputs.append(Output(path=Path(self._path), content=document))


def _item(page: Source, base_url: str) -> str:
    title = str(page.frontmatter.get("title", page.relpath.stem))
    link = absolute_url(base_url, str(page.meta.get(URL, "")))
    parts = [
        f"      <title>{escape(title)}</title>",
        f"      <link>{escape(link)}</link>",
        f"      <guid>{escape(link)}</guid>",
    ]
    pub_date = _rfc822(page.frontmatter.get("date"))
    if pub_date:
        parts.append(f"      <pubDate>{pub_date}</pubDate>")
    description = page.frontmatter.get("description") or page.frontmatter.get("summary")
    if isinstance(description, str) and description:
        parts.append(f"      <description>{escape(description)}</description>")
    return "    <item>\n" + "\n".join(parts) + "\n    </item>"


def _rfc822(value: object) -> str:
    if not isinstance(value, str) or not value:
        return ""
    text = value.split("T", 1)[0]
    try:
        parsed = datetime.strptime(text, "%Y-%m-%d").replace(tzinfo=UTC)
    except ValueError:
        return ""
    return format_datetime(parsed)
