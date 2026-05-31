"""Tests for the scaffolding layer behind ``pyssg new``."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pyssg_cli.scaffold import (
    ScaffoldError,
    new_post,
    new_site,
    parse_manifest,
    render_config,
)
from pyssg_cli.scaffold.themes import (
    ThemeError,
    github_tarball_url,
    list_embedded_themes,
    parse_github_ref,
    resolve_theme,
)

_VALID_TOML = """
[theme]
name = "blog"
description = "A blog"

[config]
preset = "blog"
src = "content"
out = "public"

[config.options]
page_size = 10
rss = true
markdown_extensions = ["fenced_code", "tables"]

[dependencies]
plugins = ["pyssg-search"]

[scaffold]
include = ["layouts", "assets", "content"]
sample = ["content"]
"""


class ParseManifestTest(unittest.TestCase):
    def test_parses_all_fields(self) -> None:
        manifest = parse_manifest(_VALID_TOML)
        self.assertEqual(manifest.name, "blog")
        self.assertEqual(manifest.config.preset, "blog")
        self.assertEqual(manifest.config.src, "content")
        self.assertEqual(manifest.config.options["page_size"], 10)
        self.assertEqual(manifest.config.options["rss"], True)
        self.assertEqual(manifest.plugins, ["pyssg-search"])
        self.assertEqual(manifest.sample, ["content"])

    def test_defaults_when_optional_tables_absent(self) -> None:
        manifest = parse_manifest('[theme]\nname = "x"\n[config]\npreset = "docs"\n')
        self.assertEqual(manifest.config.src, "content")
        self.assertEqual(manifest.config.out, "public")
        self.assertEqual(manifest.include, ["layouts", "assets", "content"])
        self.assertEqual(manifest.sample, ["content"])
        self.assertEqual(manifest.plugins, [])

    def test_missing_name_is_error(self) -> None:
        with self.assertRaises(ThemeError):
            parse_manifest('[theme]\n[config]\npreset = "docs"\n')

    def test_invalid_preset_is_error(self) -> None:
        with self.assertRaises(ThemeError):
            parse_manifest('[theme]\nname = "x"\n[config]\npreset = "nope"\n')

    def test_invalid_toml_is_error(self) -> None:
        with self.assertRaises(ThemeError):
            parse_manifest("this is = = not toml")


class GithubRefTest(unittest.TestCase):
    def test_owner_repo(self) -> None:
        self.assertEqual(parse_github_ref("owner/repo"), ("owner", "repo", "", "main"))

    def test_owner_repo_with_tag(self) -> None:
        self.assertEqual(
            parse_github_ref("owner/repo@v1.2"), ("owner", "repo", "", "v1.2")
        )

    def test_owner_repo_with_subpath_and_tag(self) -> None:
        self.assertEqual(
            parse_github_ref("owner/repo/themes/docs@v1"),
            ("owner", "repo", "themes/docs", "v1"),
        )

    def test_invalid_ref_is_error(self) -> None:
        with self.assertRaises(ThemeError):
            parse_github_ref("justone")

    def test_tarball_url(self) -> None:
        self.assertEqual(
            github_tarball_url("o", "r", "main"),
            "https://codeload.github.com/o/r/tar.gz/main",
        )


class EmbeddedThemeTest(unittest.TestCase):
    def test_official_themes_present(self) -> None:
        themes = list_embedded_themes()
        self.assertIn("docs", themes)
        self.assertIn("blog", themes)

    def test_resolve_embedded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = resolve_theme("docs", workdir=Path(tmp))
            self.assertTrue((path / "theme.toml").is_file())

    def test_resolve_unknown_is_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ThemeError):
                resolve_theme("does-not-exist", workdir=Path(tmp))


class RenderConfigTest(unittest.TestCase):
    def test_renders_importable_config(self) -> None:
        manifest = parse_manifest(_VALID_TOML)
        text = render_config(manifest, site_title="My Blog")
        self.assertIn("from pyssg_cli.presets import blog", text)
        self.assertIn("from pyssg_plugins import StaticFiles", text)
        self.assertIn("page_size=10", text)
        self.assertIn("rss=True", text)
        self.assertIn("'title': 'My Blog'", text)
        # The generated module must be valid, executable Python.
        namespace: dict[str, object] = {}
        exec(compile(text, "<generated>", "exec"), namespace)
        self.assertIn("config", namespace)

    def test_omits_staticfiles_without_assets(self) -> None:
        manifest = parse_manifest(
            '[theme]\nname = "x"\n[config]\npreset = "site"\n'
            '[scaffold]\ninclude = ["layouts", "content"]\n'
        )
        text = render_config(manifest, site_title="X")
        self.assertNotIn("StaticFiles", text)


class NewSiteTest(unittest.TestCase):
    def test_scaffold_docs_site(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "mysite"
            result = new_site(str(target), theme="docs")
            self.assertEqual(result.manifest.name, "docs")
            self.assertTrue((target / "pyssg.config.py").is_file())
            self.assertTrue((target / "layouts" / "base.html").is_file())
            self.assertTrue((target / "assets" / "style.css").is_file())
            self.assertTrue((target / "content" / "index.md").is_file())

    def test_no_sample_skips_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "bare"
            new_site(str(target), theme="docs", sample=False)
            content = target / "content"
            self.assertTrue(content.is_dir())
            self.assertEqual(list(content.iterdir()), [])
            self.assertTrue((target / "layouts" / "base.html").is_file())

    def test_existing_non_empty_dir_is_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "taken"
            target.mkdir()
            (target / "keep.txt").write_text("hi", encoding="utf-8")
            with self.assertRaises(ScaffoldError):
                new_site(str(target), theme="docs")


class NewPostTest(unittest.TestCase):
    def test_creates_post_with_frontmatter(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            content = Path(tmp) / "content"
            content.mkdir()
            path = new_post("My First Post!", content_dir=content, date="2026-01-02")
            self.assertEqual(path, content / "my-first-post.md")
            text = path.read_text(encoding="utf-8")
            self.assertIn('title: "My First Post!"', text)
            self.assertIn("date: 2026-01-02", text)

    def test_autodetects_blog_section(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            content = Path(tmp) / "content"
            (content / "blog").mkdir(parents=True)
            path = new_post("Hello", content_dir=content, date="2026-01-01")
            self.assertEqual(path, content / "blog" / "hello.md")

    def test_explicit_section_overrides(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            content = Path(tmp) / "content"
            (content / "blog").mkdir(parents=True)
            path = new_post(
                "Note", content_dir=content, section="notes", date="2026-01-01"
            )
            self.assertEqual(path, content / "notes" / "note.md")

    def test_duplicate_post_is_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            content = Path(tmp) / "content"
            content.mkdir()
            new_post("Dup", content_dir=content, date="2026-01-01")
            with self.assertRaises(ScaffoldError):
                new_post("Dup", content_dir=content, date="2026-01-01")

    def test_missing_content_dir_is_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ScaffoldError):
                new_post("X", content_dir=Path(tmp) / "nope")


if __name__ == "__main__":
    unittest.main()
