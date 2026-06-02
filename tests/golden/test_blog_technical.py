"""Build test for the gallery ``blog-technical`` theme (ported from PaperMod).

Drives the gallery theme through the ``blog`` preset over the shared content
fixture and overrides two theme options, covering three things at once: the theme
renders PaperMod's page structure, the theme configuration API (#53) layers
``config.theme`` over the ``layout.toml`` defaults, and two independent builds are
byte-identical (determinism).

Assertion-based rather than a byte snapshot: the theme bundles a large stylesheet
whose bytes are already version-controlled in the theme directory, so
re-committing them as a golden tree would only add brittle duplication. The theme
lives in the repo-root ``themes/`` gallery (source-only), so the helper vendors it
into the site under ``theme/`` to match the config's ``layout="theme"``.
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
config.theme = {"default_theme": "dark", "toc_open": True}
"""

# A nested post that exists in the shared content fixture, used to assert the
# theme's single-post structure.
POST = "posts/customizing-the-look/index.html"


class BlogTechnicalThemeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_path = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.dist = build_site_from_fixture(
            self.tmp_path, config=CONFIG, vendor_theme="blog-technical"
        )

    def _read(self, rel: str) -> str:
        return (self.dist / rel).read_text(encoding="utf-8")

    def test_post_page_has_papermod_structure(self) -> None:
        post = self._read(POST)
        # Core PaperMod building blocks, keyed by the class names its CSS targets.
        for marker in (
            'class="post-single"',
            'class="post-header"',
            'class="post-content md-content"',
            'class="breadcrumbs"',
            'class="post-meta"',
            'class="paginav"',
        ):
            self.assertIn(marker, post)

    def test_list_page_uses_entry_cards_and_pagination(self) -> None:
        index = self._read("index.html")
        self.assertIn('<body class="list"', index)
        self.assertIn('class="post-entry"', index)
        self.assertIn('class="entry-link"', index)
        # posts_per_page=2 over three posts paginates, so a second page exists.
        self.assertIn('class="pagination"', index)
        self.assertTrue((self.dist / "page" / "2" / "index.html").is_file())

    def test_tags_index_lists_terms(self) -> None:
        tags = self._read("tags/index.html")
        self.assertIn('class="terms-tags"', tags)

    def test_theme_option_overrides_propagate(self) -> None:
        # Config sets theme = {default_theme: dark, toc_open: True}.
        post = self._read(POST)
        self.assertIn('data-theme="dark"', post)
        self.assertIn('<details class="toc" open', post)

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
                self.tmp_path, config=CONFIG, vendor_theme="blog-technical", name="a"
            )
        )
        second = files_under(
            build_site_from_fixture(
                self.tmp_path, config=CONFIG, vendor_theme="blog-technical", name="b"
            )
        )
        self.assertEqual(first, second)
