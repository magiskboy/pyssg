"""Unit tests: dependency diffing."""

from __future__ import annotations

import unittest

from pyssg.core.build import Build, ResolveContext
from pyssg.core.builder import Builder
from pyssg.core.dependency import Connection, Dependency
from pyssg.core.incremental.depdiff import apply_dep_diff, resolve_pending
from pyssg.core.incremental.invalidation import WorkList
from pyssg.core.node import Document
from pyssg.core.types import ConnectionKind, NodeKind, Phase


def _build_with_a_to_b() -> tuple[Builder, Build, Dependency, Connection]:
    builder = Builder()
    build = builder.create_build()
    a = Document(id="a", kind=NodeKind.MARKDOWN)
    dep = Dependency(kind="link", request="b")
    a.dependencies = [dep]
    build.graph.add_node(a)
    build.graph.add_node(Document(id="b", kind=NodeKind.MARKDOWN))
    conn = build.create_connection(
        src="a",
        dst="b",
        kind=ConnectionKind.LINK,
        dependency=dep,
        sensitive_to=frozenset({"title"}),
        restart_phase=Phase.RENDER,
        reverse=True,
    )
    return builder, build, dep, conn


class DepDiffTest(unittest.TestCase):
    def test_removed_dependency_disconnects_and_wakes_dst(self) -> None:
        _, build, _dep, conn = _build_with_a_to_b()
        work = WorkList()
        apply_dep_diff(build, "a", [], work)  # all deps removed
        self.assertEqual(build.graph.out_edges("a"), [])
        self.assertEqual(build.graph.in_edges("b"), [])
        self.assertIs(work.get("b"), Phase.RENDER)  # lost backlink -> re-render
        self.assertEqual(conn.dst, "b")  # the connection object is unchanged, just unlinked

    def test_added_dependency_flags_resolve(self) -> None:
        _, build, dep, _conn = _build_with_a_to_b()
        work = WorkList()
        new = Dependency(kind="link", request="c")
        apply_dep_diff(build, "a", [dep, new], work)
        self.assertIs(work.get("a"), Phase.RESOLVE)
        a = build.graph.get("a")
        self.assertIsNotNone(a)
        assert a is not None  # narrow for the type checker
        self.assertIn(new, a.dependencies)

    def test_resolve_pending_connects_via_hook(self) -> None:
        builder = Builder()
        build = builder.create_build()
        a = Document(id="a", kind=NodeKind.MARKDOWN)
        dep = Dependency(kind="link", request="b")
        a.dependencies = [dep]
        build.graph.add_node(a)
        build.graph.add_node(Document(id="b", kind=NodeKind.MARKDOWN))

        @build.hooks.resolve.tap("test")
        def _resolve(d: Dependency, ctx: ResolveContext) -> Connection | None:
            # Resolvers construct a Connection; the engine registers it.
            return Connection(
                src=ctx.origin,
                dst="b",
                kind=ConnectionKind.LINK,
                dependency=d,
                sensitive_to=frozenset({"title"}),
                restart_phase=Phase.RENDER,
                reverse=True,
            )

        work = WorkList()
        resolve_pending(build, ["a"], work)
        self.assertIsNotNone(build.graph.connection_of("a", dep))
        self.assertIs(work.get("b"), Phase.RENDER)  # new reverse edge -> dst re-renders
