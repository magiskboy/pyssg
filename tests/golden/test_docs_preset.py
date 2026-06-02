"""Golden test for the ``docs`` preset (U1).

A one-line config (``config = docs(...)``) over the shared content fixture proves
the preset stands up a full site (wikilinks, taxonomy, code highlighting, RSS,
sitemap) with the built-in ``docs`` theme and no manual plugin wiring. The
emitted tree is compared byte-for-byte against the committed snapshot, which also
guards determinism across two builds.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tests._support import build_site_from_fixture, files_under

CONFIG = """\
from __future__ import annotations

from pyssg.presets import docs

config = docs(site={"title": "Docs Preset"}, base_url="https://example.com")
"""

EXPECTED = Path(__file__).resolve().parent / "docs_preset_expected"


def build(tmp_path: Path, name: str = "site") -> Path:
    return build_site_from_fixture(tmp_path, config=CONFIG, name=name)


class DocsPresetGoldenTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_path = Path(self.enterContext(tempfile.TemporaryDirectory()))

    def test_docs_preset_matches_golden(self) -> None:
        produced = files_under(build(self.tmp_path))
        self.assertEqual(produced, files_under(EXPECTED))

    def test_build_is_deterministic(self) -> None:
        """Two independent builds of the same site produce identical bytes."""
        first = files_under(build(self.tmp_path, "a"))
        second = files_under(build(self.tmp_path, "b"))
        self.assertEqual(first, second)
