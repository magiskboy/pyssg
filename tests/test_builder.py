"""Unit tests for the Builder and the build lifecycle."""

from __future__ import annotations

import unittest
from pathlib import Path

from pyssg.build import Build
from pyssg.builder import Builder
from pyssg.config import Config
from pyssg.errors import BuildError
from pyssg.models import Output, Source


def make_config(plugins: list[object]) -> Config:
    # A plugin only needs an apply method; narrow the type for use in tests.
    from pyssg.plugin import Plugin

    typed: list[Plugin] = [p for p in plugins if isinstance(p, Plugin)]
    return Config(src=Path("content"), out=Path("public"), plugins=typed)


class RecordingPlugin:
    """A plugin that records the order in which lifecycle stages are called."""

    def __init__(self, log: list[str]) -> None:
        self.log = log

    def apply(self, builder: Builder) -> None:
        builder.hooks.initialize.tap("rec", lambda _b: self.log.append("initialize"))
        builder.hooks.before_run.tap("rec", lambda _b: self.log.append("before_run"))
        builder.hooks.discover.tap("rec", self._discover)
        builder.hooks.load.tap("rec", lambda _s, _b: self.log.append("load"))
        builder.hooks.parse.tap("rec", lambda _s, _b: self.log.append("parse"))
        builder.hooks.collect.tap("rec", lambda _b: self.log.append("collect"))
        builder.hooks.transform.tap("rec", self._transform)
        builder.hooks.render.tap("rec", lambda _s, _b: self.log.append("render"))
        builder.hooks.generate.tap("rec", lambda _b: self.log.append("generate"))
        builder.hooks.optimize.tap("rec", lambda _b: self.log.append("optimize"))
        builder.hooks.emit.tap("rec", lambda _b: self.log.append("emit"))
        builder.hooks.after_emit.tap("rec", lambda _b: self.log.append("after_emit"))
        builder.hooks.done.tap("rec", lambda _b: self.log.append("done"))

    def _discover(self, build: Build) -> None:
        self.log.append("discover")
        build.sources.append(Source(path=Path("a.md"), relpath=Path("a.md")))

    def _transform(self, source: Source, build: Build) -> Source:
        self.log.append("transform")
        return source


class LifecycleOrderTest(unittest.TestCase):
    def test_initialize_runs_at_construction(self) -> None:
        log: list[str] = []
        Builder(make_config([RecordingPlugin(log)]))
        self.assertEqual(log, ["initialize"])

    def test_full_lifecycle_order(self) -> None:
        log: list[str] = []
        builder = Builder(make_config([RecordingPlugin(log)]))
        builder.run()

        self.assertEqual(
            log,
            [
                "initialize",
                "before_run",
                "discover",
                "load",
                "parse",
                "collect",
                "transform",
                "render",
                "generate",
                "optimize",
                "emit",
                "after_emit",
                "done",
            ],
        )

    def test_per_source_hooks_run_once_per_source(self) -> None:
        log: list[str] = []

        class TwoSourcePlugin(RecordingPlugin):
            def _discover(self, build: Build) -> None:
                self.log.append("discover")
                build.sources.append(Source(path=Path("a.md"), relpath=Path("a.md")))
                build.sources.append(Source(path=Path("b.md"), relpath=Path("b.md")))

        builder = Builder(make_config([TwoSourcePlugin(log)]))
        builder.run()

        self.assertEqual(log.count("load"), 2)
        self.assertEqual(log.count("render"), 2)
        self.assertEqual(log.count("discover"), 1)


class PhasedPassesTest(unittest.TestCase):
    def test_all_sources_parsed_before_any_render(self) -> None:
        # Phased passes: parse sweeps every source before render begins, so a
        # render tap can see the whole site (needed for navigation/collections).
        order: list[str] = []

        class Plugin:
            def apply(self, builder: Builder) -> None:
                builder.hooks.discover.tap("src", self._discover)
                builder.hooks.parse.tap(
                    "p", lambda s, _b: order.append(f"parse:{s.relpath}")
                )
                builder.hooks.render.tap(
                    "r", lambda s, _b: order.append(f"render:{s.relpath}")
                )

            def _discover(self, build: Build) -> None:
                build.sources.append(Source(path=Path("a.md"), relpath=Path("a.md")))
                build.sources.append(Source(path=Path("b.md"), relpath=Path("b.md")))

        Builder(make_config([Plugin()])).run()

        self.assertEqual(
            order,
            ["parse:a.md", "parse:b.md", "render:a.md", "render:b.md"],
        )

    def test_render_can_read_site_context_from_collect(self) -> None:
        # collect builds build.meta before render; render reads it.
        class Plugin:
            def apply(self, builder: Builder) -> None:
                builder.hooks.discover.tap("src", self._discover)
                builder.hooks.collect.tap("col", self._collect)
                builder.hooks.render.tap("r", self._render)

            def _discover(self, build: Build) -> None:
                build.sources.append(Source(path=Path("a.md"), relpath=Path("a.md")))
                build.sources.append(Source(path=Path("b.md"), relpath=Path("b.md")))

            def _collect(self, build: Build) -> None:
                build.meta["count"] = len(build.sources)

            def _render(self, source: Source, build: Build) -> None:
                source.meta["site_count"] = build.meta["count"]

        build = Builder(make_config([Plugin()])).run()

        self.assertEqual(build.sources[0].meta["site_count"], 2)
        self.assertEqual(build.sources[1].meta["site_count"], 2)

    def test_generate_can_append_derived_outputs(self) -> None:
        # generate runs after render and can synthesize pages not backed by a
        # source file (tag index, sitemap, pagination...).
        class Plugin:
            def apply(self, builder: Builder) -> None:
                builder.hooks.discover.tap("src", self._discover)
                builder.hooks.render.tap("r", self._render)
                builder.hooks.generate.tap("g", self._generate)

            def _discover(self, build: Build) -> None:
                build.sources.append(Source(path=Path("a.md"), relpath=Path("a.md")))

            def _render(self, source: Source, build: Build) -> None:
                build.outputs.append(Output(path=Path("a.html"), content="a"))

            def _generate(self, build: Build) -> None:
                build.outputs.append(Output(path=Path("sitemap.xml"), content="<x/>"))

        build = Builder(make_config([Plugin()])).run()

        paths = {o.path for o in build.outputs}
        self.assertEqual(paths, {Path("a.html"), Path("sitemap.xml")})


class TransformPipelineTest(unittest.TestCase):
    def test_transform_is_waterfall_across_plugins(self) -> None:
        class SourcePlugin:
            def apply(self, builder: Builder) -> None:
                builder.hooks.discover.tap("src", self._discover)

            def _discover(self, build: Build) -> None:
                build.sources.append(
                    Source(path=Path("a.md"), relpath=Path("a.md"), body="hi")
                )

        class UpperPlugin:
            def apply(self, builder: Builder) -> None:
                builder.hooks.transform.tap("upper", self._transform, stage=0)

            def _transform(self, source: Source, build: Build) -> Source:
                source.content = source.body.upper()
                return source

        class WrapPlugin:
            def apply(self, builder: Builder) -> None:
                builder.hooks.transform.tap("wrap", self._transform, stage=10)

            def _transform(self, source: Source, build: Build) -> Source:
                source.content = f"[{source.content}]"
                return source

        builder = Builder(make_config([SourcePlugin(), UpperPlugin(), WrapPlugin()]))
        build = builder.run()

        self.assertEqual(build.sources[0].content, "[HI]")


class StageOrderingTest(unittest.TestCase):
    def test_optimize_respects_stage(self) -> None:
        order: list[str] = []

        class Plugin:
            def apply(self, builder: Builder) -> None:
                builder.hooks.optimize.tap(
                    "late", lambda _b: order.append("late"), stage=100
                )
                builder.hooks.optimize.tap(
                    "early", lambda _b: order.append("early"), stage=-100
                )

        builder = Builder(make_config([Plugin()]))
        builder.run()

        self.assertEqual(order, ["early", "late"])


class FailureTest(unittest.TestCase):
    def test_failed_hook_runs_and_error_propagates(self) -> None:
        captured: list[Exception] = []

        class BoomPlugin:
            def apply(self, builder: Builder) -> None:
                builder.hooks.discover.tap("boom", self._boom)
                builder.hooks.failed.tap("catch", self._catch)

            def _boom(self, build: Build) -> None:
                raise RuntimeError("boom")

            def _catch(self, error: Exception, build: Build) -> None:
                captured.append(error)

        builder = Builder(make_config([BoomPlugin()]))
        with self.assertRaises(BuildError) as ctx:
            builder.run()

        # Errors are normalized to BuildError, tagged with the failing stage and
        # chained to the original exception as __cause__.
        self.assertEqual(ctx.exception.stage, "discover")
        self.assertIsInstance(ctx.exception.__cause__, RuntimeError)
        self.assertEqual(len(captured), 1)
        self.assertIsInstance(captured[0], BuildError)


class EmitTest(unittest.TestCase):
    def test_plugin_can_collect_outputs(self) -> None:
        class Plugin:
            def apply(self, builder: Builder) -> None:
                builder.hooks.discover.tap("src", self._discover)
                builder.hooks.render.tap("render", self._render)

            def _discover(self, build: Build) -> None:
                build.sources.append(Source(path=Path("a.md"), relpath=Path("a.md")))

            def _render(self, source: Source, build: Build) -> None:
                build.outputs.append(
                    Output(path=Path("a.html"), content="<p>a</p>", source=source)
                )

        builder = Builder(make_config([Plugin()]))
        build = builder.run()

        self.assertEqual(len(build.outputs), 1)
        self.assertEqual(build.outputs[0].path, Path("a.html"))


if __name__ == "__main__":
    unittest.main()
