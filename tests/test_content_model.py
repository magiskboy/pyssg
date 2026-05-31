"""Unit tests for the shared tier-2 content model."""

from __future__ import annotations

import unittest
from pathlib import Path

from pyssg.build import Build
from pyssg.config import Config
from pyssg.content import (
    Collection,
    NavNode,
    collections,
    is_draft,
    is_generated,
    menus,
    site,
)
from pyssg.models import Source


def make_build(options: dict[str, object] | None = None) -> Build:
    config = Config(src=Path("content"), out=Path("public"), options=options or {})
    return Build(config=config)


class SiteTest(unittest.TestCase):
    def test_seeds_from_config_options(self) -> None:
        build = make_build({"title": "My Site", "base_url": "/"})
        self.assertEqual(site(build)["title"], "My Site")

    def test_returns_same_dict_on_repeat_access(self) -> None:
        build = make_build()
        first = site(build)
        first["added"] = 1
        self.assertIs(site(build), first)
        self.assertEqual(site(build)["added"], 1)


class CollectionsTest(unittest.TestCase):
    def test_created_empty_and_persisted(self) -> None:
        build = make_build()
        reg = collections(build)
        self.assertEqual(reg, {})

        reg["python"] = Collection(name="python", kind="tag")
        self.assertIs(collections(build), reg)
        self.assertIn("python", collections(build))

    def test_collection_holds_ordered_pages(self) -> None:
        a = Source(path=Path("a.md"), relpath=Path("a.md"))
        b = Source(path=Path("b.md"), relpath=Path("b.md"))
        collection = Collection(name="posts", kind="custom", pages=[a, b])
        self.assertEqual(
            [p.relpath for p in collection.pages], [Path("a.md"), Path("b.md")]
        )


class MenusTest(unittest.TestCase):
    def test_nested_nav_nodes(self) -> None:
        build = make_build()
        reg = menus(build)
        reg["main"] = [
            NavNode(title="Home", url="/", order=0),
            NavNode(
                title="Docs",
                url="/docs/",
                order=1,
                children=[NavNode(title="Intro", url="/docs/intro/")],
            ),
        ]
        self.assertIs(menus(build), reg)
        self.assertEqual(menus(build)["main"][1].children[0].title, "Intro")


class FlagTest(unittest.TestCase):
    def test_is_generated(self) -> None:
        source = Source(path=Path("a.md"), relpath=Path("a.md"))
        self.assertFalse(is_generated(source))
        source.meta["generated"] = True
        self.assertTrue(is_generated(source))

    def test_is_draft(self) -> None:
        source = Source(path=Path("a.md"), relpath=Path("a.md"))
        self.assertFalse(is_draft(source))
        source.frontmatter["draft"] = True
        self.assertTrue(is_draft(source))


if __name__ == "__main__":
    unittest.main()
