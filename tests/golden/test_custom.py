"""Golden test for the canonical ``custom`` fixture (a copy of ``examples/custom``).

This is the anchor snapshot for the whole suite: the single content fixture built
through its own ``pyssg.config.py`` -- the ``blog`` preset wearing a locally
ejected, customized theme (``layout/``) with two ``config.theme`` overrides. It
proves the local-layout + theme-options path end to end and that the emitted tree
is byte-for-byte stable across two builds.

Every other golden test reuses this same content fixture but swaps in its own
config, so a content change shows up here first.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tests._support import build_site_from_fixture, files_under

EXPECTED = Path(__file__).resolve().parent / "custom_expected"


def build(tmp_path: Path, name: str = "site") -> Path:
    """Build the fixture through its own config (no override). Used by the test
    and by the golden-tree regeneration step so the two never drift."""
    return build_site_from_fixture(tmp_path, name=name)


class CustomGoldenTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_path = Path(self.enterContext(tempfile.TemporaryDirectory()))

    def test_custom_matches_golden(self) -> None:
        produced = files_under(build(self.tmp_path))
        self.assertEqual(produced, files_under(EXPECTED))

    def test_build_is_deterministic(self) -> None:
        """Two independent builds of the same site produce identical bytes."""
        first = files_under(build(self.tmp_path, "a"))
        second = files_under(build(self.tmp_path, "b"))
        self.assertEqual(first, second)
