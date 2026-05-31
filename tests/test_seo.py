"""Tests for the Seo plugin: per-page struct, tag rendering and integration."""

from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stderr
from pathlib import Path

from pyssg.build import Build
from pyssg.config import Config
from pyssg.models import Source
from pyssg_plugins.seo import Seo, _excerpt, _render_tags


def make_build(**options: object) -> Build:
    return Build(
        config=Config(src=Path("content"), out=Path("public"), options=options)
    )


def make_source(
    relpath: str, *, content: str = "", url: str | None = None, **frontmatter: object
) -> Source:
    source = Source(path=Path("content") / relpath, relpath=Path(relpath))
    source.content = content
    source.frontmatter = dict(frontmatter)
    if url is not None:
        source.meta["url"] = url
    return source


def model_for(
    source: Source, build: Build, plugin: Seo | None = None
) -> dict[str, object]:
    (plugin or Seo())._build(source, build)
    seo = source.meta["seo"]
    assert isinstance(seo, dict)
    return seo


class DescriptionTest(unittest.TestCase):
    def test_explicit_description_wins(self) -> None:
        build = make_build(base_url="https://x.com", description="site desc")
        source = make_source(
            "a.md", content="<p>body text</p>", url="/a/", description="page desc"
        )
        self.assertEqual(model_for(source, build)["description"], "page desc")

    def test_summary_used_as_description(self) -> None:
        build = make_build()
        source = make_source("a.md", content="<p>body</p>", summary="from summary")
        self.assertEqual(model_for(source, build)["description"], "from summary")

    def test_excerpt_fallback_from_content(self) -> None:
        build = make_build()
        source = make_source("a.md", content="<h1>Hi</h1><p>Hello world body</p>")
        self.assertEqual(model_for(source, build)["description"], "Hi Hello world body")

    def test_site_description_fallback(self) -> None:
        build = make_build(description="site-wide desc")
        source = make_source("a.md", content="")
        self.assertEqual(model_for(source, build)["description"], "site-wide desc")


class CanonicalTest(unittest.TestCase):
    def test_absolute_canonical_when_base_url_set(self) -> None:
        build = make_build(base_url="https://x.com")
        source = make_source("a.md", url="/a/")
        model = model_for(source, build)
        self.assertEqual(model["canonical"], "https://x.com/a/")

    def test_canonical_omitted_without_base_url(self) -> None:
        build = make_build()
        source = make_source("a.md", url="/a/")
        model = model_for(source, build)
        self.assertEqual(model["canonical"], "")
        self.assertEqual(model["jsonld"], "")

    def test_render_omits_canonical_and_ogurl_when_empty(self) -> None:
        build = make_build()
        source = make_source("a.md", url="/a/", title="A")
        tags = _render_tags(model_for(source, build))
        self.assertNotIn('rel="canonical"', tags)
        self.assertNotIn("og:url", tags)
        self.assertIn("og:title", tags)


class OgTypeTest(unittest.TestCase):
    def test_dated_page_is_article(self) -> None:
        build = make_build(base_url="https://x.com")
        source = make_source("post.md", url="/post/", title="Post", date="2026-01-31")
        model = model_for(source, build)
        self.assertEqual(model["type"], "article")
        self.assertEqual(model["published"], "2026-01-31")
        self.assertIn("article:published_time", _render_tags(model))

    def test_undated_page_is_website(self) -> None:
        build = make_build(base_url="https://x.com")
        source = make_source("about.md", url="/about/", title="About")
        self.assertEqual(model_for(source, build)["type"], "website")

    def test_generated_dated_page_is_not_article(self) -> None:
        build = make_build(base_url="https://x.com")
        source = make_source(
            "blog/index.md", url="/blog/", title="Blog", date="2026-01-31"
        )
        source.meta["generated"] = True
        self.assertEqual(model_for(source, build)["type"], "website")


class JsonLdTest(unittest.TestCase):
    def test_website_for_home(self) -> None:
        build = make_build(base_url="https://x.com", title="My Site", description="d")
        source = make_source("index.md", url="/")
        data = json.loads(str(model_for(source, build)["jsonld"]))
        self.assertEqual(data["@type"], "WebSite")
        self.assertEqual(data["name"], "My Site")
        self.assertEqual(data["url"], "https://x.com/")

    def test_article_for_dated_page(self) -> None:
        build = make_build(base_url="https://x.com")
        source = make_source(
            "post.md", url="/post/", title="P", date="2026-01-31", author="Me"
        )
        data = json.loads(
            str(model_for(source, build, Seo(schema_type="BlogPosting"))["jsonld"])
        )
        self.assertEqual(data["@type"], "BlogPosting")
        self.assertEqual(data["headline"], "P")
        self.assertEqual(data["datePublished"], "2026-01-31")
        self.assertEqual(data["author"], {"@type": "Person", "name": "Me"})

    def test_plain_page_has_no_jsonld(self) -> None:
        build = make_build(base_url="https://x.com")
        source = make_source("about.md", url="/about/", title="About")
        self.assertEqual(model_for(source, build)["jsonld"], "")

    def test_script_close_sequence_is_escaped(self) -> None:
        build = make_build(base_url="https://x.com", title="</script> hack")
        source = make_source("index.md", url="/")
        jsonld = str(model_for(source, build)["jsonld"])
        self.assertNotIn("</script>", jsonld)
        self.assertIn("<\\/script>", jsonld)


class NoindexTest(unittest.TestCase):
    def test_draft_is_noindex(self) -> None:
        build = make_build(base_url="https://x.com")
        source = make_source("a.md", url="/a/", title="A", draft=True)
        model = model_for(source, build)
        self.assertTrue(model["noindex"])
        self.assertIn('name="robots" content="noindex"', _render_tags(model))

    def test_explicit_noindex(self) -> None:
        build = make_build()
        source = make_source("a.md", url="/a/", title="A", noindex=True)
        self.assertTrue(model_for(source, build)["noindex"])


class ImageTest(unittest.TestCase):
    def test_relative_image_made_absolute(self) -> None:
        build = make_build(base_url="https://x.com")
        source = make_source("a.md", url="/a/", image="og.png")
        self.assertEqual(model_for(source, build)["image"], "https://x.com/og.png")

    def test_absolute_image_kept(self) -> None:
        build = make_build()
        source = make_source("a.md", url="/a/", image="https://cdn/og.png")
        self.assertEqual(model_for(source, build)["image"], "https://cdn/og.png")

    def test_image_omitted_without_base_url(self) -> None:
        build = make_build()
        source = make_source("a.md", url="/a/", image="og.png")
        model = model_for(source, build)
        self.assertEqual(model["image"], "")
        self.assertEqual(model["twitter_card"], "summary")

    def test_site_default_image(self) -> None:
        build = make_build(base_url="https://x.com", og_image="default.png")
        source = make_source("a.md", url="/a/")
        model = model_for(source, build)
        self.assertEqual(model["image"], "https://x.com/default.png")
        self.assertEqual(model["twitter_card"], "summary_large_image")


class RenderEscapingTest(unittest.TestCase):
    def test_title_attribute_is_escaped(self) -> None:
        build = make_build(base_url="https://x.com")
        source = make_source("a.md", url="/a/", title='A "quote" & <tag>')
        tags = _render_tags(model_for(source, build))
        self.assertIn("A &quot;quote&quot; &amp; &lt;tag&gt;", tags)
        self.assertNotIn("<tag>", tags)


class ExcerptTest(unittest.TestCase):
    def test_strips_tags_and_collapses_whitespace(self) -> None:
        self.assertEqual(_excerpt("<p>a\n  b</p>", 100), "a b")

    def test_truncates_at_word_boundary(self) -> None:
        result = _excerpt("one two three four", 9)
        self.assertEqual(result, "one two…")


class CollectTest(unittest.TestCase):
    def test_registers_global(self) -> None:
        build = make_build(base_url="https://x.com")
        Seo()._collect(build)
        registry = build.meta["template_globals"]
        assert isinstance(registry, dict)
        self.assertTrue(callable(registry["seo"]))

    def test_warns_when_base_url_missing(self) -> None:
        build = make_build()
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            Seo()._collect(build)
        self.assertIn("base_url", stderr.getvalue())


class GlobalRenderTest(unittest.TestCase):
    def test_seo_global_renders_from_page_struct(self) -> None:
        try:
            import jinja2  # noqa: F401
            from markupsafe import Markup  # noqa: F401
        except ImportError:
            self.skipTest("jinja2/markupsafe not installed")

        from jinja2 import Environment

        build = make_build(base_url="https://x.com")
        Seo()._collect(build)
        registry = build.meta["template_globals"]
        assert isinstance(registry, dict)

        source = make_source("a.md", url="/a/", title="A page")
        Seo()._build(source, build)

        env = Environment(autoescape=True)
        env.globals["seo"] = registry["seo"]
        template = env.from_string("{{ seo() }}")
        html = template.render(page={**source.frontmatter, **source.meta})
        self.assertIn('property="og:title" content="A page"', html)
        self.assertIn("https://x.com/a/", html)


if __name__ == "__main__":
    unittest.main()
