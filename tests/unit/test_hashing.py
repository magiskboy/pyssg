"""Unit tests: aspect hashing & identity."""

from __future__ import annotations

import unittest

from pyssg.core.incremental.hashing import (
    canonical_bytes,
    compute_raw_hash,
    digest,
    hash_aspect,
    resolve_identity,
)
from pyssg.core.node import Document
from pyssg.core.types import NodeKind


class HashingTest(unittest.TestCase):
    def test_raw_hash_normalizes_newlines(self) -> None:
        self.assertEqual(compute_raw_hash(b"a\r\nb"), compute_raw_hash(b"a\nb"))

    def test_raw_hash_differs_on_content(self) -> None:
        self.assertNotEqual(compute_raw_hash(b"a"), compute_raw_hash(b"b"))

    def test_canonical_bytes_dict_order_independent(self) -> None:
        self.assertEqual(canonical_bytes({"a": 1, "b": 2}), canonical_bytes({"b": 2, "a": 1}))

    def test_digest_is_deterministic_and_separated(self) -> None:
        self.assertEqual(digest("a", "b"), digest("a", "b"))
        # Separator prevents ("a","b") colliding with ("ab",).
        self.assertNotEqual(digest("a", "b"), digest("ab"))

    def test_hash_aspect_stores_on_node(self) -> None:
        node = Document(id="d", kind=NodeKind.MARKDOWN)
        h = hash_aspect(node, "body", "hello")
        self.assertEqual(node.hashes["body"], h)
        self.assertEqual(hash_aspect(node, "body", "hello"), h)
        self.assertNotEqual(hash_aspect(node, "body", "other"), h)

    def test_resolve_identity_precedence(self) -> None:
        # frontmatter id wins
        self.assertEqual(resolve_identity("p.md", {"id": "x", "slug": "s"}, "h", {}), "id:x")
        # then move-detect by raw hash
        self.assertEqual(resolve_identity("p.md", {}, "h", {"h": "id:moved"}), "id:moved")
        # then slug
        self.assertEqual(resolve_identity("p.md", {"slug": "s"}, "h", {}), "slug:s")
        # then path fallback
        self.assertEqual(resolve_identity("p.md", {}, "h", {}), "path:p.md")
