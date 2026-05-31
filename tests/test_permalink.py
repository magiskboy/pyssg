"""Unit tests for the Permalink plugin."""

from __future__ import annotations

import unittest
from pathlib import Path

from pyssg.build import Build
from pyssg.config import Config
from pyssg.models import Source
from pyssg_plugins.permalink import Permalink, resolve_slugify, slugify


def render(source: Source, plugin: Permalink | None = None) -> Source:
    (plugin or Permalink())._assign(source, slugify)
    return source


def src(rel: str, **frontmatter: object) -> Source:
    return Source(path=Path(rel), relpath=Path(rel), frontmatter=dict(frontmatter))


class SlugifyTest(unittest.TestCase):
    def test_basic(self) -> None:
        self.assertEqual(slugify("Hello World"), "hello-world")

    def test_strips_punctuation_and_edges(self) -> None:
        self.assertEqual(slugify("  A, B & C!  "), "a-b-c")

    def test_vietnamese_diacritics(self) -> None:
        self.assertEqual(slugify("Lập trình bất đồng bộ"), "lap-trinh-bat-dong-bo")

    def test_other_scripts(self) -> None:
        self.assertEqual(slugify("Größe"), "grosse")
        self.assertEqual(slugify("北京欢迎你"), "bei-jing-huan-ying-ni")


class ResolveSlugifyTest(unittest.TestCase):
    def _build(self, slug: object = None) -> Build:
        config = Config(src=Path("content"), out=Path("public"))
        if slug is not None:
            config.slugify = slug  # type: ignore[assignment]
        return Build(config=config)

    def test_defaults_to_builtin(self) -> None:
        self.assertIs(resolve_slugify(self._build()), slugify)

    def test_config_override_wins(self) -> None:
        build = self._build(lambda text: text.upper())
        self.assertEqual(resolve_slugify(build)("abc"), "ABC")

    def test_override_drives_pattern(self) -> None:
        build = self._build(lambda text: "fixed")
        build.sources.append(src("x.md", title="Anything"))
        Permalink(pattern="/p/:title/")._collect(build)
        self.assertEqual(build.sources[0].meta["url"], "/p/fixed/")


class PrettyUrlTest(unittest.TestCase):
    def test_page_becomes_directory(self) -> None:
        s = render(src("foo.md"))
        self.assertEqual(s.meta["url"], "/foo/")
        self.assertEqual(s.meta["output_path"], "foo/index.html")

    def test_nested_page(self) -> None:
        s = render(src("blog/post.md"))
        self.assertEqual(s.meta["url"], "/blog/post/")
        self.assertEqual(s.meta["output_path"], "blog/post/index.html")

    def test_root_index(self) -> None:
        s = render(src("index.md"))
        self.assertEqual(s.meta["url"], "/")
        self.assertEqual(s.meta["output_path"], "index.html")

    def test_folder_index(self) -> None:
        s = render(src("blog/index.md"))
        self.assertEqual(s.meta["url"], "/blog/")
        self.assertEqual(s.meta["output_path"], "blog/index.html")


class FlatUrlTest(unittest.TestCase):
    def test_non_pretty(self) -> None:
        s = render(src("blog/post.md"), Permalink(pretty=False))
        self.assertEqual(s.meta["url"], "/blog/post.html")
        self.assertEqual(s.meta["output_path"], "blog/post.html")


class FrontmatterOverrideTest(unittest.TestCase):
    def test_explicit_permalink_directory(self) -> None:
        s = render(src("x.md", permalink="/custom/place/"))
        self.assertEqual(s.meta["url"], "/custom/place/")
        self.assertEqual(s.meta["output_path"], "custom/place/index.html")

    def test_explicit_permalink_with_tokens(self) -> None:
        s = render(
            src("x.md", permalink="/blog/:year/:slug/", date="2024-03-07", slug="hello")
        )
        self.assertEqual(s.meta["url"], "/blog/2024/hello/")

    def test_explicit_permalink_normalizes_missing_slash(self) -> None:
        s = render(src("x.md", permalink="about"))
        self.assertEqual(s.meta["url"], "/about/")


class PatternTest(unittest.TestCase):
    def test_pattern_applied_with_date_and_slug(self) -> None:
        plugin = Permalink(pattern="/blog/:year/:month/:slug/")
        s = render(src("hello.md", date="2024-1-5"), plugin)
        self.assertEqual(s.meta["url"], "/blog/2024/01/hello/")

    def test_pattern_title_token(self) -> None:
        plugin = Permalink(pattern="/posts/:title/")
        s = render(src("a.md", title="My First Post"), plugin)
        self.assertEqual(s.meta["url"], "/posts/my-first-post/")

    def test_pattern_arbitrary_frontmatter_key(self) -> None:
        plugin = Permalink(pattern="/:category/:slug/")
        s = render(src("a.md", category="Tech News", slug="x"), plugin)
        self.assertEqual(s.meta["url"], "/tech-news/x/")


class PrecedenceTest(unittest.TestCase):
    def test_frontmatter_beats_pattern(self) -> None:
        plugin = Permalink(pattern="/blog/:slug/")
        s = render(src("a.md", permalink="/override/", slug="x"), plugin)
        self.assertEqual(s.meta["url"], "/override/")

    def test_existing_url_not_overridden(self) -> None:
        s = src("a.md")
        s.meta["url"] = "/already/"
        render(s)
        self.assertEqual(s.meta["url"], "/already/")
        self.assertNotIn("output_path", s.meta)

    def test_pattern_skipped_for_generated_pages(self) -> None:
        plugin = Permalink(pattern="/blog/:slug/")
        s = src("tags/python.md")
        s.meta["generated"] = True
        render(s, plugin)
        # Falls back to default pretty URL instead of the post pattern.
        self.assertEqual(s.meta["url"], "/tags/python/")


if __name__ == "__main__":
    unittest.main()
