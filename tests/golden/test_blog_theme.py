"""Golden test for the built-in ``blog`` theme (U2).

The fixture drives the bundled ``blog`` theme with the existing plugin set
(via the ``docs`` preset with a ``layout`` override), proving the theme renders a
post list, individual posts with date/tags/prev-next, and tag pages. The emitted
tree is compared byte-for-byte against the committed snapshot, which also guards
determinism across two builds. The blog *preset* (date-sorted, paginated post
collection) lands in U3 with M6 collections.
"""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "blog_theme"
EXPECTED = Path(__file__).resolve().parent / "blog_theme_expected"


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
    build_site(site)
    return site / "dist"


class BlogThemeGoldenTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_path = Path(self.enterContext(tempfile.TemporaryDirectory()))

    def test_blog_theme_matches_golden(self) -> None:
        dist = _build_into(self.tmp_path)
        produced = _files_under(dist)
        expected = _files_under(EXPECTED)
        self.assertEqual(produced, expected)

    def test_build_is_deterministic(self) -> None:
        """Two independent builds of the same site produce identical bytes."""
        first = _files_under(_build_into(self.tmp_path / "a"))
        second = _files_under(_build_into(self.tmp_path / "b"))
        self.assertEqual(first, second)
