"""Unit tests: node model and dependency hashability."""

from __future__ import annotations

import unittest

from pyssg.core.dependency import Dependency
from pyssg.core.node import Asset, Document, Node
from pyssg.core.types import NodeKind, Phase, SourceSpan


class NodeModelTest(unittest.TestCase):
    def test_node_defaults(self) -> None:
        n = Node(id="x", kind=NodeKind.MARKDOWN)
        self.assertIsNone(n.source_path)
        self.assertIs(n.state, Phase.LOAD)
        self.assertEqual(n.meta, {})
        self.assertEqual(n.hashes, {})
        self.assertEqual(n.dependencies, [])
        self.assertIsNone(n.ast)
        self.assertIsNone(n.payload)

    def test_lazy_ast_payload_properties(self) -> None:
        n = Node(id="x", kind=NodeKind.MARKDOWN)
        n.ast = {"type": "root"}
        n.payload = b"<html></html>"
        self.assertEqual(n.ast, {"type": "root"})
        self.assertEqual(n.payload, b"<html></html>")

    def test_add_dependency(self) -> None:
        n = Document(id="x", kind=NodeKind.MARKDOWN)
        dep = Dependency(kind="link", request="./a.md", loc=SourceSpan(1, 0, 1, 5))
        n.add_dependency(dep)
        self.assertEqual(n.dependencies, [dep])

    def test_independent_mutable_defaults(self) -> None:
        """default_factory must give each node its own dict/list (no shared state)."""
        a = Node(id="a", kind=NodeKind.MARKDOWN)
        b = Node(id="b", kind=NodeKind.MARKDOWN)
        a.meta["k"] = 1
        a.hashes["raw"] = "deadbeef"
        a.add_dependency(Dependency(kind="link", request="x"))
        self.assertEqual(b.meta, {})
        self.assertEqual(b.hashes, {})
        self.assertEqual(b.dependencies, [])

    def test_asset_output_path(self) -> None:
        asset = Asset(id="img", kind=NodeKind.ASSET, output_path="img/logo.png")
        self.assertEqual(asset.output_path, "img/logo.png")

    def test_dependency_is_frozen_and_hashable(self) -> None:
        d1 = Dependency(kind="wikilink", request="[[Bar]]", meta=(("k", "v"),))
        d2 = Dependency(kind="wikilink", request="[[Bar]]", meta=(("k", "v"),))
        self.assertEqual(d1, d2)
        self.assertEqual(hash(d1), hash(d2))
        self.assertEqual({d1, d2}, {d1})  # usable in sets for dependency diffing
