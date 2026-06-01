"""Unit tests for the rss plugin."""

from __future__ import annotations

import datetime as dt
import unittest

from pyssg.config import Config
from pyssg.core.build import Build
from pyssg.core.builder import Builder
from pyssg.core.node import Document, Page
from pyssg.core.types import NodeKind
from pyssg.plugins.rss import (
    _MAX_ITEMS,
    _PAGE_ID,
    _PAGE_URL,
    _Item,
    build_rss,
    render_rss_xml,
)


def _add_doc_page(build: Build, doc_id: str, url: str, meta: dict[str, object]) -> None:
    build.graph.add_node(Document(id=doc_id, kind=NodeKind.MARKDOWN, meta=meta))
    build.graph.add_node(
        Page(
            id=f"page:{doc_id}",
            kind=NodeKind.PAGE,
            url=url,
            generated_from=[doc_id],
        )
    )


def _build(base_url: str = "https://example.com", site: dict[str, object] | None = None) -> Build:
    builder = Builder(config=Config(base_url=base_url, site=site or {}))
    return builder.create_build()


class RssTest(unittest.TestCase):
    def test_render_rss_xml_basic_shape(self) -> None:
        item = _Item(
            title="Hello",
            link="https://example.com/p/",
            url="/p/",
            description="An intro",
            date_key="2024-01-01",
        )
        xml = render_rss_xml(title="Site", link="https://example.com", items=[item])
        self.assertIn('<rss version="2.0">', xml)
        self.assertIn("<title>Site</title>", xml)
        self.assertIn("<link>https://example.com</link>", xml)
        self.assertIn("<title>Hello</title>", xml)
        self.assertIn("<link>https://example.com/p/</link>", xml)
        self.assertIn("<description>An intro</description>", xml)

    def test_build_rss_emits_virtual_page_with_site_title(self) -> None:
        build = _build(site={"title": "My Site"})
        _add_doc_page(build, "a", "/a/", {"title": "A", "excerpt": "first"})
        build_rss(build)

        page = build.graph.get(_PAGE_ID)
        self.assertIsInstance(page, Page)
        self.assertEqual(page.url, _PAGE_URL)  # type: ignore[union-attr]
        self.assertIsNone(page.template)  # type: ignore[union-attr]
        xml = str(page.meta["content_html"])  # type: ignore[union-attr]
        self.assertIn("<title>My Site</title>", xml)
        self.assertIn("<link>https://example.com/a/</link>", xml)
        self.assertIn("<description>first</description>", xml)

    def test_build_rss_factory_title_overrides_site_title(self) -> None:
        build = _build(site={"title": "Site Title"})
        _add_doc_page(build, "a", "/a/", {"title": "A"})
        build_rss(build, "Override")

        xml = str(build.graph.get(_PAGE_ID).meta["content_html"])  # type: ignore[union-attr]
        self.assertIn("<title>Override</title>", xml)

    def test_build_rss_empty_description_when_no_excerpt(self) -> None:
        build = _build()
        _add_doc_page(build, "a", "/a/", {"title": "A"})
        build_rss(build)

        xml = str(build.graph.get(_PAGE_ID).meta["content_html"])  # type: ignore[union-attr]
        self.assertIn("<description></description>", xml)

    def test_build_rss_orders_by_date_descending(self) -> None:
        build = _build()
        _add_doc_page(build, "old", "/old/", {"title": "Old", "date": dt.date(2020, 1, 1)})
        _add_doc_page(build, "new", "/new/", {"title": "New", "date": dt.date(2024, 1, 1)})
        build_rss(build)

        xml = str(build.graph.get(_PAGE_ID).meta["content_html"])  # type: ignore[union-attr]
        self.assertLess(xml.index("New"), xml.index("Old"))

    def test_build_rss_orders_by_url_without_dates(self) -> None:
        build = _build()
        _add_doc_page(build, "b", "/b/", {"title": "B"})
        _add_doc_page(build, "a", "/a/", {"title": "A"})
        build_rss(build)

        xml = str(build.graph.get(_PAGE_ID).meta["content_html"])  # type: ignore[union-attr]
        self.assertLess(xml.index("/a/"), xml.index("/b/"))

    def test_build_rss_caps_to_max_items(self) -> None:
        build = _build()
        for i in range(_MAX_ITEMS + 5):
            # Zero-padded so url ordering is stable and predictable.
            _add_doc_page(build, f"d{i:03d}", f"/d{i:03d}/", {"title": f"D{i}"})
        build_rss(build)

        xml = str(build.graph.get(_PAGE_ID).meta["content_html"])  # type: ignore[union-attr]
        self.assertEqual(xml.count("<item>"), _MAX_ITEMS)

    def test_build_rss_escapes_title(self) -> None:
        build = _build()
        _add_doc_page(build, "a", "/a/", {"title": "A & B <x>"})
        build_rss(build)

        xml = str(build.graph.get(_PAGE_ID).meta["content_html"])  # type: ignore[union-attr]
        self.assertIn("A &amp; B &lt;x&gt;", xml)

    def test_build_rss_skips_virtual_pages(self) -> None:
        build = _build()
        _add_doc_page(build, "a", "/a/", {"title": "A"})
        build.graph.add_node(Page(id="page:tagindex", kind=NodeKind.PAGE, url="/tags/"))
        build_rss(build)

        xml = str(build.graph.get(_PAGE_ID).meta["content_html"])  # type: ignore[union-attr]
        self.assertEqual(xml.count("<item>"), 1)
