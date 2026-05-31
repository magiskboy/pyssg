"""Unit tests for the Markdown and Template plugins (third party libs)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pyssg.build import Build
from pyssg.config import Config
from pyssg.models import Source
from pyssg_plugins.markdown import Markdown
from pyssg_plugins.template import Template


def make_build(src: Path, out: Path) -> Build:
    return Build(config=Config(src=src, out=out))


class MarkdownTest(unittest.TestCase):
    def test_renders_body_to_html(self) -> None:
        source = Source(path=Path("a.md"), relpath=Path("a.md"), body="# Title")
        build = make_build(Path("content"), Path("out"))

        result = Markdown()._transform(source, build)

        self.assertIn("<h1>Title</h1>", result.content)

    def test_paragraph(self) -> None:
        source = Source(path=Path("a.md"), relpath=Path("a.md"), body="hello world")
        build = make_build(Path("content"), Path("out"))

        Markdown()._transform(source, build)

        self.assertEqual(source.content, "<p>hello world</p>")


class TemplateTest(unittest.TestCase):
    def test_wraps_content_in_layout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "layouts").mkdir()
            (root / "layouts" / "default.html").write_text(
                "<html>{{ page.title }}:{{ content }}</html>", encoding="utf-8"
            )
            src = root / "content"
            src.mkdir()

            source = Source(
                path=src / "a.md",
                relpath=Path("a.md"),
                content="<p>hi</p>",
                frontmatter={"title": "T"},
            )
            build = make_build(src, root / "out")

            Template()._render(source, build)

            self.assertEqual(len(build.outputs), 1)
            output = build.outputs[0]
            self.assertEqual(output.path, Path("a.html"))
            self.assertEqual(output.content, "<html>T:<p>hi</p></html>")

    def test_layout_from_frontmatter(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "layouts").mkdir()
            (root / "layouts" / "post.html").write_text(
                "POST:{{ content }}", encoding="utf-8"
            )
            src = root / "content"
            src.mkdir()

            source = Source(
                path=src / "a.md",
                relpath=Path("a.md"),
                content="body",
                frontmatter={"layout": "post.html"},
            )
            build = make_build(src, root / "out")

            Template()._render(source, build)

            self.assertEqual(build.outputs[0].content, "POST:body")

    def test_site_context_available(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "layouts").mkdir()
            (root / "layouts" / "default.html").write_text(
                "{{ site.name }}|{{ menus.main }}", encoding="utf-8"
            )
            src = root / "content"
            src.mkdir()

            source = Source(path=src / "a.md", relpath=Path("a.md"), content="x")
            build = make_build(src, root / "out")
            build.meta["site"] = {"name": "MySite"}
            build.meta["menus"] = {"main": "MENU"}

            Template()._render(source, build)

            self.assertEqual(build.outputs[0].content, "MySite|MENU")

    def test_site_defaults_to_config_options(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "layouts").mkdir()
            (root / "layouts" / "default.html").write_text(
                "{{ site.title }}", encoding="utf-8"
            )
            src = root / "content"
            src.mkdir()

            source = Source(path=src / "a.md", relpath=Path("a.md"), content="x")
            config = Config(src=src, out=root / "out", options={"title": "FromOptions"})
            build = Build(config=config)

            Template()._render(source, build)

            self.assertEqual(build.outputs[0].content, "FromOptions")

    def test_output_path_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "layouts").mkdir()
            (root / "layouts" / "default.html").write_text(
                "{{ content }}", encoding="utf-8"
            )
            src = root / "content"
            src.mkdir()

            source = Source(path=src / "a.md", relpath=Path("a.md"), content="x")
            source.meta["output_path"] = "blog/custom/index.html"
            build = make_build(src, root / "out")

            Template()._render(source, build)

            self.assertEqual(build.outputs[0].path, Path("blog/custom/index.html"))


if __name__ == "__main__":
    unittest.main()
