"""M3 golden test: a hand-wired minimal site builds to a snapshot.

The "assemble the plugins yourself" path: a bare ``Config`` with an explicit
plugin list (no preset) and a minimal hand-written layout, staged into the shared
content fixture by :func:`tests._support.stage_minimal_site`. Every emitted file
is compared byte-for-byte against the committed expected output, which also
guards determinism across two builds.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tests._support import files_under, stage_minimal_site

EXPECTED = Path(__file__).resolve().parent / "docs_min_expected"


def build(tmp_path: Path, name: str = "site") -> Path:
    """Build the minimal site. Shared by the test and the golden-tree
    regeneration step so the two never drift."""
    from pyssg.cli import build_site

    site = stage_minimal_site(tmp_path, name=name)
    build_site(site)
    return site / "dist"


class DocsMinGoldenTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_path = Path(self.enterContext(tempfile.TemporaryDirectory()))

    def test_docs_min_matches_golden(self) -> None:
        produced = files_under(build(self.tmp_path))
        self.assertEqual(produced, files_under(EXPECTED))

    def test_build_is_deterministic(self) -> None:
        """Two independent builds of the same site produce identical bytes."""
        first = files_under(build(self.tmp_path, "a"))
        second = files_under(build(self.tmp_path, "b"))
        self.assertEqual(first, second)
