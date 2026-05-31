"""Unit tests for the Collections plugin."""

from __future__ import annotations

import unittest
from pathlib import Path

from pyssg.build import Build
from pyssg.builder import Builder
from pyssg.config import Config
from pyssg.content import collections
from pyssg.models import Source
from pyssg_plugins.collections import Collections, sort_pages


def src(rel: str, **frontmatter: object) -> Source:
    return Source(path=Path(rel), relpath=Path(rel), frontmatter=dict(frontmatter))


def run(plugin: Collections, sources: list[Source]) -> Build:
    config = Config(src=Path("content"), out=Path("public"))
    build = Build(config=config)
    build.sources = sources
    plugin._collect(build)
    return build


class ByTagTest(unittest.TestCase):
    def test_groups_pages_by_tag(self) -> None:
        build = run(
            Collections(),
            [
                src("a.md", tags=["python", "web"]),
                src("b.md", tags=["python"]),
                src("c.md", tags=["web"]),
            ],
        )
        reg = collections(build)
        self.assertEqual(
            {c.relpath.name for c in reg["python"].pages}, {"a.md", "b.md"}
        )
        self.assertEqual({c.relpath.name for c in reg["web"].pages}, {"a.md", "c.md"})
        self.assertEqual(reg["python"].kind, "tag")

    def test_string_tag_is_accepted(self) -> None:
        build = run(Collections(), [src("a.md", tags="python")])
        self.assertIn("python", collections(build))


class ByFolderTest(unittest.TestCase):
    def test_groups_by_folder(self) -> None:
        build = run(
            Collections(by_tag=False, by_folder=True),
            [src("blog/a.md"), src("blog/b.md"), src("docs/c.md"), src("root.md")],
        )
        reg = collections(build)
        self.assertEqual(len(reg["blog"].pages), 2)
        self.assertEqual(reg["blog"].kind, "folder")
        self.assertIn("docs", reg)
        self.assertNotIn(".", reg)


class CustomTest(unittest.TestCase):
    def test_predicate_collection(self) -> None:
        build = run(
            Collections(
                by_tag=False,
                custom={"featured": lambda s: bool(s.frontmatter.get("featured"))},
            ),
            [src("a.md", featured=True), src("b.md"), src("c.md", featured=True)],
        )
        reg = collections(build)
        self.assertEqual(
            {c.relpath.name for c in reg["featured"].pages}, {"a.md", "c.md"}
        )
        self.assertEqual(reg["featured"].kind, "custom")


class FilterTest(unittest.TestCase):
    def test_drafts_excluded_by_default(self) -> None:
        build = run(
            Collections(),
            [src("a.md", tags=["x"]), src("b.md", tags=["x"], draft=True)],
        )
        self.assertEqual(len(collections(build)["x"].pages), 1)

    def test_drafts_included_when_requested(self) -> None:
        build = run(
            Collections(include_drafts=True),
            [src("a.md", tags=["x"]), src("b.md", tags=["x"], draft=True)],
        )
        self.assertEqual(len(collections(build)["x"].pages), 2)

    def test_generated_pages_excluded(self) -> None:
        generated = src("gen.md", tags=["x"])
        generated.meta["generated"] = True
        build = run(Collections(), [src("a.md", tags=["x"]), generated])
        self.assertEqual(len(collections(build)["x"].pages), 1)


class SortTest(unittest.TestCase):
    def test_sort_by_date_desc(self) -> None:
        pages = [
            src("a.md", date="2024-01-01"),
            src("b.md", date="2024-03-01"),
            src("c.md", date="2024-02-01"),
        ]
        ordered = sort_pages(pages, "date")
        self.assertEqual([p.relpath.name for p in ordered], ["b.md", "c.md", "a.md"])

    def test_sort_by_order_then_title(self) -> None:
        pages = [
            src("a.md", order=2, title="A"),
            src("b.md", order=1, title="B"),
            src("c.md", order=1, title="A"),
        ]
        ordered = sort_pages(pages, "order")
        self.assertEqual([p.relpath.name for p in ordered], ["c.md", "b.md", "a.md"])

    def test_auto_prefers_date_when_present(self) -> None:
        pages = [src("a.md", date="2024-01-01"), src("b.md", date="2024-02-01")]
        ordered = sort_pages(pages, "auto")
        self.assertEqual([p.relpath.name for p in ordered], ["b.md", "a.md"])

    def test_auto_falls_back_to_order(self) -> None:
        pages = [src("a.md", order=2), src("b.md", order=1)]
        ordered = sort_pages(pages, "auto")
        self.assertEqual([p.relpath.name for p in ordered], ["b.md", "a.md"])


class IntegrationTest(unittest.TestCase):
    def test_runs_through_builder_collect_pass(self) -> None:
        config = Config(
            src=Path("content"),
            out=Path("public"),
            plugins=[Collections()],
        )

        class Seed:
            def apply(self, builder: Builder) -> None:
                builder.hooks.discover.tap("seed", self._seed)

            def _seed(self, build: Build) -> None:
                build.sources.append(src("a.md", tags=["python"]))

        config.plugins.insert(0, Seed())
        build = Builder(config).run()
        self.assertIn("python", collections(build))


if __name__ == "__main__":
    unittest.main()
