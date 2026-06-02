"""M4 acceptance: a second build reuses the cache and is byte-identical.

This is the determinism / purity guard: rebuilding the same site
with a shared cache must serve render results from cache yet produce the exact
same output bytes. It builds the shared content fixture twice in place (the
cache only reuses work when the same site dir is rebuilt).
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pyssg.cli import build_site
from pyssg.core.incremental.cache import FsCache, MemoryCache
from tests._support import files_under, stage_minimal_site


class CacheReuseTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_path = Path(self.enterContext(tempfile.TemporaryDirectory()))

    def test_memory_cache_second_build_hits_and_is_identical(self) -> None:
        site = stage_minimal_site(self.tmp_path)
        cache = MemoryCache()

        stats1 = build_site(site, cache=cache)
        out1 = files_under(site / "dist")
        self.assertEqual(stats1.cache_hits, 0)  # cold

        stats2 = build_site(site, cache=cache)
        out2 = files_under(site / "dist")
        # every page from cache
        self.assertEqual(stats2.cache_hits, len(stats2.changed_outputs))
        self.assertGreater(stats2.cache_hits, 0)
        self.assertEqual(out1, out2)  # byte-identical

    def test_fs_cache_persists_across_runs(self) -> None:
        site = stage_minimal_site(self.tmp_path)
        cache_dir = self.tmp_path / "cache"

        build_site(site, cache=FsCache(cache_dir))
        out1 = files_under(site / "dist")

        # A brand-new FsCache over the same dir simulates a fresh process / cold start.
        stats2 = build_site(site, cache=FsCache(cache_dir))
        out2 = files_under(site / "dist")
        self.assertGreater(stats2.cache_hits, 0)
        self.assertEqual(out1, out2)
