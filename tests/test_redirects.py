"""Unit tests for the Redirects plugin."""

from __future__ import annotations

import unittest
from pathlib import Path

from pyssg.build import Build
from pyssg.config import Config
from pyssg.models import Output, Source
from pyssg_plugins.redirects import Redirects


def make_build(options: dict[str, object] | None = None) -> Build:
    return Build(
        config=Config(src=Path("content"), out=Path("public"), options=options or {})
    )


def page(url: str, *, aliases: object = None, draft: bool = False) -> Source:
    frontmatter: dict[str, object] = {}
    if aliases is not None:
        frontmatter["aliases"] = aliases
    if draft:
        frontmatter["draft"] = True
    source = Source(path=Path("x.md"), relpath=Path("x.md"))
    source.frontmatter = frontmatter
    source.meta = {"url": url}
    return source


def outputs(build: Build) -> dict[str, Output]:
    return {output.path.as_posix(): output for output in build.outputs}


class AliasCollectionTest(unittest.TestCase):
    def test_emits_html_page_per_alias(self) -> None:
        build = make_build()
        build.sources = [page("/new/", aliases=["/old/", "/older/"])]
        Redirects()._generate(build)
        paths = set(outputs(build))
        self.assertEqual(paths, {"old/index.html", "older/index.html"})

    def test_meta_refresh_points_at_target(self) -> None:
        build = make_build()
        build.sources = [page("/new/", aliases=["/old/"])]
        Redirects()._generate(build)
        content = outputs(build)["old/index.html"].content
        self.assertIn('http-equiv="refresh" content="0; url=/new/"', content)
        self.assertIn('location.replace("/new/")', content)

    def test_no_aliases_emits_nothing(self) -> None:
        build = make_build()
        build.sources = [page("/new/")]
        Redirects()._generate(build)
        self.assertEqual(build.outputs, [])

    def test_string_alias_supported(self) -> None:
        build = make_build()
        build.sources = [page("/new/", aliases="/old/")]
        Redirects()._generate(build)
        self.assertIn("old/index.html", outputs(build))

    def test_draft_pages_are_skipped(self) -> None:
        build = make_build()
        build.sources = [page("/new/", aliases=["/old/"], draft=True)]
        Redirects()._generate(build)
        self.assertEqual(build.outputs, [])

    def test_aliases_can_be_disabled(self) -> None:
        build = make_build()
        build.sources = [page("/new/", aliases=["/old/"])]
        Redirects(aliases=False)._generate(build)
        self.assertEqual(build.outputs, [])

    def test_custom_alias_key(self) -> None:
        build = make_build()
        source = page("/new/")
        source.frontmatter = {"redirect_from": ["/old/"]}
        build.sources = [source]
        Redirects(alias_key="redirect_from")._generate(build)
        self.assertIn("old/index.html", outputs(build))


class NormalizationTest(unittest.TestCase):
    def test_relative_alias_gets_leading_slash(self) -> None:
        build = make_build()
        build.sources = [page("/new/", aliases=["old/"])]
        Redirects()._generate(build)
        self.assertIn("old/index.html", outputs(build))

    def test_bare_alias_path_becomes_index_html(self) -> None:
        build = make_build()
        build.sources = [page("/new/", aliases=["/legacy.html"])]
        Redirects()._generate(build)
        self.assertIn("legacy.html", outputs(build))


class RulesTest(unittest.TestCase):
    def test_explicit_rule_emits_redirect(self) -> None:
        build = make_build()
        build.sources = []
        Redirects(rules={"/old/": "/new/"})._generate(build)
        self.assertIn("old/index.html", outputs(build))

    def test_external_target_kept_verbatim(self) -> None:
        build = make_build()
        build.sources = []
        Redirects(rules={"/go/": "https://example.com/x"})._generate(build)
        content = outputs(build)["go/index.html"].content
        self.assertIn('content="0; url=https://example.com/x"', content)
        self.assertIn('rel="canonical" href="https://example.com/x"', content)

    def test_frontmatter_alias_wins_over_rule(self) -> None:
        build = make_build()
        build.sources = [page("/from-page/", aliases=["/old/"])]
        Redirects(rules={"/old/": "/from-rule/"})._generate(build)
        content = outputs(build)["old/index.html"].content
        self.assertIn("/from-page/", content)
        self.assertNotIn("/from-rule/", content)


class CollisionTest(unittest.TestCase):
    def test_redirect_shadowing_a_page_is_dropped(self) -> None:
        build = make_build()
        build.sources = [page("/keep/")]
        Redirects(rules={"/keep/": "/elsewhere/"})._generate(build)
        self.assertEqual(build.outputs, [])


class CanonicalTest(unittest.TestCase):
    def test_canonical_absolute_with_base_url(self) -> None:
        build = make_build({"base_url": "https://x.com"})
        build.sources = [page("/new/", aliases=["/old/"])]
        Redirects()._generate(build)
        content = outputs(build)["old/index.html"].content
        self.assertIn('rel="canonical" href="https://x.com/new/"', content)


class RedirectsFileTest(unittest.TestCase):
    def test_no_redirects_file_by_default(self) -> None:
        build = make_build()
        build.sources = [page("/new/", aliases=["/old/"])]
        Redirects()._generate(build)
        self.assertNotIn("_redirects", outputs(build))

    def test_emits_redirects_manifest(self) -> None:
        build = make_build()
        build.sources = [page("/new/", aliases=["/old/"])]
        Redirects(emit_redirects_file=True)._generate(build)
        content = outputs(build)["_redirects"].content
        self.assertEqual(content, "/old/ /new/ 301\n")

    def test_custom_status_code(self) -> None:
        build = make_build()
        build.sources = []
        Redirects(
            rules={"/old/": "/new/"}, emit_redirects_file=True, status=302
        )._generate(build)
        self.assertIn("/old/ /new/ 302\n", outputs(build)["_redirects"].content)

    def test_html_can_be_disabled(self) -> None:
        build = make_build()
        build.sources = [page("/new/", aliases=["/old/"])]
        Redirects(emit_html=False, emit_redirects_file=True)._generate(build)
        paths = set(outputs(build))
        self.assertEqual(paths, {"_redirects"})


class EscapingTest(unittest.TestCase):
    def test_target_is_attribute_escaped(self) -> None:
        build = make_build()
        build.sources = []
        Redirects(rules={"/old/": '/new/?a=1&b="2"'})._generate(build)
        content = outputs(build)["old/index.html"].content
        self.assertIn("&amp;", content)
        self.assertIn("&quot;", content)


if __name__ == "__main__":
    unittest.main()
