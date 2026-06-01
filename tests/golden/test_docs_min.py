"""M3 golden test: a minimal docs site builds to a snapshot.

The fixture site is copied into a temp dir (so the build's ``dist`` never touches
the repo), built via the public ``build_site`` entry point, and every emitted
file is compared byte-for-byte against the committed expected output. This also
guards determinism: a second build must reproduce the same bytes.
"""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "docs_min"
EXPECTED = Path(__file__).resolve().parent / "docs_min_expected"


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


class DocsMinGoldenTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_path = Path(self.enterContext(tempfile.TemporaryDirectory()))

    def test_docs_min_matches_golden(self) -> None:
        dist = _build_into(self.tmp_path)
        produced = _files_under(dist)
        expected = _files_under(EXPECTED)
        self.assertEqual(produced, expected)

    def test_build_is_deterministic(self) -> None:
        """Two independent builds of the same site produce identical bytes."""
        first = _files_under(_build_into(self.tmp_path / "a"))
        second = _files_under(_build_into(self.tmp_path / "b"))
        self.assertEqual(first, second)
