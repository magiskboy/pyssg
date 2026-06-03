"""Unit tests for the taxonomy plugin: slug grouping + per-locale partitioning."""

from __future__ import annotations

import unittest

from pyssg.config import Config
from pyssg.core.build import Build
from pyssg.core.builder import Builder
from pyssg.core.node import Document, Page
from pyssg.core.types import NodeKind
from pyssg.plugins.taxonomy import build_taxonomies, category, tag


def _add_doc_page(build: Build, doc_id: str, url: str, meta: dict[str, object]) -> None:
    build.graph.add_node(Document(id=doc_id, kind=NodeKind.MARKDOWN, meta=meta))
    build.graph.add_node(
        Page(id=f"page:{doc_id}", kind=NodeKind.PAGE, url=url, generated_from=[doc_id])
    )


def _build() -> Build:
    return Builder(config=Config(base_url="https://example.com")).create_build()


def _page(build: Build, pid: str) -> Page:
    node = build.graph.get(pid)
    assert isinstance(node, Page)
    return node


class TaxonomyBasicTest(unittest.TestCase):
    def test_term_and_index_pages(self) -> None:
        build = _build()
        _add_doc_page(build, "a.md", "/a/", {"title": "A", "tags": ["design"]})
        build_taxonomies(build, [tag()])

        self.assertEqual(_page(build, "page:term:tag:design").url, "/tags/design/")
        self.assertEqual(_page(build, "page:taxindex:tag").url, "/tags/")
        all_tags = build.site_data["all_tags"]
        assert isinstance(all_tags, list)
        self.assertEqual(all_tags[0]["url"], "/tags/design/")
        self.assertEqual(all_tags[0]["count"], 1)

    def test_hierarchical_category_expands_to_ancestors(self) -> None:
        build = _build()
        _add_doc_page(build, "a.md", "/a/", {"title": "A", "category": "lang/python"})
        build_taxonomies(build, [category()])

        self.assertEqual(_page(build, "page:term:category:lang").url, "/categories/lang/")
        self.assertEqual(
            _page(build, "page:term:category:lang/python").url, "/categories/lang/python/"
        )

    def test_stale_term_page_removed_on_rebuild(self) -> None:
        build = _build()
        _add_doc_page(build, "a.md", "/a/", {"title": "A", "tags": ["gone"]})
        build_taxonomies(build, [tag()])
        self.assertIsInstance(build.graph.get("page:term:tag:gone"), Page)

        # Drop the tag and rebuild: the now-orphaned term page is removed.
        doc = build.graph.get("a.md")
        assert isinstance(doc, Document)
        doc.meta["tags"] = []
        build_taxonomies(build, [tag()])
        self.assertIsNone(build.graph.get("page:term:tag:gone"))


class TaxonomySlugCollisionTest(unittest.TestCase):
    """Raw terms that share a slug merge into one term page (the historical bug)."""

    def test_python_and_capital_python_merge(self) -> None:
        build = _build()
        _add_doc_page(build, "a.md", "/a/", {"title": "A", "tags": ["python"]})
        _add_doc_page(build, "b.md", "/b/", {"title": "B", "tags": ["Python"]})
        build_taxonomies(build, [tag()])

        page = _page(build, "page:term:tag:python")
        members = page.meta["members"]
        assert isinstance(members, list)
        # Both documents are members of the single shared term page.
        self.assertEqual({m["url"] for m in members}, {"/a/", "/b/"})
        self.assertEqual(page.meta["count"], 2)
        # The index lists exactly one term for the shared slug.
        all_tags = build.site_data["all_tags"]
        assert isinstance(all_tags, list)
        self.assertEqual(len(all_tags), 1)
        # Display label is deterministic (smallest by sort: "Python" < "python").
        self.assertEqual(page.meta["term"], "Python")


class TaxonomyI18nTest(unittest.TestCase):
    """With i18n, term pages are partitioned per locale."""

    def _localized_build(self) -> Build:
        build = _build()
        _add_doc_page(build, "vi/a.md", "/a/", {"title": "A", "tags": ["python"], "lang": "vi"})
        _add_doc_page(build, "en/a.md", "/en/a/", {"title": "A", "tags": ["python"], "lang": "en"})
        build_taxonomies(build, [tag()])
        return build

    def test_term_pages_split_by_locale(self) -> None:
        build = self._localized_build()
        self.assertEqual(_page(build, "page:term:tag:python").url, "/tags/python/")
        self.assertEqual(_page(build, "page:term:tag:en:python").url, "/en/tags/python/")

    def test_term_pages_do_not_mix_locale_members(self) -> None:
        build = self._localized_build()
        vi_members = _page(build, "page:term:tag:python").meta["members"]
        en_members = _page(build, "page:term:tag:en:python").meta["members"]
        assert isinstance(vi_members, list) and isinstance(en_members, list)
        self.assertEqual([m["url"] for m in vi_members], ["/a/"])
        self.assertEqual([m["url"] for m in en_members], ["/en/a/"])

    def test_all_terms_published_per_locale(self) -> None:
        build = self._localized_build()
        # Default locale keeps the bare key; other locales are suffixed.
        self.assertIn("all_tags", build.site_data)
        self.assertIn("all_tags:en", build.site_data)
        en_terms = build.site_data["all_tags:en"]
        assert isinstance(en_terms, list)
        self.assertEqual(en_terms[0]["url"], "/en/tags/python/")


if __name__ == "__main__":
    unittest.main()
