"""Golden test for the ``docs`` preset (U1).

The fixture site's ``pyssg.config.py`` is a single line -- ``config = docs(...)``
-- proving the preset stands up a full documentation site (wikilinks, taxonomy,
code highlighting, RSS, sitemap) with the built-in ``docs`` theme and no manual
plugin wiring. The emitted tree is compared byte-for-byte against the committed
snapshot, which also guards determinism across two builds.
"""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "docs_preset"
EXPECTED = Path(__file__).resolve().parent / "docs_preset_expected"


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


class DocsPresetGoldenTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_path = Path(self.enterContext(tempfile.TemporaryDirectory()))

    def test_docs_preset_matches_golden(self) -> None:
        dist = _build_into(self.tmp_path)
        produced = _files_under(dist)
        expected = _files_under(EXPECTED)
        self.assertEqual(produced, expected)

    def test_build_is_deterministic(self) -> None:
        """Two independent builds of the same site produce identical bytes."""
        first = _files_under(_build_into(self.tmp_path / "a"))
        second = _files_under(_build_into(self.tmp_path / "b"))
        self.assertEqual(first, second)
