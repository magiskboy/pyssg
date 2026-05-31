"""Unit tests for the Navigation plugin."""

from __future__ import annotations

import unittest
from pathlib import Path

from pyssg.build import Build
from pyssg.config import Config
from pyssg.content import menus
from pyssg.models import Source
from pyssg_plugins.navigation import Navigation


def src(rel: str, url: str, **frontmatter: object) -> Source:
    s = Source(path=Path(rel), relpath=Path(rel), frontmatter=dict(frontmatter))
    s.meta["url"] = url
    return s


def run(plugin: Navigation, sources: list[Source]) -> Build:
    build = Build(config=Config(src=Path("content"), out=Path("public")))
    build.sources = sources
    plugin._collect(build)
    return build


class FrontmatterMenuTest(unittest.TestCase):
    def test_flat_menu_from_declarations(self) -> None:
        build = run(
            Navigation(mode="frontmatter"),
            [
                src("about.md", "/about/", menu="main", title="About", order=2),
                src("home.md", "/", menu="main", title="Home", order=1),
                src("secret.md", "/secret/", title="Secret"),
            ],
        )
        menu = menus(build)["main"]
        self.assertEqual([n.title for n in menu], ["Home", "About"])
        self.assertEqual([n.url for n in menu], ["/", "/about/"])

    def test_menu_list_membership(self) -> None:
        build = run(
            Navigation(menu="footer", mode="frontmatter"),
            [src("a.md", "/a/", menu=["main", "footer"], title="A")],
        )
        self.assertEqual(len(menus(build)["footer"]), 1)


class FolderTreeTest(unittest.TestCase):
    def test_builds_hierarchy(self) -> None:
        build = run(
            Navigation(mode="folder"),
            [
                src("index.md", "/", title="Home", order=0),
                src("guide/index.md", "/guide/", title="Guide", order=1),
                src("guide/install.md", "/guide/install/", title="Install", order=1),
                src("guide/usage.md", "/guide/usage/", title="Usage", order=2),
            ],
        )
        tree = menus(build)["main"]
        # Root index is the home page, not a menu node; only the guide section remains.
        self.assertEqual([n.title for n in tree], ["Guide"])
        guide = tree[0]
        self.assertEqual(guide.url, "/guide/")
        self.assertEqual([c.title for c in guide.children], ["Install", "Usage"])

    def test_section_without_index_becomes_header(self) -> None:
        build = run(
            Navigation(mode="folder"),
            [src("api/ref.md", "/api/ref/", title="Ref")],
        )
        tree = menus(build)["main"]
        self.assertEqual(tree[0].title, "Api")
        self.assertEqual(tree[0].url, "")
        self.assertEqual(tree[0].children[0].title, "Ref")

    def test_titleize_from_filename(self) -> None:
        build = run(
            Navigation(mode="folder"),
            [src("getting-started.md", "/getting-started/")],
        )
        self.assertEqual(menus(build)["main"][0].title, "Getting Started")


class SequentialTest(unittest.TestCase):
    def test_prev_next_links(self) -> None:
        a = src("guide/a.md", "/guide/a/", title="A", order=1)
        b = src("guide/b.md", "/guide/b/", title="B", order=2)
        c = src("guide/c.md", "/guide/c/", title="C", order=3)
        run(Navigation(mode="folder", sequential=True), [a, b, c])

        self.assertNotIn("prev", a.meta)
        assert isinstance(a.meta["next"], dict)
        self.assertEqual(a.meta["next"]["url"], "/guide/b/")
        assert isinstance(b.meta["prev"], dict)
        assert isinstance(b.meta["next"], dict)
        self.assertEqual(b.meta["prev"]["url"], "/guide/a/")
        self.assertEqual(b.meta["next"]["url"], "/guide/c/")
        self.assertNotIn("next", c.meta)


class OverrideTest(unittest.TestCase):
    def test_explicit_items(self) -> None:
        build = run(
            Navigation(
                items=[
                    {"title": "Home", "url": "/"},
                    {
                        "title": "Docs",
                        "url": "/docs/",
                        "children": [{"title": "Intro", "url": "/docs/intro/"}],
                    },
                ]
            ),
            [],
        )
        tree = menus(build)["main"]
        self.assertEqual([n.title for n in tree], ["Home", "Docs"])
        self.assertEqual(tree[1].children[0].url, "/docs/intro/")


class FilterTest(unittest.TestCase):
    def test_drafts_and_generated_excluded(self) -> None:
        draft = src("d.md", "/d/", menu="main", title="D", draft=True)
        generated = src("g.md", "/g/", menu="main", title="G")
        generated.meta["generated"] = True
        normal = src("n.md", "/n/", menu="main", title="N")
        build = run(Navigation(mode="frontmatter"), [draft, generated, normal])
        self.assertEqual([n.title for n in menus(build)["main"]], ["N"])


if __name__ == "__main__":
    unittest.main()
