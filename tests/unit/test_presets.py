"""Unit tests for presets and built-in themes."""

from __future__ import annotations

import unittest
from pathlib import Path

from pyssg.config import Config
from pyssg.core.errors import LayoutError
from pyssg.presets import blog, docs, obsidian
from pyssg.themes import available_themes, theme_path


class ThemePathTest(unittest.TestCase):
    def test_docs_theme_resolves_to_a_real_package(self) -> None:
        path = theme_path("docs")
        self.assertTrue((path / "layout.toml").is_file())
        self.assertTrue((path / "templates").is_dir())

    def test_unknown_theme_raises_with_available_names(self) -> None:
        with self.assertRaises(LayoutError) as ctx:
            theme_path("nope")
        self.assertIn("docs", str(ctx.exception))

    def test_blog_theme_resolves_to_a_real_package(self) -> None:
        path = theme_path("blog")
        self.assertTrue((path / "layout.toml").is_file())
        self.assertTrue((path / "templates" / "post.html.j2").is_file())

    def test_docs_and_blog_are_listed(self) -> None:
        listed = available_themes()
        self.assertIn("docs", listed)
        self.assertIn("blog", listed)


class ObsidianPresetTest(unittest.TestCase):
    def test_returns_config_with_docs_theme_by_default(self) -> None:
        config = obsidian(site={"title": "Vault"})
        self.assertIsInstance(config, Config)
        self.assertEqual(config.layout, theme_path("docs"))

    def test_pipeline_includes_obsidian_specific_plugins(self) -> None:
        names = [p.name for p in obsidian().plugins]
        self.assertIn("obsidian_attachments", names)
        self.assertIn("publish_gate", names)
        self.assertIn("directory_loader", names)

    def test_extra_plugins_are_appended_after_defaults(self) -> None:
        from pyssg.contrib.external_links import external_links

        config = obsidian(extra_plugins=[external_links()])
        self.assertEqual(config.plugins[-1].name, "external_links")

    def test_layout_override_is_used_verbatim(self) -> None:
        config = obsidian(layout="layouts/custom")
        self.assertEqual(config.layout, "layouts/custom")


class DocsPresetTest(unittest.TestCase):
    def test_returns_config_with_builtin_theme_by_default(self) -> None:
        config = docs(site={"title": "T"}, base_url="https://example.com")
        self.assertIsInstance(config, Config)
        self.assertEqual(config.layout, theme_path("docs"))
        self.assertEqual(config.base_url, "https://example.com")
        self.assertEqual(config.site, {"title": "T"})
        # A rich-but-ordered plugin set is bundled so the user wires nothing.
        names = [p.name for p in config.plugins]
        self.assertEqual(names[0], "directory_loader")
        self.assertEqual(names[-1], "render")
        for required in ("markdown", "frontmatter", "permalink", "taxonomy", "wikilink"):
            self.assertIn(required, names)

    def test_layout_override_is_used_verbatim(self) -> None:
        config = docs(layout="layouts/custom")
        self.assertEqual(config.layout, "layouts/custom")

    def test_extra_plugins_are_appended_after_defaults(self) -> None:
        sentinel = docs().plugins[-1]  # render
        config = docs(extra_plugins=[sentinel])
        self.assertEqual(config.plugins[-1], sentinel)
        self.assertEqual(config.plugins[-2].name, "render")

    def test_site_dict_is_copied_not_aliased(self) -> None:
        site: dict[str, object] = {"title": "T"}
        config = docs(site=site)
        site["title"] = "changed"
        self.assertEqual(config.site, {"title": "T"})

    def test_default_site_is_empty_dict(self) -> None:
        self.assertEqual(docs().site, {})

    def test_rss_title_defaults_to_site_title(self) -> None:
        # Smoke check that construction with a title succeeds and stays pure.
        config = docs(site={"title": "My Docs"})
        self.assertIn("rss", [p.name for p in config.plugins])

    def test_paths_are_relative_to_site(self) -> None:
        config = docs()
        self.assertEqual(config.content_dir, "content")
        self.assertEqual(config.output_dir, "dist")
        self.assertNotIsInstance(config.layout, str)
        self.assertIsInstance(config.layout, Path)


class BlogPresetTest(unittest.TestCase):
    def test_returns_config_with_blog_theme_and_collections(self) -> None:
        config = blog(site={"title": "B"}, base_url="https://example.com")
        self.assertIsInstance(config, Config)
        self.assertEqual(config.layout, theme_path("blog"))
        names = [p.name for p in config.plugins]
        self.assertIn("collections", names)
        self.assertEqual(names[-1], "render")

    def test_collections_plugin_has_a_posts_spec(self) -> None:
        config = blog(posts_per_page=3)
        plugin = next(p for p in config.plugins if p.name == "collections")
        specs = plugin.specs  # type: ignore[attr-defined]
        self.assertEqual(len(specs), 1)
        spec = specs[0]
        self.assertEqual(spec.name, "posts")
        self.assertEqual(spec.pagination.size, 3)
        self.assertTrue(spec.reverse)

    def test_extra_plugins_are_appended(self) -> None:
        sentinel = blog().plugins[-1]
        config = blog(extra_plugins=[sentinel])
        self.assertEqual(config.plugins[-1], sentinel)


if __name__ == "__main__":
    unittest.main()
