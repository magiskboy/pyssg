"""Unit tests: caches + cache key."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pyssg.core.builder import Builder
from pyssg.core.incremental.cache import (
    FsCache,
    MemoryCache,
    cache_key,
    cached_or_compute,
)
from pyssg.core.node import Page
from pyssg.core.types import NodeKind, Phase


class CacheTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_path = Path(self.enterContext(tempfile.TemporaryDirectory()))

    def test_memory_cache_roundtrip(self) -> None:
        cache = MemoryCache()
        self.assertIsNone(cache.get("k"))
        cache.set("k", "v")
        self.assertEqual(cache.get("k"), "v")

    def test_fs_cache_persists_across_instances(self) -> None:
        first = FsCache(self.tmp_path)
        first.set("k", {"html": "<p>x</p>"})
        # A fresh instance over the same dir reads the value back from disk.
        second = FsCache(self.tmp_path)
        self.assertEqual(second.get("k"), {"html": "<p>x</p>"})

    def test_cached_or_compute_counts_hits_and_misses(self) -> None:
        builder = Builder()
        build = builder.create_build()
        page = Page(id="p", kind=NodeKind.PAGE, url="/p/")
        calls = 0

        def compute() -> str:
            nonlocal calls
            calls += 1
            return "rendered"

        self.assertEqual(cached_or_compute(build, page, Phase.RENDER, compute), "rendered")
        self.assertEqual(cached_or_compute(build, page, Phase.RENDER, compute), "rendered")
        self.assertEqual(calls, 1)  # second call served from cache
        self.assertEqual(build.stats.cache_hits, 1)

    def test_cache_key_changes_with_input_aspect(self) -> None:
        builder = Builder()
        build = builder.create_build()
        page = Page(id="p", kind=NodeKind.PAGE, url="/p/")
        page.hashes["content"] = "aaa"
        key1 = cache_key(page, Phase.RENDER, build)
        page.hashes["content"] = "bbb"
        key2 = cache_key(page, Phase.RENDER, build)
        self.assertNotEqual(key1, key2)
