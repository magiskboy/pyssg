"""Unit tests for the Sitemap plugin."""

from __future__ import annotations

import unittest
from pathlib import Path

from pyssg.build import Build
from pyssg.config import Config
from pyssg.models import Source
from pyssg_plugins.sitemap import Sitemap


def page(rel: str, url: str, **frontmatter: object) -> Source:
    s = Source(path=Path(rel), relpath=Path(rel), frontmatter=dict(frontmatter))
    s.meta["url"] = url
    return s


def run(sources: list[Source], options: dict[str, object] | None = None) -> str:
    build = Build(
        config=Config(src=Path("content"), out=Path("public"), options=options or {})
    )
    build.sources = sources
    Sitemap()._generate(build)
    return build.outputs[0].content


class SitemapTest(unittest.TestCase):
    def test_emits_sitemap_output(self) -> None:
        build = Build(config=Config(src=Path("c"), out=Path("p")))
        build.sources = [page("a.md", "/a/")]
        Sitemap()._generate(build)
        self.assertEqual(build.outputs[0].path, Path("sitemap.xml"))

    def test_absolute_urls_with_base(self) -> None:
        xml = run([page("a.md", "/a/")], {"base_url": "https://x.com/"})
        self.assertIn("<loc>https://x.com/a/</loc>", xml)

    def test_root_relative_without_base(self) -> None:
        xml = run([page("a.md", "/a/")])
        self.assertIn("<loc>/a/</loc>", xml)

    def test_lastmod_from_date(self) -> None:
        xml = run([page("a.md", "/a/", date="2024-03-07")])
        self.assertIn("<lastmod>2024-03-07</lastmod>", xml)

    def test_drafts_excluded(self) -> None:
        xml = run([page("a.md", "/a/"), page("b.md", "/b/", draft=True)])
        self.assertIn("/a/", xml)
        self.assertNotIn("/b/", xml)

    def test_pages_without_url_excluded(self) -> None:
        no_url = Source(path=Path("x.md"), relpath=Path("x.md"))
        xml = run([page("a.md", "/a/"), no_url])
        self.assertEqual(xml.count("<url>"), 1)

    def test_special_characters_escaped(self) -> None:
        xml = run([page("a.md", "/search/?q=a&b/")], {"base_url": "https://x.com"})
        self.assertIn("&amp;", xml)
        self.assertNotIn("?q=a&b", xml)


if __name__ == "__main__":
    unittest.main()
