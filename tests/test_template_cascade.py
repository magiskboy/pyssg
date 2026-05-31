"""Unit tests for the Template lookup cascade and partial() global."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pyssg.build import Build
from pyssg.config import Config
from pyssg.models import Source
from pyssg_plugins.template import Template


def make_build(root: Path) -> Build:
    src = root / "content"
    src.mkdir(parents=True, exist_ok=True)
    return Build(config=Config(src=src, out=root / "out"))


def write_layout(root: Path, name: str, body: str) -> None:
    path = root / "layouts" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def page(relpath: str, **frontmatter: object) -> Source:
    return Source(
        path=Path(relpath),
        relpath=Path(relpath),
        content="BODY",
        frontmatter=dict(frontmatter),
    )


class CandidatesTest(unittest.TestCase):
    def test_single_page_order(self) -> None:
        names = Template()._candidates(page("blog/post.md"))
        self.assertEqual(
            names,
            ["blog/single.html", "_default/single.html", "single.html", "default.html"],
        )

    def test_explicit_layout_first(self) -> None:
        names = Template()._candidates(page("blog/post.md", layout="custom.html"))
        self.assertEqual(names[0], "custom.html")

    def test_type_takes_priority_over_section(self) -> None:
        names = Template()._candidates(page("blog/post.md", type="article"))
        self.assertEqual(names[0], "article/single.html")
        self.assertIn("blog/single.html", names)

    def test_generated_page_is_list_kind(self) -> None:
        listing = page("tags/python.md")
        listing.meta["generated"] = True
        names = Template()._candidates(listing)
        self.assertIn("tags/list.html", names)
        self.assertIn("_default/list.html", names)
        self.assertNotIn("tags/single.html", names)

    def test_root_page_has_no_section_candidate(self) -> None:
        names = Template()._candidates(page("about.md"))
        self.assertEqual(names, ["_default/single.html", "single.html", "default.html"])

    def test_layout_without_suffix_gets_html(self) -> None:
        names = Template()._candidates(page("a.md", layout="custom"))
        self.assertEqual(names[0], "custom.html")


class CascadeRenderTest(unittest.TestCase):
    def test_picks_section_template(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_layout(root, "default.html", "DEFAULT")
            write_layout(root, "blog/single.html", "BLOG:{{ content }}")
            build = make_build(root)

            Template()._render(page("blog/post.md"), build)

            self.assertEqual(build.outputs[0].content, "BLOG:BODY")

    def test_falls_back_to_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_layout(root, "default.html", "DEFAULT:{{ content }}")
            build = make_build(root)

            Template()._render(page("blog/post.md"), build)

            self.assertEqual(build.outputs[0].content, "DEFAULT:BODY")

    def test_list_template_for_generated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_layout(root, "default.html", "D")
            write_layout(root, "_default/list.html", "LIST")
            build = make_build(root)

            listing = page("tags/python.md")
            listing.meta["generated"] = True
            Template()._render(listing, build)

            self.assertEqual(build.outputs[0].content, "LIST")


class InheritanceTest(unittest.TestCase):
    def test_native_extends_and_block(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_layout(
                root, "base.html", "<html>[{% block main %}{% endblock %}]</html>"
            )
            write_layout(
                root,
                "default.html",
                '{% extends "base.html" %}{% block main %}{{ content }}{% endblock %}',
            )
            build = make_build(root)

            Template()._render(page("a.md"), build)

            self.assertEqual(build.outputs[0].content, "<html>[BODY]</html>")


class PartialTest(unittest.TestCase):
    def test_partial_with_explicit_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_layout(root, "partials/badge.html", "<b>{{ label }}</b>")
            write_layout(
                root,
                "default.html",
                '{{ partial("partials/badge.html", {"label": "New"}) }}',
            )
            build = make_build(root)

            Template()._render(page("a.md"), build)

            self.assertEqual(build.outputs[0].content, "<b>New</b>")

    def test_partial_sees_site_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_layout(root, "partials/foot.html", "{{ site.title }}")
            write_layout(root, "default.html", '{{ partial("partials/foot.html") }}')
            src = root / "content"
            src.mkdir(parents=True, exist_ok=True)
            build = Build(
                config=Config(src=src, out=root / "out", options={"title": "Site"})
            )

            Template()._render(page("a.md"), build)

            self.assertEqual(build.outputs[0].content, "Site")

    def test_partial_name_without_suffix(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_layout(root, "partials/x.html", "X")
            write_layout(root, "default.html", '{{ partial("partials/x") }}')
            build = make_build(root)

            Template()._render(page("a.md"), build)

            self.assertEqual(build.outputs[0].content, "X")

    def test_partial_output_is_not_escaped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_layout(root, "partials/raw.html", "<i>hi</i>")
            write_layout(root, "default.html", '{{ partial("partials/raw.html") }}')
            build = make_build(root)

            Template()._render(page("a.md"), build)

            self.assertEqual(build.outputs[0].content, "<i>hi</i>")


if __name__ == "__main__":
    unittest.main()
