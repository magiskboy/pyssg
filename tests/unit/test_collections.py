"""Unit tests for the collections plugin: section, per-locale pagination."""

from __future__ import annotations

import unittest

from pyssg.config import Config
from pyssg.core.build import Build
from pyssg.core.builder import Builder
from pyssg.core.node import Document, Page
from pyssg.core.types import NodeKind
from pyssg.plugins.collections import (
    CollectionSpec,
    Pagination,
    build_collections,
)


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


def _posts_spec(size: int = 2) -> CollectionSpec:
    return CollectionSpec(
        name="posts",
        select=lambda item: item.section == "posts",
        sort_key=lambda item: item.date,
        reverse=True,
        pagination=Pagination(size=size, route="/", template="list.html.j2"),
        title="Posts",
    )


class CollectionsBasicTest(unittest.TestCase):
    def test_paginates_at_route(self) -> None:
        build = _build()
        _add_doc_page(build, "p1.md", "/posts/a/", {"title": "A", "date": "2024-01-01"})
        _add_doc_page(build, "p2.md", "/posts/b/", {"title": "B", "date": "2024-01-02"})
        _add_doc_page(build, "p3.md", "/posts/c/", {"title": "C", "date": "2024-01-03"})
        build_collections(build, (_posts_spec(size=2),))

        self.assertEqual(_page(build, "page:collection:posts:1").url, "/")
        self.assertEqual(_page(build, "page:collection:posts:2").url, "/page/2/")
        # Newest first across the two pages.
        first = _page(build, "page:collection:posts:1").meta["items"]
        assert isinstance(first, list)
        self.assertEqual([i["title"] for i in first], ["C", "B"])

    def test_select_uses_section(self) -> None:
        build = _build()
        _add_doc_page(build, "p.md", "/posts/a/", {"title": "A"})
        _add_doc_page(build, "about.md", "/about/", {"title": "About"})
        build_collections(build, (_posts_spec(),))

        members = build.site_data["posts"]
        assert isinstance(members, list)
        self.assertEqual([m["url"] for m in members], ["/posts/a/"])


class CollectionsI18nTest(unittest.TestCase):
    """With i18n, each locale gets its own paginated index under its root."""

    def _localized_build(self) -> Build:
        build = _build()
        # Vietnamese (default, root) posts and English (prefixed) posts.
        _add_doc_page(
            build, "vi/p.md", "/posts/a/", {"title": "Bai", "date": "2024-01-01", "lang": "vi"}
        )
        _add_doc_page(
            build,
            "en/p.md",
            "/en/posts/a/",
            {"title": "Post", "date": "2024-01-01", "lang": "en"},
        )
        build_collections(build, (_posts_spec(),))
        return build

    def test_section_ignores_locale_prefix(self) -> None:
        # The English post must be selected even though its URL starts with /en/.
        build = self._localized_build()
        en_members = build.site_data["posts:en"]
        assert isinstance(en_members, list)
        self.assertEqual([m["url"] for m in en_members], ["/en/posts/a/"])

    def test_index_pages_split_by_locale(self) -> None:
        build = self._localized_build()
        self.assertEqual(_page(build, "page:collection:posts:1").url, "/")
        self.assertEqual(_page(build, "page:collection:posts:en:1").url, "/en/")

    def test_index_pages_do_not_mix_locales(self) -> None:
        build = self._localized_build()
        root_items = _page(build, "page:collection:posts:1").meta["items"]
        en_items = _page(build, "page:collection:posts:en:1").meta["items"]
        assert isinstance(root_items, list) and isinstance(en_items, list)
        self.assertEqual([i["title"] for i in root_items], ["Bai"])
        self.assertEqual([i["title"] for i in en_items], ["Post"])

    def test_member_lists_published_per_locale(self) -> None:
        build = self._localized_build()
        self.assertIn("posts", build.site_data)  # default locale keeps bare key
        self.assertIn("posts:en", build.site_data)


if __name__ == "__main__":
    unittest.main()
