"""Golden test for the built-in ``blog`` theme (U2).

Drives the bundled ``blog`` theme with the existing plugin set (the ``docs``
preset plus a ``layout`` override pointing at the packaged theme) over the shared
content fixture, proving the theme renders a post list and individual posts with
date/tags/prev-next and tag pages. The emitted tree is compared byte-for-byte
against the committed snapshot, which also guards determinism across two builds.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tests._support import build_site_from_fixture, files_under

CONFIG = """\
from __future__ import annotations

from pyssg.presets import docs
from pyssg.themes import theme_path

config = docs(
    site={"title": "My Blog"},
    base_url="https://example.com",
    layout=theme_path("blog"),
)
"""

EXPECTED = Path(__file__).resolve().parent / "blog_theme_expected"


def build(tmp_path: Path, name: str = "site") -> Path:
    return build_site_from_fixture(tmp_path, config=CONFIG, name=name)


class BlogThemeGoldenTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_path = Path(self.enterContext(tempfile.TemporaryDirectory()))

    def test_blog_theme_matches_golden(self) -> None:
        produced = files_under(build(self.tmp_path))
        self.assertEqual(produced, files_under(EXPECTED))

    def test_build_is_deterministic(self) -> None:
        """Two independent builds of the same site produce identical bytes."""
        first = files_under(build(self.tmp_path, "a"))
        second = files_under(build(self.tmp_path, "b"))
        self.assertEqual(first, second)
