"""Unit tests: Builder/Build skeleton + Plugin.apply."""

from __future__ import annotations

import unittest

from pyssg.core.build import Build
from pyssg.core.builder import Builder
from pyssg.core.dependency import Dependency
from pyssg.core.node import Document, Node
from pyssg.core.types import ConnectionKind, NodeKind, Phase
from pyssg.plugins.api import Plugin, PluginContext


class _RecordingPlugin:
    name = "recording"
    cache_version = "1.0.0"

    def __init__(self) -> None:
        self.applied_to: Builder | None = None

    def apply(self, builder: Builder) -> None:
        self.applied_to = builder

        @builder.hooks.this_compilation.tap(self.name)
        def _(build: Build) -> None:
            @build.parsers.for_("markdown").after_parse.tap(self.name)
            def _on_parse(node: Node) -> None:
                node.meta["seen_by"] = self.name


class BuilderTest(unittest.TestCase):
    def test_plugin_protocol_is_runtime_checkable(self) -> None:
        plugin = _RecordingPlugin()
        self.assertIsInstance(plugin, Plugin)

    def test_use_applies_plugin_once(self) -> None:
        builder = Builder()
        plugin = _RecordingPlugin()
        builder.use(plugin)
        self.assertIs(plugin.applied_to, builder)

    def test_plugin_wiring_flows_through_build(self) -> None:
        builder = Builder()
        builder.use(_RecordingPlugin())
        build = builder.create_build()
        # Fire the per-build wiring the plugin registered on this_compilation.
        builder.hooks.this_compilation.call(build)
        # The parser slot tap should now decorate a parsed node.
        node = Document(id="d", kind=NodeKind.MARKDOWN)
        build.parsers.for_("markdown").after_parse.call(node)
        self.assertEqual(node.meta["seen_by"], "recording")

    def test_create_connection_registers_edge(self) -> None:
        builder = Builder()
        build = builder.create_build()
        build.graph.add_node(Document(id="a", kind=NodeKind.MARKDOWN))
        conn = build.create_connection(
            src="a",
            dst="b",
            kind=ConnectionKind.LINK,
            dependency=Dependency(kind="link", request="./b.md"),
            sensitive_to=frozenset({"title", "url", "exists"}),
            restart_phase=Phase.RENDER,
            reverse=True,
        )
        self.assertEqual(build.graph.out_edges("a"), [conn])
        self.assertEqual(build.graph.in_edges("b"), [conn])

    def test_plugin_context_holds_builder(self) -> None:
        builder = Builder()
        ctx = PluginContext(builder=builder)
        self.assertIs(ctx.builder, builder)
