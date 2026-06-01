"""Unit tests: WorkList + dirty propagation with cutoff."""

from __future__ import annotations

import unittest

from pyssg.core.build import Build
from pyssg.core.builder import Builder
from pyssg.core.dependency import Dependency
from pyssg.core.incremental.invalidation import (
    WorkList,
    changed_aspects,
    propagate_aspect_changes,
)
from pyssg.core.node import Document
from pyssg.core.types import ConnectionKind, NodeKind, Phase


def _two_node_link_build() -> tuple[Builder, Build]:
    builder = Builder()
    build = builder.create_build()
    build.graph.add_node(Document(id="a", kind=NodeKind.MARKDOWN))
    build.graph.add_node(Document(id="b", kind=NodeKind.MARKDOWN))
    # a links to b, sensitive to b.title; reverse so in_edges(b) sees it.
    build.create_connection(
        src="a",
        dst="b",
        kind=ConnectionKind.LINK,
        dependency=Dependency(kind="link", request="b"),
        sensitive_to=frozenset({"title"}),
        restart_phase=Phase.RENDER,
        reverse=True,
    )
    return builder, build


class WorkListTest(unittest.TestCase):
    def test_worklist_keeps_smallest_phase(self) -> None:
        work = WorkList()
        work.add("a", Phase.RENDER)
        work.add("a", Phase.PARSE)  # deeper wins
        work.add("a", Phase.EMIT)
        self.assertIs(work.get("a"), Phase.PARSE)
        self.assertIn("a", work)
        self.assertEqual(len(work), 1)

    def test_worklist_drain_clears(self) -> None:
        work = WorkList([("a", Phase.LOAD), ("b", Phase.RENDER)])
        drained = work.drain()
        self.assertEqual(drained, {"a": Phase.LOAD, "b": Phase.RENDER})
        self.assertFalse(work)


class PropagationTest(unittest.TestCase):
    def test_changed_aspects_against_baseline(self) -> None:
        _, build = _two_node_link_build()
        b = build.graph.get("b")
        assert b is not None
        b.hashes["title"] = "t1"
        build.commit_hashes("b")
        self.assertEqual(changed_aspects(build, "b"), set())
        b.hashes["title"] = "t2"
        self.assertEqual(changed_aspects(build, "b"), {"title"})

    def test_propagate_marks_sensitive_dependent(self) -> None:
        _, build = _two_node_link_build()
        b = build.graph.get("b")
        assert b is not None
        b.hashes["title"] = "t1"
        build.commit_hashes("b")

        b.hashes["title"] = "t2"  # title changed -> a is sensitive
        work = WorkList()
        propagate_aspect_changes(build, "b", work)
        self.assertIs(work.get("a"), Phase.RENDER)

    def test_propagate_cutoff_when_insensitive_aspect_changes(self) -> None:
        _, build = _two_node_link_build()
        b = build.graph.get("b")
        assert b is not None
        b.hashes["title"] = "t1"
        b.hashes["body"] = "x1"
        build.commit_hashes("b")

        b.hashes["body"] = "x2"  # body changed, but the edge is sensitive only to title
        work = WorkList()
        propagate_aspect_changes(build, "b", work)
        self.assertNotIn("a", work)  # cutoff: dependent not woken

    def test_propagate_full_cutoff_when_nothing_changed(self) -> None:
        _, build = _two_node_link_build()
        b = build.graph.get("b")
        assert b is not None
        b.hashes["title"] = "t1"
        build.commit_hashes("b")

        work = WorkList()
        propagate_aspect_changes(build, "b", work)
        self.assertFalse(work)  # nothing changed -> no propagation at all
