"""Unit tests for the Rss plugin."""

from __future__ import annotations

import unittest
from pathlib import Path

from pyssg.build import Build
from pyssg.config import Config
from pyssg.content import Collection, collections
from pyssg.models import Source
from pyssg_plugins.rss import Rss


def page(rel: str, url: str, **frontmatter: object) -> Source:
    s = Source(path=Path(rel), relpath=Path(rel), frontmatter=dict(frontmatter))
    s.meta["url"] = url
    return s


def build_with(
    name: str, pages: list[Source], options: dict[str, object] | None = None
) -> Build:
    build = Build(
        config=Config(src=Path("content"), out=Path("public"), options=options or {})
    )
    collections(build)[name] = Collection(name=name, kind="folder", pages=pages)
    return build


class RssTest(unittest.TestCase):
    def test_emits_feed_output(self) -> None:
        build = build_with("blog", [page("a.md", "/blog/a/", title="A")])
        Rss(collection="blog")._generate(build)
        self.assertEqual(build.outputs[0].path, Path("feed.xml"))

    def test_missing_collection_emits_nothing(self) -> None:
        build = build_with("blog", [])
        Rss(collection="nope")._generate(build)
        self.assertEqual(build.outputs, [])

    def test_channel_metadata_from_site(self) -> None:
        build = build_with(
            "blog",
            [page("a.md", "/blog/a/", title="A")],
            {"title": "My Site", "tagline": "Hello", "base_url": "https://x.com"},
        )
        Rss(collection="blog")._generate(build)
        xml = build.outputs[0].content
        self.assertIn("<title>My Site</title>", xml)
        self.assertIn("<description>Hello</description>", xml)
        self.assertIn("<link>https://x.com</link>", xml)

    def test_items_with_absolute_links(self) -> None:
        build = build_with(
            "blog",
            [
                page("a.md", "/blog/a/", title="First"),
                page("b.md", "/blog/b/", title="Second"),
            ],
            {"base_url": "https://x.com"},
        )
        Rss(collection="blog")._generate(build)
        xml = build.outputs[0].content
        self.assertEqual(xml.count("<item>"), 2)
        self.assertIn("<link>https://x.com/blog/a/</link>", xml)
        self.assertIn("<title>First</title>", xml)

    def test_pubdate_rfc822(self) -> None:
        build = build_with(
            "blog", [page("a.md", "/blog/a/", title="A", date="2024-01-02")]
        )
        Rss(collection="blog")._generate(build)
        self.assertIn(
            "<pubDate>Tue, 02 Jan 2024 00:00:00 +0000</pubDate>",
            build.outputs[0].content,
        )

    def test_limit_caps_items(self) -> None:
        pages = [page(f"p{i}.md", f"/blog/p{i}/", title=f"P{i}") for i in range(5)]
        build = build_with("blog", pages)
        Rss(collection="blog", limit=2)._generate(build)
        self.assertEqual(build.outputs[0].content.count("<item>"), 2)

    def test_description_included_when_present(self) -> None:
        build = build_with(
            "blog", [page("a.md", "/blog/a/", title="A", description="Hi there")]
        )
        Rss(collection="blog")._generate(build)
        self.assertIn("<description>Hi there</description>", build.outputs[0].content)

    def test_overrides_title_and_path(self) -> None:
        build = build_with("blog", [page("a.md", "/blog/a/", title="A")])
        Rss(collection="blog", path="rss/blog.xml", title="Custom")._generate(build)
        self.assertEqual(build.outputs[0].path, Path("rss/blog.xml"))
        self.assertIn("<title>Custom</title>", build.outputs[0].content)


if __name__ == "__main__":
    unittest.main()
