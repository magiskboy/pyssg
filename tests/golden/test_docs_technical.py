"""Build test for the gallery ``docs-technical`` theme (docsy-style).

Drives the gallery theme through the ``docs`` preset over the shared content
fixture with two ``config.theme`` overrides, covering the docsy-like three-column
structure, the theme configuration API (#53) layering -- including the runtime
``accent`` color fed into a CSS custom property -- and byte-for-byte determinism
across two builds.

Assertions target a nested post in the shared fixture (``posts/customizing-the-
look/``) so the breadcrumb, active sidebar link, and on-this-page TOC all have
something to render. The theme lives in the repo-root ``themes/`` gallery
(source-only), so the helper vendors it into the site under ``theme/`` to match
the config's ``layout="theme"``.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tests._support import build_site_from_fixture, files_under

CONFIG = """\
from __future__ import annotations

from pyssg.presets import docs

config = docs(
    site={"title": "My Docs"},
    base_url="https://example.com",
    layout="theme",
)
config.theme = {"default_theme": "dark", "accent": "#b5179e"}
"""

# A nested post that exists in the shared content fixture.
PAGE = "posts/customizing-the-look/index.html"


class DocsTechnicalThemeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_path = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.dist = build_site_from_fixture(
            self.tmp_path, config=CONFIG, vendor_theme="docs-technical"
        )

    def _read(self, rel: str) -> str:
        return (self.dist / rel).read_text(encoding="utf-8")

    def test_page_has_docsy_three_column_structure(self) -> None:
        page = self._read(PAGE)
        for marker in (
            'class="td-navbar"',
            'class="td-main"',
            'class="td-sidebar"',
            'class="td-content"',
            'class="td-sidebar-toc"',
            'class="td-breadcrumb"',
        ):
            self.assertIn(marker, page)

    def test_sidebar_marks_current_page_active(self) -> None:
        page = self._read(PAGE)
        self.assertIn('href="/posts/customizing-the-look/" class="active"', page)

    def test_on_this_page_toc_renders(self) -> None:
        self.assertIn('class="td-toc"', self._read(PAGE))

    def test_tags_index_uses_tag_cloud(self) -> None:
        tags = self._read("tags/index.html")
        self.assertIn('class="td-tag-cloud"', tags)

    def test_theme_option_overrides_propagate(self) -> None:
        # Config sets theme = {default_theme: dark, accent: #b5179e}.
        page = self._read(PAGE)
        self.assertIn('data-theme="dark"', page)
        # The accent option is a real runtime value, fed into --td-accent.
        self.assertIn("--td-accent: #b5179e", page)

    def test_theme_option_defaults_apply(self) -> None:
        # sidebar_title defaults to "Documentation" in layout.toml (not overridden).
        self.assertIn("Documentation", self._read(PAGE))

    def test_assets_are_copied(self) -> None:
        self.assertTrue((self.dist / "assets" / "style.css").is_file())
        self.assertTrue((self.dist / "assets" / "js" / "theme.js").is_file())

    def test_build_is_deterministic(self) -> None:
        """Two independent builds of the same site produce identical bytes."""
        first = files_under(
            build_site_from_fixture(
                self.tmp_path, config=CONFIG, vendor_theme="docs-technical", name="a"
            )
        )
        second = files_under(
            build_site_from_fixture(
                self.tmp_path, config=CONFIG, vendor_theme="docs-technical", name="b"
            )
        )
        self.assertEqual(first, second)
