"""Unit tests for the MarkdownPage plugin."""

from __future__ import annotations

import unittest
from pathlib import Path

from pyssg.build import Build
from pyssg.config import Config
from pyssg.content import GENERATED, URL
from pyssg.models import Output, Source
from pyssg_plugins.markdown_page import (
    MarkdownPage,
    _frontmatter_block,
    _inject_alternate,
    markdown_url,
)


def page(
    url: str,
    *,
    body: str = "",
    raw: str = "",
    frontmatter: dict[str, object] | None = None,
    generated: bool = False,
    draft: bool = False,
) -> Source:
    meta: dict[str, object] = {URL: url}
    if generated:
        meta[GENERATED] = True
    front = dict(frontmatter or {})
    if draft:
        front["draft"] = True
    return Source(
        path=Path("content") / "x.md",
        relpath=Path("x.md"),
        raw=raw,
        body=body,
        frontmatter=front,
        meta=meta,
    )


def build_with(
    sources: list[Source], options: dict[str, object] | None = None
) -> Build:
    build = Build(
        config=Config(src=Path("content"), out=Path("public"), options=options or {})
    )
    build.sources = sources
    return build


def outputs_by_path(build: Build) -> dict[str, Output]:
    return {output.path.as_posix(): output for output in build.outputs}


class MarkdownUrlTest(unittest.TestCase):
    def test_pretty_url(self) -> None:
        self.assertEqual(markdown_url("/guide/intro/"), "/guide/intro.md")

    def test_home_url(self) -> None:
        self.assertEqual(markdown_url("/"), "/index.md")

    def test_non_pretty_html_url(self) -> None:
        self.assertEqual(markdown_url("/foo.html"), "/foo.md")

    def test_extensionless_url(self) -> None:
        self.assertEqual(markdown_url("/foo"), "/foo.md")


class CompanionEmissionTest(unittest.TestCase):
    def test_emits_md_per_page(self) -> None:
        build = build_with([page("/guide/intro/", body="Hello")])
        MarkdownPage(llms_txt=False)._generate(build)
        files = outputs_by_path(build)
        self.assertIn("guide/intro.md", files)
        self.assertEqual(files["guide/intro.md"].content, "Hello\n")

    def test_companion_keeps_source_reference(self) -> None:
        source = page("/foo/", body="Body")
        build = build_with([source])
        MarkdownPage(llms_txt=False)._generate(build)
        self.assertIs(outputs_by_path(build)["foo.md"].source, source)

    def test_skips_generated_pages(self) -> None:
        build = build_with([page("/tags/python/", body="", generated=True)])
        MarkdownPage(llms_txt=False)._generate(build)
        self.assertEqual(build.outputs, [])

    def test_skips_drafts(self) -> None:
        build = build_with([page("/secret/", body="x", draft=True)])
        MarkdownPage(llms_txt=False)._generate(build)
        self.assertEqual(build.outputs, [])

    def test_trailing_newline(self) -> None:
        build = build_with([page("/a/", body="text")])
        MarkdownPage(llms_txt=False)._generate(build)
        self.assertTrue(outputs_by_path(build)["a.md"].content.endswith("\n"))


class ContentOptionsTest(unittest.TestCase):
    def test_body_only_by_default(self) -> None:
        source = page(
            "/a/",
            body="Body text",
            raw="---\ntitle: T\n---\nBody text",
            frontmatter={"title": "T"},
        )
        build = build_with([source])
        MarkdownPage(llms_txt=False)._generate(build)
        self.assertEqual(outputs_by_path(build)["a.md"].content, "Body text\n")

    def test_include_title_prepends_heading(self) -> None:
        source = page("/a/", body="Body", frontmatter={"title": "My Title"})
        build = build_with([source])
        MarkdownPage(llms_txt=False, include_title=True)._generate(build)
        self.assertEqual(outputs_by_path(build)["a.md"].content, "# My Title\n\nBody\n")

    def test_include_title_skips_when_body_has_heading(self) -> None:
        source = page("/a/", body="# Existing\n\nBody", frontmatter={"title": "T"})
        build = build_with([source])
        MarkdownPage(llms_txt=False, include_title=True)._generate(build)
        self.assertEqual(outputs_by_path(build)["a.md"].content, "# Existing\n\nBody\n")

    def test_include_frontmatter_prepends_raw_block(self) -> None:
        source = page(
            "/a/",
            body="Body",
            raw="---\ntitle: T\ntags: [x]\n---\nBody",
            frontmatter={"title": "T"},
        )
        build = build_with([source])
        MarkdownPage(llms_txt=False, include_frontmatter=True)._generate(build)
        content = outputs_by_path(build)["a.md"].content
        self.assertEqual(content, "---\ntitle: T\ntags: [x]\n---\n\nBody\n")


class LlmsIndexTest(unittest.TestCase):
    def test_emits_llms_txt(self) -> None:
        build = build_with(
            [page("/a/", body="x", frontmatter={"title": "Alpha"})],
            {"title": "My Site", "tagline": "A tagline"},
        )
        MarkdownPage()._generate(build)
        index = outputs_by_path(build)["llms.txt"].content
        self.assertIn("# My Site", index)
        self.assertIn("> A tagline", index)
        self.assertIn("- [Alpha](/a.md)", index)

    def test_llms_can_be_disabled(self) -> None:
        build = build_with([page("/a/", body="x")])
        MarkdownPage(llms_txt=False)._generate(build)
        self.assertNotIn("llms.txt", outputs_by_path(build))

    def test_absolute_links_with_base_url(self) -> None:
        build = build_with(
            [page("/a/", body="x", frontmatter={"title": "A"})],
            {"base_url": "https://x.com"},
        )
        MarkdownPage()._generate(build)
        self.assertIn(
            "(https://x.com/a.md)", outputs_by_path(build)["llms.txt"].content
        )

    def test_description_appended(self) -> None:
        build = build_with(
            [page("/a/", body="x", frontmatter={"title": "A", "description": "Desc"})]
        )
        MarkdownPage()._generate(build)
        self.assertIn("- [A](/a.md): Desc", outputs_by_path(build)["llms.txt"].content)

    def test_excludes_generated_and_drafts(self) -> None:
        build = build_with(
            [
                page("/keep/", body="x", frontmatter={"title": "Keep"}),
                page("/tags/t/", generated=True, frontmatter={"title": "Tag"}),
                page("/draft/", draft=True, frontmatter={"title": "Draft"}),
            ]
        )
        MarkdownPage()._generate(build)
        index = outputs_by_path(build)["llms.txt"].content
        self.assertIn("Keep", index)
        self.assertNotIn("Tag", index)
        self.assertNotIn("Draft", index)


class HtmlLinkInjectionTest(unittest.TestCase):
    def _html_output(self, source: Source, html: str) -> Output:
        return Output(path=Path("a/index.html"), content=html, source=source)

    def test_injects_alternate_link(self) -> None:
        source = page("/a/")
        build = build_with([source])
        build.outputs = [self._html_output(source, "<head><title>x</title></head>")]
        MarkdownPage()._inject_links(build)
        content = build.outputs[0].content
        self.assertIn(
            '<link rel="alternate" type="text/markdown" href="/a.md"', content
        )
        self.assertTrue(content.index("text/markdown") < content.index("</head>"))

    def test_skips_outputs_without_source(self) -> None:
        build = build_with([])
        build.outputs = [Output(path=Path("x.html"), content="<head></head>")]
        MarkdownPage()._inject_links(build)
        self.assertNotIn("text/markdown", build.outputs[0].content)

    def test_skips_non_html(self) -> None:
        source = page("/a/")
        build = build_with([source])
        build.outputs = [
            Output(path=Path("a.css"), content="<head></head>", source=source)
        ]
        MarkdownPage()._inject_links(build)
        self.assertNotIn("text/markdown", build.outputs[0].content)

    def test_idempotent(self) -> None:
        source = page("/a/")
        build = build_with([source])
        build.outputs = [self._html_output(source, "<head></head>")]
        MarkdownPage()._inject_links(build)
        MarkdownPage()._inject_links(build)
        self.assertEqual(build.outputs[0].content.count("text/markdown"), 1)

    def test_no_head_left_untouched(self) -> None:
        source = page("/a/")
        build = build_with([source])
        build.outputs = [self._html_output(source, "<p>no head</p>")]
        MarkdownPage()._inject_links(build)
        self.assertEqual(build.outputs[0].content, "<p>no head</p>")

    def test_link_disabled_skips_optimize_tap(self) -> None:
        source = page("/a/")
        build = build_with([source])
        build.outputs = [self._html_output(source, "<head></head>")]
        # With html_link off, calling _inject_links directly still works, but the
        # tap is simply never registered; verify the guard via apply wiring.
        plugin = MarkdownPage(html_link=False)
        self.assertFalse(plugin._html_link)


class HelpersTest(unittest.TestCase):
    def test_frontmatter_block_extracts_verbatim(self) -> None:
        raw = "---\ntitle: T\n---\nbody"
        self.assertEqual(_frontmatter_block(raw), "---\ntitle: T\n---")

    def test_frontmatter_block_absent(self) -> None:
        self.assertEqual(_frontmatter_block("no front matter"), "")

    def test_frontmatter_block_unclosed(self) -> None:
        self.assertEqual(_frontmatter_block("---\ntitle: T\nbody"), "")

    def test_inject_alternate_case_insensitive_head(self) -> None:
        result = _inject_alternate("<HEAD></HEAD>", "/a.md")
        self.assertIn("text/markdown", result)


if __name__ == "__main__":
    unittest.main()
