"""Unit tests for the Listing plugin."""

from __future__ import annotations

import unittest
from pathlib import Path

from pyssg.build import Build
from pyssg.config import Config
from pyssg.content import collections, is_generated
from pyssg.models import Source
from pyssg_plugins.listing import Listing


def src(rel: str, url: str, **frontmatter: object) -> Source:
    s = Source(path=Path(rel), relpath=Path(rel), frontmatter=dict(frontmatter))
    s.meta["url"] = url
    return s


def build_with(collection_name: str, kind: str, pages: list[Source]) -> Build:
    from pyssg.content import Collection

    build = Build(config=Config(src=Path("content"), out=Path("public")))
    collections(build)[collection_name] = Collection(
        name=collection_name, kind=kind, pages=pages
    )
    return build


def generated_pages(build: Build) -> list[Source]:
    return [s for s in build.sources if is_generated(s)]


class ConstructorTest(unittest.TestCase):
    def test_requires_exactly_one_target(self) -> None:
        with self.assertRaises(ValueError):
            Listing(base_url="/x/")
        with self.assertRaises(ValueError):
            Listing(collection="a", kind="tag", base_url="/x/")


class SingleCollectionTest(unittest.TestCase):
    def test_creates_one_page_without_pagination(self) -> None:
        build = build_with(
            "blog",
            "folder",
            [src("blog/a.md", "/blog/a/"), src("blog/b.md", "/blog/b/")],
        )
        Listing(collection="blog", base_url="/blog/", title="Blog")._collect(build)

        pages = generated_pages(build)
        self.assertEqual(len(pages), 1)
        page = pages[0]
        self.assertEqual(page.meta["url"], "/blog/")
        self.assertEqual(page.meta["output_path"], "blog/index.html")
        self.assertEqual(page.frontmatter["title"], "Blog")
        entries = page.meta["entries"]
        assert isinstance(entries, list)
        self.assertEqual([i["url"] for i in entries], ["/blog/a/", "/blog/b/"])

    def test_missing_collection_creates_nothing(self) -> None:
        build = build_with("blog", "folder", [])
        Listing(collection="nope", base_url="/x/")._collect(build)
        self.assertEqual(generated_pages(build), [])


class PaginationTest(unittest.TestCase):
    def test_splits_into_pages(self) -> None:
        pages = [src(f"p{i}.md", f"/p{i}/") for i in range(5)]
        build = build_with("blog", "folder", pages)
        Listing(collection="blog", base_url="/blog/", page_size=2)._collect(build)

        generated = generated_pages(build)
        urls = [g.meta["url"] for g in generated]
        self.assertEqual(urls, ["/blog/", "/blog/page/2/", "/blog/page/3/"])

    def test_paginator_links(self) -> None:
        pages = [src(f"p{i}.md", f"/p{i}/") for i in range(5)]
        build = build_with("blog", "folder", pages)
        Listing(collection="blog", base_url="/blog/", page_size=2)._collect(build)
        generated = generated_pages(build)

        first = generated[0].meta["paginator"]
        second = generated[1].meta["paginator"]
        third = generated[2].meta["paginator"]
        assert isinstance(first, dict)
        assert isinstance(second, dict)
        assert isinstance(third, dict)

        self.assertEqual(first["prev_url"], None)
        self.assertEqual(first["next_url"], "/blog/page/2/")
        self.assertEqual(second["prev_url"], "/blog/")
        self.assertEqual(second["next_url"], "/blog/page/3/")
        self.assertEqual(third["next_url"], None)
        self.assertEqual(third["total_pages"], 3)

    def test_page_size_distribution(self) -> None:
        pages = [src(f"p{i}.md", f"/p{i}/") for i in range(5)]
        build = build_with("blog", "folder", pages)
        Listing(collection="blog", base_url="/blog/", page_size=2)._collect(build)
        generated = generated_pages(build)
        counts = [
            len(g.meta["entries"])
            for g in generated
            if isinstance(g.meta["entries"], list)
        ]
        self.assertEqual(counts, [2, 2, 1])


class ByKindTest(unittest.TestCase):
    def test_one_page_per_collection_of_kind(self) -> None:
        from pyssg.content import Collection

        build = Build(config=Config(src=Path("content"), out=Path("public")))
        reg = collections(build)
        reg["python"] = Collection(
            name="python", kind="tag", pages=[src("a.md", "/a/")]
        )
        reg["web dev"] = Collection(
            name="web dev", kind="tag", pages=[src("b.md", "/b/")]
        )
        reg["blog"] = Collection(name="blog", kind="folder", pages=[src("c.md", "/c/")])

        Listing(kind="tag", base_url="/tags/:name/", title=":name")._collect(build)

        generated = generated_pages(build)
        urls = sorted(str(g.meta["url"]) for g in generated)
        self.assertEqual(urls, ["/tags/python/", "/tags/web-dev/"])
        titles = {str(g.frontmatter["title"]) for g in generated}
        self.assertEqual(titles, {"python", "web dev"})


if __name__ == "__main__":
    unittest.main()
