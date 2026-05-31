"""Unit tests for the LinkResolver plugin."""

from __future__ import annotations

import unittest
from pathlib import Path

from pyssg.build import Build
from pyssg.config import Config
from pyssg.content import URL
from pyssg.models import Source
from pyssg_plugins.link_resolver import LinkResolver


def make_build(pages: dict[str, str]) -> Build:
    """A build whose sources expose ``relpath -> url`` via ``meta[URL]``."""

    build = Build(config=Config(src=Path("content"), out=Path("public")))
    for relpath, url in pages.items():
        source = Source(path=Path(relpath), relpath=Path(relpath))
        source.meta[URL] = url
        build.sources.append(source)
    return build


def transform(build: Build, relpath: str, content: str) -> str:
    source = Source(path=Path(relpath), relpath=Path(relpath), content=content)
    source.meta[URL] = "/" + relpath.removesuffix(".md") + "/"
    build.sources.append(source)
    return LinkResolver()._transform(source, build).content


class ResolveTest(unittest.TestCase):
    def test_relative_link_is_rewritten(self) -> None:
        build = make_build({"foo/Bar.md": "/foo/bar/"})
        out = transform(build, "notes/index.md", '<a href="../foo/Bar.md">x</a>')
        self.assertIn('href="/foo/bar/"', out)

    def test_sibling_link_is_rewritten(self) -> None:
        build = make_build({"notes/other.md": "/notes/other/"})
        out = transform(build, "notes/index.md", '<a href="other.md">x</a>')
        self.assertIn('href="/notes/other/"', out)

    def test_anchor_fragment_is_preserved(self) -> None:
        build = make_build({"foo/Bar.md": "/foo/bar/"})
        out = transform(build, "notes/index.md", '<a href="../foo/Bar.md#sec">x</a>')
        self.assertIn('href="/foo/bar/#sec"', out)

    def test_query_string_is_preserved(self) -> None:
        build = make_build({"foo/Bar.md": "/foo/bar/"})
        out = transform(build, "a.md", '<a href="foo/Bar.md?v=1#sec">x</a>')
        self.assertIn('href="/foo/bar/?v=1#sec"', out)

    def test_root_relative_link_is_rewritten(self) -> None:
        build = make_build({"foo/Bar.md": "/foo/bar/"})
        out = transform(build, "deep/nested/a.md", '<a href="/foo/Bar.md">x</a>')
        self.assertIn('href="/foo/bar/"', out)

    def test_percent_encoded_name_is_decoded(self) -> None:
        build = make_build({"My Note.md": "/my-note/"})
        out = transform(build, "a.md", '<a href="My%20Note.md">x</a>')
        self.assertIn('href="/my-note/"', out)

    def test_single_quoted_href_is_rewritten(self) -> None:
        build = make_build({"foo.md": "/foo/"})
        out = transform(build, "a.md", "<a href='foo.md'>x</a>")
        self.assertIn("href='/foo/'", out)

    def test_other_attributes_are_preserved(self) -> None:
        build = make_build({"foo.md": "/foo/"})
        out = transform(build, "a.md", '<a class="c" href="foo.md" title="t">x</a>')
        self.assertIn('class="c"', out)
        self.assertIn('title="t"', out)
        self.assertIn('href="/foo/"', out)

    def test_markdown_suffix_variant_is_resolved(self) -> None:
        build = make_build({"foo.markdown": "/foo/"})
        out = transform(build, "a.md", '<a href="foo.markdown">x</a>')
        self.assertIn('href="/foo/"', out)


class LeftUntouchedTest(unittest.TestCase):
    def test_external_link_is_untouched(self) -> None:
        build = make_build({"foo.md": "/foo/"})
        out = transform(build, "a.md", '<a href="https://x.com/foo.md">x</a>')
        self.assertIn('href="https://x.com/foo.md"', out)

    def test_mailto_is_untouched(self) -> None:
        build = make_build({})
        out = transform(build, "a.md", '<a href="mailto:me@x.com">x</a>')
        self.assertIn('href="mailto:me@x.com"', out)

    def test_protocol_relative_is_untouched(self) -> None:
        build = make_build({})
        out = transform(build, "a.md", '<a href="//cdn.x.com/foo.md">x</a>')
        self.assertIn('href="//cdn.x.com/foo.md"', out)

    def test_anchor_only_is_untouched(self) -> None:
        build = make_build({})
        out = transform(build, "a.md", '<a href="#section">x</a>')
        self.assertIn('href="#section"', out)

    def test_query_only_is_untouched(self) -> None:
        build = make_build({})
        out = transform(build, "a.md", '<a href="?page=2">x</a>')
        self.assertIn('href="?page=2"', out)

    def test_non_markdown_link_is_untouched(self) -> None:
        build = make_build({})
        out = transform(build, "a.md", '<a href="../about/">x</a>')
        self.assertIn('href="../about/"', out)

    def test_unknown_target_is_untouched(self) -> None:
        build = make_build({})
        out = transform(build, "a.md", '<a href="missing.md">x</a>')
        self.assertIn('href="missing.md"', out)

    def test_escape_above_root_is_untouched(self) -> None:
        build = make_build({"foo.md": "/foo/"})
        out = transform(build, "a.md", '<a href="../../foo.md">x</a>')
        self.assertIn('href="../../foo.md"', out)

    def test_link_inside_code_fence_is_untouched(self) -> None:
        # Markdown renders fenced links as escaped text inside <code>, never as an
        # anchor, so the resolver never sees an href to rewrite.
        build = make_build({"foo.md": "/foo/"})
        original = "<pre><code>[x](foo.md)</code></pre>"
        out = transform(build, "a.md", original)
        self.assertEqual(out, original)


class MultipleAndEmptyTest(unittest.TestCase):
    def test_multiple_links_are_all_rewritten(self) -> None:
        build = make_build({"a/x.md": "/a/x/", "a/y.md": "/a/y/"})
        content = '<a href="a/x.md">x</a> and <a href="a/y.md">y</a>'
        out = transform(build, "a.md", content)
        self.assertIn('href="/a/x/"', out)
        self.assertIn('href="/a/y/"', out)

    def test_empty_content_is_noop(self) -> None:
        build = make_build({})
        source = Source(path=Path("a.md"), relpath=Path("a.md"), content="")
        result = LinkResolver()._transform(source, build)
        self.assertEqual(result.content, "")

    def test_registry_is_cached_across_sources(self) -> None:
        build = make_build({"foo.md": "/foo/"})
        transform(build, "a.md", '<a href="foo.md">x</a>')
        self.assertIn("_link_registry", build.meta)


if __name__ == "__main__":
    unittest.main()
