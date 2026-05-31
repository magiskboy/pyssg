"""Unit tests for the WikiLink plugin."""

from __future__ import annotations

import unittest
from pathlib import Path

from pyssg.build import Build
from pyssg.config import Config
from pyssg.content import URL
from pyssg.models import Source
from pyssg_plugins.link_resolver import BROKEN_LINKS, BrokenLink
from pyssg_plugins.wikilinks import WikiLink


def make_build(pages: dict[str, str]) -> Build:
    build = Build(config=Config(src=Path("content"), out=Path("public")))
    for relpath, url in pages.items():
        source = Source(path=Path(relpath), relpath=Path(relpath))
        source.meta[URL] = url
        build.sources.append(source)
    return build


def transform(build: Build, content: str, relpath: str = "a.md") -> str:
    source = Source(path=Path(relpath), relpath=Path(relpath), content=content)
    source.meta[URL] = "/" + relpath.removesuffix(".md") + "/"
    build.sources.append(source)
    return WikiLink()._transform(source, build).content


class ResolveTest(unittest.TestCase):
    def test_stem_match_renders_anchor(self) -> None:
        build = make_build({"notes/Note Title.md": "/notes/note-title/"})
        out = transform(build, "<p>see [[Note Title]] now</p>")
        self.assertIn(
            '<a class="wikilink" href="/notes/note-title/">Note Title</a>', out
        )

    def test_match_is_case_insensitive(self) -> None:
        build = make_build({"Foo.md": "/foo/"})
        out = transform(build, "<p>[[foo]]</p>")
        self.assertIn('href="/foo/"', out)

    def test_path_form_is_resolved(self) -> None:
        build = make_build({"posts/Deep.md": "/posts/deep/"})
        out = transform(build, "<p>[[posts/Deep]]</p>")
        self.assertIn('href="/posts/deep/"', out)
        self.assertIn(">posts/Deep</a>", out)

    def test_surrounding_whitespace_is_trimmed(self) -> None:
        build = make_build({"Foo.md": "/foo/"})
        out = transform(build, "<p>[[  Foo  ]]</p>")
        self.assertIn('href="/foo/"', out)

    def test_first_source_wins_on_stem_collision(self) -> None:
        build = make_build({"a/Dup.md": "/a/dup/", "b/Dup.md": "/b/dup/"})
        out = transform(build, "<p>[[Dup]]</p>")
        self.assertIn('href="/a/dup/"', out)

    def test_multiple_wikilinks_in_one_document(self) -> None:
        build = make_build({"X.md": "/x/", "Y.md": "/y/"})
        out = transform(build, "<p>[[X]] and [[Y]]</p>")
        self.assertIn('href="/x/"', out)
        self.assertIn('href="/y/"', out)

    def test_link_text_is_html_escaped(self) -> None:
        build = make_build({"A&B.md": "/ab/"})
        out = transform(build, "<p>[[A&B]]</p>")
        self.assertIn(">A&amp;B</a>", out)


class AliasAnchorTest(unittest.TestCase):
    def test_alias_overrides_display_text(self) -> None:
        build = make_build({"Note.md": "/note/"})
        out = transform(build, "<p>[[Note|click here]]</p>")
        self.assertIn('<a class="wikilink" href="/note/">click here</a>', out)

    def test_heading_anchor_is_slugified(self) -> None:
        build = make_build({"Note.md": "/note/"})
        out = transform(build, "<p>[[Note#My Heading]]</p>")
        self.assertIn('href="/note/#my-heading"', out)
        self.assertIn(">Note &gt; My Heading</a>", out)

    def test_heading_and_alias_combined(self) -> None:
        build = make_build({"Note.md": "/note/"})
        out = transform(build, "<p>[[Note#Sec|see section]]</p>")
        self.assertIn('href="/note/#sec"', out)
        self.assertIn(">see section</a>", out)

    def test_same_page_heading_anchor(self) -> None:
        build = make_build({})
        out = transform(build, "<p>[[#Local Section]]</p>", relpath="page.md")
        self.assertIn('href="/page/#local-section"', out)
        self.assertIn(">Local Section</a>", out)

    def test_empty_alias_falls_back_to_default_text(self) -> None:
        build = make_build({"Note.md": "/note/"})
        out = transform(build, "<p>[[Note|]]</p>")
        self.assertIn(">Note</a>", out)

    def test_first_pipe_splits_alias(self) -> None:
        build = make_build({"Note.md": "/note/"})
        out = transform(build, "<p>[[Note|a|b]]</p>")
        self.assertIn(">a|b</a>", out)

    def test_empty_target_is_left_literal(self) -> None:
        build = make_build({})
        out = transform(build, "<p>[[ ]]</p>")
        self.assertIn("[[ ]]", out)
        self.assertNotIn("<a", out)


class BrokenTest(unittest.TestCase):
    def test_unresolved_renders_broken_span(self) -> None:
        build = make_build({})
        out = transform(build, "<p>[[Ghost]]</p>")
        self.assertIn('<span class="wikilink-broken">Ghost</span>', out)

    def test_unresolved_is_recorded(self) -> None:
        build = make_build({})
        transform(build, "<p>[[Ghost]]</p>", relpath="notes/a.md")
        recorded = build.meta.get(BROKEN_LINKS)
        assert isinstance(recorded, list)
        self.assertEqual(recorded, [BrokenLink("notes/a.md", "[[Ghost]]")])

    def test_unresolved_records_raw_with_anchor_and_alias(self) -> None:
        build = make_build({})
        transform(build, "<p>[[Ghost#X|t]]</p>", relpath="a.md")
        recorded = build.meta.get(BROKEN_LINKS)
        assert isinstance(recorded, list)
        self.assertEqual(recorded[0], BrokenLink("a.md", "[[Ghost#X|t]]"))


class CodeProtectionTest(unittest.TestCase):
    def test_fenced_block_is_untouched(self) -> None:
        build = make_build({"Note.md": "/note/"})
        original = "<pre><code>[[Note]]\n</code></pre>"
        self.assertEqual(transform(build, original), original)

    def test_inline_code_is_untouched(self) -> None:
        build = make_build({"Note.md": "/note/"})
        original = "<p>literal <code>[[Note]]</code> here</p>"
        self.assertEqual(transform(build, original), original)

    def test_link_outside_code_still_resolved(self) -> None:
        build = make_build({"Note.md": "/note/"})
        out = transform(build, "<p>[[Note]] <code>[[Note]]</code></p>")
        self.assertIn('href="/note/"', out)
        self.assertIn("<code>[[Note]]</code>", out)


class IgnoreTest(unittest.TestCase):
    def test_embed_syntax_is_left_untouched(self) -> None:
        # ![[note]] is an embed (issue #21), not a link.
        build = make_build({"Note.md": "/note/"})
        out = transform(build, "<p>![[Note]]</p>")
        self.assertIn("![[Note]]", out)
        self.assertNotIn("<a", out)

    def test_content_without_wikilinks_is_unchanged(self) -> None:
        build = make_build({"Note.md": "/note/"})
        original = "<p>plain text, no links</p>"
        self.assertEqual(transform(build, original), original)

    def test_empty_content_is_noop(self) -> None:
        build = make_build({})
        source = Source(path=Path("a.md"), relpath=Path("a.md"), content="")
        self.assertEqual(WikiLink()._transform(source, build).content, "")

    def test_custom_classes(self) -> None:
        build = make_build({"Note.md": "/note/"})
        source = Source(
            path=Path("a.md"), relpath=Path("a.md"), content="<p>[[Note]] [[X]]</p>"
        )
        source.meta[URL] = "/a/"
        build.sources.append(source)
        out = (
            WikiLink(link_class="wl", broken_class="wl-x")
            ._transform(source, build)
            .content
        )
        self.assertIn('<a class="wl" href="/note/">Note</a>', out)
        self.assertIn('<span class="wl-x">X</span>', out)


class IndexTest(unittest.TestCase):
    def test_index_is_cached_and_reused_across_sources(self) -> None:
        build = make_build({"Note.md": "/note/"})
        transform(build, "<p>[[Note]]</p>", relpath="a.md")
        self.assertIn("_wikilink_index", build.meta)
        # A second source reuses the cached index (the cache-hit path).
        out = transform(build, "<p>[[Note]] again</p>", relpath="b.md")
        self.assertIn('href="/note/"', out)

    def test_source_without_url_is_skipped(self) -> None:
        build = make_build({"Note.md": "/note/"})
        # A URL-less source (e.g. not yet assigned) must not enter the index.
        build.sources.append(Source(path=Path("draft.md"), relpath=Path("draft.md")))
        out = transform(build, "<p>[[Note]] and [[draft]]</p>")
        self.assertIn('href="/note/"', out)
        self.assertIn('<span class="wikilink-broken">draft</span>', out)


class HookTest(unittest.TestCase):
    def test_apply_taps_transform(self) -> None:
        from pyssg.builder import Builder

        builder = Builder(Config(src=Path("c"), out=Path("o"), plugins=[WikiLink()]))
        build = make_build({"Note.md": "/note/"})
        source = Source(
            path=Path("a.md"), relpath=Path("a.md"), content="<p>[[Note]]</p>"
        )
        source.meta[URL] = "/a/"
        build.sources.append(source)
        result = builder.hooks.transform.call(source, build)
        self.assertIn('href="/note/"', result.content)


if __name__ == "__main__":
    unittest.main()
