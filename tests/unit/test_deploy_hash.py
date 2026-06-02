"""Unit tests for the deterministic output-tree hash."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pyssg.deploy._hash import file_count_and_size, hash_tree


class HashTreeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(self.enterContext(tempfile.TemporaryDirectory()))

    def _write(self, rel: str, body: bytes = b"x") -> None:
        path = self.tmp / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)

    def test_empty_tree_has_stable_hash(self) -> None:
        self.assertEqual(hash_tree(self.tmp), hash_tree(self.tmp))

    def test_missing_root_returns_empty_hash(self) -> None:
        missing = self.tmp / "does-not-exist"
        # No exception; behaves like an empty tree.
        self.assertEqual(hash_tree(missing), hash_tree(self.tmp / "also-missing"))

    def test_identical_trees_have_equal_hash(self) -> None:
        other = Path(self.enterContext(tempfile.TemporaryDirectory()))
        for rel, body in [("a.txt", b"alpha"), ("b/c.txt", b"beta")]:
            (self.tmp / rel).parent.mkdir(parents=True, exist_ok=True)
            (other / rel).parent.mkdir(parents=True, exist_ok=True)
            (self.tmp / rel).write_bytes(body)
            (other / rel).write_bytes(body)
        self.assertEqual(hash_tree(self.tmp), hash_tree(other))

    def test_content_change_changes_hash(self) -> None:
        self._write("a.txt", b"alpha")
        first = hash_tree(self.tmp)
        (self.tmp / "a.txt").write_bytes(b"alphabet")
        self.assertNotEqual(first, hash_tree(self.tmp))

    def test_rename_changes_hash(self) -> None:
        """Same bytes, different relative path -> different digest."""
        self._write("a.txt", b"alpha")
        first = hash_tree(self.tmp)
        (self.tmp / "a.txt").rename(self.tmp / "b.txt")
        self.assertNotEqual(first, hash_tree(self.tmp))

    def test_hash_is_independent_of_iteration_order(self) -> None:
        """Files added in different orders still produce the same hash."""
        other = Path(self.enterContext(tempfile.TemporaryDirectory()))
        files = [("a.txt", b"1"), ("b.txt", b"2"), ("c/d.txt", b"3")]
        for rel, body in files:
            (self.tmp / rel).parent.mkdir(parents=True, exist_ok=True)
            (self.tmp / rel).write_bytes(body)
        for rel, body in reversed(files):
            (other / rel).parent.mkdir(parents=True, exist_ok=True)
            (other / rel).write_bytes(body)
        self.assertEqual(hash_tree(self.tmp), hash_tree(other))


class FileCountAndSizeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(self.enterContext(tempfile.TemporaryDirectory()))

    def test_empty(self) -> None:
        self.assertEqual(file_count_and_size(self.tmp), (0, 0))

    def test_missing_root(self) -> None:
        self.assertEqual(file_count_and_size(self.tmp / "nope"), (0, 0))

    def test_counts_and_sums(self) -> None:
        (self.tmp / "a.txt").write_bytes(b"abc")
        (self.tmp / "b").mkdir()
        (self.tmp / "b" / "c.txt").write_bytes(b"defgh")
        count, total = file_count_and_size(self.tmp)
        self.assertEqual(count, 2)
        self.assertEqual(total, 8)


if __name__ == "__main__":
    unittest.main()
