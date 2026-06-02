"""Build test for the built-in ``blog-technical`` theme (ported from PaperMod).

The fixture drives the theme through the ``blog`` preset (paginated post
collection) and overrides two theme options, so the test covers three things at
once: the theme renders PaperMod's page structure, the theme configuration API
(#53) layers ``Config.theme`` over the ``layout.toml`` defaults, and two
independent builds are byte-identical (determinism).

This is assertion-based rather than a byte snapshot: the theme bundles a large
stylesheet whose bytes are already version-controlled in the theme directory, so
re-committing them as a golden tree would only add brittle duplication. The
determinism check still guards reproducibility end to end.
"""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "blog_technical"
# The theme lives in the repo-root `themes/` gallery (source-only, not shipped in
# the pyssg wheel), so it is referenced by path rather than via `theme_path`.
THEME = Path(__file__).resolve().parents[2] / "themes" / "blog-technical"


def _files_under(root: Path) -> dict[str, str]:
    return {
        p.relative_to(root).as_posix(): p.read_text(encoding="utf-8")
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


def _build_into(tmp_path: Path) -> Path:
    from pyssg.cli import build_site

    site = tmp_path / "site"
    shutil.copytree(FIXTURE, site)
    # Vendor the gallery theme into the site under `theme/`, matching the
    # relative `layout="theme"` the fixture config points at.
    shutil.copytree(THEME, site / "theme")
    build_site(site)
    return site / "dist"


class BlogTechnicalThemeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_path = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.dist = _build_into(self.tmp_path)

    def _read(self, rel: str) -> str:
        return (self.dist / rel).read_text(encoding="utf-8")

    def test_post_page_has_papermod_structure(self) -> None:
        post = self._read("posts/first-post/index.html")
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
        # Fixture sets Config.theme = {default_theme: dark, toc_open: True}.
        post = self._read("posts/first-post/index.html")
        self.assertIn('data-theme="dark"', post)
        self.assertIn('<details class="toc" open', post)

    def test_theme_option_defaults_apply(self) -> None:
        # show_reading_time defaults to true in layout.toml and is not overridden.
        post = self._read("posts/first-post/index.html")
        self.assertIn("min read", post)

    def test_assets_are_copied(self) -> None:
        self.assertTrue((self.dist / "assets" / "style.css").is_file())
        self.assertTrue((self.dist / "assets" / "js" / "theme.js").is_file())

    def test_build_is_deterministic(self) -> None:
        first = _files_under(_build_into(self.tmp_path / "a"))
        second = _files_under(_build_into(self.tmp_path / "b"))
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
