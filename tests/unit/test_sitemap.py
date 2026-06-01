"""Unit tests for the sitemap plugin."""

from __future__ import annotations

import datetime as dt
import unittest

from pyssg.config import Config
from pyssg.core.build import Build
from pyssg.core.builder import Builder
from pyssg.core.node import Document, Page
from pyssg.core.types import NodeKind
from pyssg.plugins.sitemap import (
    _PAGE_ID,
    _PAGE_URL,
    build_sitemap,
    render_sitemap_xml,
)


def _add_doc_page(build: Build, doc_id: str, url: str, meta: dict[str, object]) -> None:
    """Mimic the permalink convention: a Document plus its derived Page."""
    build.graph.add_node(Document(id=doc_id, kind=NodeKind.MARKDOWN, meta=meta))
    build.graph.add_node(
        Page(
            id=f"page:{doc_id}",
            kind=NodeKind.PAGE,
            url=url,
            generated_from=[doc_id],
        )
    )


def _build(base_url: str = "https://example.com") -> Build:
    builder = Builder(config=Config(base_url=base_url))
    return builder.create_build()


class SitemapTest(unittest.TestCase):
    def test_render_sitemap_xml_includes_loc_and_lastmod(self) -> None:
        xml = render_sitemap_xml([("https://example.com/a/", "2024-01-02")])
        self.assertIn("<loc>https://example.com/a/</loc>", xml)
        self.assertIn("<lastmod>2024-01-02</lastmod>", xml)
        self.assertTrue(xml.startswith('<?xml version="1.0" encoding="UTF-8"?>'))

    def test_render_sitemap_xml_omits_lastmod_when_absent(self) -> None:
        xml = render_sitemap_xml([("https://example.com/a/", None)])
        self.assertNotIn("<lastmod>", xml)

    def test_build_sitemap_emits_virtual_page(self) -> None:
        build = _build()
        _add_doc_page(build, "a", "/a/", {"title": "A"})
        build_sitemap(build)

        page = build.graph.get(_PAGE_ID)
        self.assertIsInstance(page, Page)
        self.assertEqual(page.url, _PAGE_URL)  # type: ignore[union-attr]
        self.assertIsNone(page.template)  # type: ignore[union-attr]
        self.assertIn("https://example.com/a/", str(page.meta["content_html"]))  # type: ignore[union-attr]

    def test_build_sitemap_orders_by_url_and_skips_virtual_pages(self) -> None:
        build = _build()
        _add_doc_page(build, "b", "/b/", {"title": "B"})
        _add_doc_page(build, "a", "/a/", {"title": "A"})
        # A virtual page with no provenance must be excluded from the sitemap.
        build.graph.add_node(Page(id="page:tagindex", kind=NodeKind.PAGE, url="/tags/"))
        build_sitemap(build)

        xml = str(build.graph.get(_PAGE_ID).meta["content_html"])  # type: ignore[union-attr]
        self.assertNotIn("/tags/", xml)
        self.assertLess(xml.index("/a/"), xml.index("/b/"))

    def test_build_sitemap_formats_date_objects(self) -> None:
        build = _build()
        _add_doc_page(build, "a", "/a/", {"date": dt.date(2024, 3, 4)})
        _add_doc_page(build, "b", "/b/", {"date": dt.datetime(2024, 5, 6, 7, 8, 9)})
        build_sitemap(build)

        xml = str(build.graph.get(_PAGE_ID).meta["content_html"])  # type: ignore[union-attr]
        self.assertIn("<lastmod>2024-03-04</lastmod>", xml)
        self.assertIn("<lastmod>2024-05-06</lastmod>", xml)

    def test_build_sitemap_escapes_urls(self) -> None:
        build = _build(base_url="https://example.com")
        _add_doc_page(build, "a", "/a?x=1&y=2/", {})
        build_sitemap(build)

        xml = str(build.graph.get(_PAGE_ID).meta["content_html"])  # type: ignore[union-attr]
        self.assertIn("&amp;", xml)
        self.assertNotIn("&y=2", xml.replace("&amp;y=2", ""))

    def test_build_sitemap_is_idempotent(self) -> None:
        build = _build()
        _add_doc_page(build, "a", "/a/", {"title": "A"})
        build_sitemap(build)
        first = str(build.graph.get(_PAGE_ID).meta["content_html"])  # type: ignore[union-attr]
        build_sitemap(build)
        second = str(build.graph.get(_PAGE_ID).meta["content_html"])  # type: ignore[union-attr]
        self.assertEqual(first, second)
        # No duplicate sitemap page was created.
        sitemap_pages = [n for n in build.graph.nodes() if n.id == _PAGE_ID]
        self.assertEqual(len(sitemap_pages), 1)
