"""Build test for the gallery ``blog-minimal`` theme (ported from hugo-coder).

Drives the gallery theme through the ``blog`` preset over the shared content
fixture with two ``config.theme`` overrides, covering the coder page structure,
the theme configuration API (#53) layering, and byte-for-byte determinism across
two builds. Assertion-based rather than a byte snapshot -- the theme's compiled
stylesheet is already version-controlled in the theme directory, so a golden tree
would only add brittle duplication.

The theme lives in the repo-root ``themes/`` gallery (source-only, not shipped in
the wheel), so the helper vendors it into the site under ``theme/`` to match the
config's ``layout="theme"``.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tests._support import build_site_from_fixture, files_under

CONFIG = """\
from __future__ import annotations

from pyssg.presets import blog

config = blog(
    site={"title": "My Blog"},
    base_url="https://example.com",
    posts_per_page=2,
    layout="theme",
)
config.theme = {"default_theme": "dark", "show_toc": True}
"""

# A nested post that exists in the shared content fixture, used to assert the
# theme's single-post structure.
POST = "posts/customizing-the-look/index.html"


class BlogMinimalThemeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_path = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.dist = build_site_from_fixture(
            self.tmp_path, config=CONFIG, vendor_theme="blog-minimal"
        )

    def _read(self, rel: str) -> str:
        return (self.dist / rel).read_text(encoding="utf-8")

    def test_post_page_has_coder_structure(self) -> None:
        post = self._read(POST)
        for marker in (
            'class="navigation"',
            'class="container post"',
            'class="post-title"',
            'class="post-meta"',
            'class="post-content"',
        ):
            self.assertIn(marker, post)

    def test_list_page_lists_posts_and_paginates(self) -> None:
        index = self._read("index.html")
        self.assertIn('class="container list"', index)
        self.assertIn('<a class="title"', index)
        # posts_per_page=2 over three posts paginates, so a second page exists.
        self.assertIn('class="pagination"', index)
        self.assertTrue((self.dist / "page" / "2" / "index.html").is_file())

    def test_tags_index_uses_taxonomy_markup(self) -> None:
        tags = self._read("tags/index.html")
        self.assertIn('class="container taxonomy"', tags)
        self.assertIn('class="taxonomy-element"', tags)

    def test_theme_option_overrides_propagate(self) -> None:
        # Config sets theme = {default_theme: dark, show_toc: True}.
        post = self._read(POST)
        self.assertIn("colorscheme-dark", post)
        self.assertIn('class="toc"', post)

    def test_theme_option_defaults_apply(self) -> None:
        # show_reading_time defaults to true in layout.toml and is not overridden.
        self.assertIn("min read", self._read(POST))

    def test_assets_are_copied(self) -> None:
        self.assertTrue((self.dist / "assets" / "style.css").is_file())
        self.assertTrue((self.dist / "assets" / "js" / "theme.js").is_file())

    def test_build_is_deterministic(self) -> None:
        """Two independent builds of the same site produce identical bytes."""
        first = files_under(
            build_site_from_fixture(
                self.tmp_path, config=CONFIG, vendor_theme="blog-minimal", name="a"
            )
        )
        second = files_under(
            build_site_from_fixture(
                self.tmp_path, config=CONFIG, vendor_theme="blog-minimal", name="b"
            )
        )
        self.assertEqual(first, second)
