"""Unit tests for the ``llms`` contrib plugin."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pyssg.config import Config
from pyssg.contrib.llms import (
    _FULL_ID,
    _FULL_URL,
    _INDEX_ID,
    _INDEX_URL,
    build_llms,
    llms,
    render_full,
    render_index,
)
from pyssg.core.build import Build
from pyssg.core.builder import Builder
from pyssg.core.node import Document, Page
from pyssg.core.types import NodeKind


def _add_doc_page(build: Build, doc_id: str, url: str, meta: dict[str, object]) -> None:
    """Mimic the permalink convention: a Markdown Document plus its derived Page."""
    build.graph.add_node(Document(id=doc_id, kind=NodeKind.MARKDOWN, meta=meta))
    build.graph.add_node(
        Page(id=f"page:{doc_id}", kind=NodeKind.PAGE, url=url, generated_from=[doc_id])
    )


def _build(base_url: str = "https://example.com", **site: object) -> Build:
    builder = Builder(config=Config(base_url=base_url, site=site))
    return builder.create_build()


def _text(build: Build, pid: str) -> str:
    page = build.graph.get(pid)
    assert isinstance(page, Page)
    return str(page.meta["content_html"])


class RenderTest(unittest.TestCase):
    def test_render_index_has_title_summary_sections_and_links(self) -> None:
        from pyssg.contrib.llms import _Entry

        entries = [
            _Entry("docs", "/docs/intro/", "https://e/docs/intro/", "Intro", "Start here", ""),
            _Entry("posts", "/posts/a/", "https://e/posts/a/", "A", "", ""),
        ]
        out = render_index(title="Site", summary="A wiki", entries=entries)
        self.assertTrue(out.startswith("# Site\n"))
        self.assertIn("> A wiki", out)
        self.assertIn("## Docs", out)
        self.assertIn("## Posts", out)
        self.assertIn("- [Intro](https://e/docs/intro/): Start here", out)
        # No excerpt -> no trailing colon.
        self.assertIn("- [A](https://e/posts/a/)\n", out)

    def test_render_index_omits_summary_when_empty(self) -> None:
        out = render_index(title="Site", summary="", entries=[])
        self.assertNotIn(">", out)

    def test_render_full_joins_bodies_with_separator(self) -> None:
        from pyssg.contrib.llms import _Entry

        entries = [
            _Entry("", "/a/", "https://e/a/", "A", "", "Body A\n"),
            _Entry("", "/b/", "https://e/b/", "B", "", "Body B"),
        ]
        out = render_full(entries)
        self.assertIn("# A\nSource: https://e/a/\n\nBody A", out)
        self.assertIn("# B\nSource: https://e/b/\n\nBody B", out)
        self.assertIn("\n\n---\n\n", out)


class BuildLlmsTest(unittest.TestCase):
    def test_emits_both_virtual_pages(self) -> None:
        build = _build(title="T", description="D")
        _add_doc_page(build, "a", "/a/", {"title": "A", "__body__": "Hello"})
        build_llms(build)

        index = build.graph.get(_INDEX_ID)
        full = build.graph.get(_FULL_ID)
        self.assertIsInstance(index, Page)
        self.assertIsInstance(full, Page)
        self.assertEqual(index.url, _INDEX_URL)  # type: ignore[union-attr]
        self.assertEqual(full.url, _FULL_URL)  # type: ignore[union-attr]
        self.assertIsNone(index.template)  # type: ignore[union-attr]
        self.assertIn("# T", _text(build, _INDEX_ID))
        self.assertIn("> D", _text(build, _INDEX_ID))
        self.assertIn("Hello", _text(build, _FULL_ID))

    def test_title_and_summary_default_to_site(self) -> None:
        build = _build(title="My Site", description="My summary")
        _add_doc_page(build, "a", "/a/", {"title": "A"})
        build_llms(build)
        self.assertIn("# My Site", _text(build, _INDEX_ID))
        self.assertIn("> My summary", _text(build, _INDEX_ID))

    def test_explicit_title_and_summary_override_site(self) -> None:
        build = _build(title="Site", description="D")
        _add_doc_page(build, "a", "/a/", {"title": "A"})
        build_llms(build, title="Override", summary="Custom")
        self.assertIn("# Override", _text(build, _INDEX_ID))
        self.assertIn("> Custom", _text(build, _INDEX_ID))

    def test_skips_virtual_pages_without_provenance(self) -> None:
        build = _build()
        _add_doc_page(build, "a", "/a/", {"title": "A", "__body__": "x"})
        build.graph.add_node(Page(id="page:tagindex", kind=NodeKind.PAGE, url="/tags/"))
        build_llms(build)
        self.assertNotIn("/tags/", _text(build, _INDEX_ID))

    def test_skips_non_markdown_documents(self) -> None:
        build = _build()
        build.graph.add_node(Document(id="d", kind=NodeKind.DATA, meta={"title": "D"}))
        build.graph.add_node(Page(id="page:d", kind=NodeKind.PAGE, url="/d/", generated_from=["d"]))
        build_llms(build)
        self.assertNotIn("/d/", _text(build, _INDEX_ID))

    def test_frontmatter_opt_out(self) -> None:
        build = _build()
        _add_doc_page(build, "a", "/a/", {"title": "A", "llms": False})
        _add_doc_page(build, "b", "/b/", {"title": "B"})
        build_llms(build)
        index = _text(build, _INDEX_ID)
        self.assertNotIn("/a/", index)
        self.assertIn("/b/", index)

    def test_include_filters_sections(self) -> None:
        build = _build()
        _add_doc_page(build, "d", "/docs/d/", {"title": "D"})
        _add_doc_page(build, "p", "/posts/p/", {"title": "P"})
        build_llms(build, include=("docs",))
        index = _text(build, _INDEX_ID)
        self.assertIn("/docs/d/", index)
        self.assertNotIn("/posts/p/", index)

    def test_exclude_filters_sections(self) -> None:
        build = _build()
        _add_doc_page(build, "d", "/docs/d/", {"title": "D"})
        _add_doc_page(build, "p", "/posts/p/", {"title": "P"})
        build_llms(build, exclude=("posts",))
        index = _text(build, _INDEX_ID)
        self.assertIn("/docs/d/", index)
        self.assertNotIn("/posts/p/", index)

    def test_full_disabled_omits_and_removes_full_page(self) -> None:
        build = _build()
        _add_doc_page(build, "a", "/a/", {"title": "A"})
        build_llms(build)  # creates the full page
        self.assertIsInstance(build.graph.get(_FULL_ID), Page)
        build_llms(build, full=False)  # toggling off must remove it
        self.assertIsNone(build.graph.get(_FULL_ID))

    def test_entries_sorted_by_section_then_url(self) -> None:
        build = _build()
        _add_doc_page(build, "pb", "/posts/b/", {"title": "PB"})
        _add_doc_page(build, "pa", "/posts/a/", {"title": "PA"})
        _add_doc_page(build, "d", "/docs/x/", {"title": "DX"})
        build_llms(build)
        index = _text(build, _INDEX_ID)
        self.assertLess(index.index("/docs/x/"), index.index("/posts/a/"))
        self.assertLess(index.index("/posts/a/"), index.index("/posts/b/"))

    def test_idempotent(self) -> None:
        build = _build(title="T")
        _add_doc_page(build, "a", "/a/", {"title": "A", "__body__": "x"})
        build_llms(build)
        first = _text(build, _INDEX_ID), _text(build, _FULL_ID)
        build_llms(build)
        second = _text(build, _INDEX_ID), _text(build, _FULL_ID)
        self.assertEqual(first, second)
        index_pages = [n for n in build.graph.nodes() if n.id == _INDEX_ID]
        self.assertEqual(len(index_pages), 1)

    def test_full_resolves_relative_md_links_to_absolute_urls(self) -> None:
        build = _build(base_url="https://e.com")
        # Target page the relative link points at.
        build.graph.add_node(
            Document(
                id="path:blog/other",
                kind=NodeKind.MARKDOWN,
                source_path="blog/other.md",
                meta={"title": "Other"},
            )
        )
        build.graph.add_node(
            Page(
                id="page:path:blog/other",
                kind=NodeKind.PAGE,
                url="/blog/other/",
                generated_from=["path:blog/other"],
            )
        )
        # Linking page whose body has a relative .md link, a fragment link, an
        # external link, and a broken .md link.
        body = "See [o](other.md), [f](other.md#my-sec), [x](https://x.com), and [b](missing.md)."
        build.graph.add_node(
            Document(
                id="path:blog/post",
                kind=NodeKind.MARKDOWN,
                source_path="blog/post.md",
                meta={"title": "Post", "__body__": body},
            )
        )
        build.graph.add_node(
            Page(
                id="page:path:blog/post",
                kind=NodeKind.PAGE,
                url="/blog/post/",
                generated_from=["path:blog/post"],
            )
        )
        build_llms(build)
        full = _text(build, _FULL_ID)
        self.assertIn("[o](https://e.com/blog/other/)", full)
        self.assertIn("[f](https://e.com/blog/other/#my-sec)", full)
        self.assertIn("[x](https://x.com)", full)  # external untouched
        self.assertIn("[b](missing.md)", full)  # broken target left as-is

    def test_factory_returns_named_plugin(self) -> None:
        plugin = llms()
        self.assertEqual(plugin.name, "llms")
        self.assertTrue(plugin.cache_version)


class LlmsBuildTest(unittest.TestCase):
    """End-to-end: the plugin emits files in a real build via a preset."""

    def setUp(self) -> None:
        self.tmp_path = Path(self.enterContext(tempfile.TemporaryDirectory()))

    def test_llms_files_written_to_output(self) -> None:
        from pyssg.cli import build_site

        site = self.tmp_path / "site"
        (site / "content").mkdir(parents=True)
        (site / "content" / "index.md").write_text(
            "---\ntitle: Home\n---\n# Home\nWelcome.\n", encoding="utf-8"
        )
        (site / "content" / "guide.md").write_text(
            "---\ntitle: Guide\nexcerpt: How to\n---\n# Guide\nSteps here.\n",
            encoding="utf-8",
        )
        (site / "pyssg.config.py").write_text(
            "from __future__ import annotations\n"
            "from pyssg.presets import docs\n"
            "from pyssg.contrib.llms import llms\n"
            "config = docs(site={'title': 'T', 'description': 'D'}, "
            "extra_plugins=[llms()])\n"
            "config.base_url = 'https://example.com'\n",
            encoding="utf-8",
        )
        build_site(site)

        index = (site / "dist" / "llms.txt").read_text(encoding="utf-8")
        full = (site / "dist" / "llms-full.txt").read_text(encoding="utf-8")
        self.assertIn("# T", index)
        self.assertIn("> D", index)
        self.assertIn("https://example.com/guide/", index)
        self.assertIn("How to", index)
        self.assertIn("Steps here.", full)


if __name__ == "__main__":
    unittest.main()
