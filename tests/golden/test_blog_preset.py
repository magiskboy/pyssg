"""Golden test for the ``blog`` preset (U3 / M6 collections).

The one-line config (``config = blog(...)``) drives the collections plugin + the
bundled ``blog`` theme over the shared content fixture: posts under
``content/posts/`` are date-sorted newest-first and paginated
(``posts_per_page=2`` over three posts puts page 1 at ``/`` and page 2 at
``/page/2/``). The emitted tree is compared byte-for-byte against the committed
snapshot, which also guards determinism across two builds.
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
)
"""

EXPECTED = Path(__file__).resolve().parent / "blog_preset_expected"


def build(tmp_path: Path, name: str = "site") -> Path:
    return build_site_from_fixture(tmp_path, config=CONFIG, name=name)


class BlogPresetGoldenTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_path = Path(self.enterContext(tempfile.TemporaryDirectory()))

    def test_blog_preset_matches_golden(self) -> None:
        produced = files_under(build(self.tmp_path))
        self.assertEqual(produced, files_under(EXPECTED))

    def test_build_is_deterministic(self) -> None:
        """Two independent builds of the same site produce identical bytes."""
        first = files_under(build(self.tmp_path, "a"))
        second = files_under(build(self.tmp_path, "b"))
        self.assertEqual(first, second)
