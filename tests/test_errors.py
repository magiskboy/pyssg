"""Tests for structured build errors, located reporting and the dev overlay."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pyssg.build import Build
from pyssg.builder import Builder
from pyssg.config import Config, load_config
from pyssg.errors import (
    BuildError,
    SourceLocation,
    read_snippet,
    render_html_overlay,
    render_terminal,
    want_traceback,
    wrap,
)
from pyssg_cli.presets import docs
from pyssg_plugins.dev_server import DevServer


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class BuildErrorTest(unittest.TestCase):
    def test_with_context_only_fills_missing(self) -> None:
        error = BuildError("boom", stage="render")
        error.with_context(stage="parse", source_path=Path("a.md"))
        self.assertEqual(error.stage, "render")  # not overwritten
        self.assertEqual(error.source_path, Path("a.md"))  # filled in

    def test_wrap_chains_cause(self) -> None:
        original = ValueError("bad")
        wrapped = wrap(original, stage="parse", source_path=Path("a.md"))
        self.assertIsInstance(wrapped, BuildError)
        self.assertEqual(wrapped.stage, "parse")
        self.assertIs(wrapped.__cause__, original)

    def test_wrap_preserves_existing_build_error(self) -> None:
        error = BuildError("x")
        wrapped = wrap(error, stage="render", source_path=Path("a.md"))
        self.assertIs(wrapped, error)
        self.assertEqual(wrapped.stage, "render")


class SnippetTest(unittest.TestCase):
    def test_read_snippet_marks_line(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp) / "f.txt"
            file.write_text("a\nb\nc\nd\ne\n", encoding="utf-8")
            snippet = read_snippet(file, 3, context=1)
            assert snippet is not None
            self.assertIn("> 3 | c", snippet)
            self.assertIn("  2 | b", snippet)

    def test_read_snippet_missing_file(self) -> None:
        self.assertIsNone(read_snippet(Path("/nope/none.txt"), 1))


class RenderTest(unittest.TestCase):
    def test_terminal_shows_location_and_message(self) -> None:
        error = BuildError(
            "Template syntax error: unexpected",
            stage="render",
            source_path=Path("content/a.md"),
            location=SourceLocation(file=Path("layouts/base.html"), line=12),
        )
        text = render_terminal(error, color=False)
        self.assertIn("Build failed", text)
        self.assertIn("content/a.md", text)
        self.assertIn("layouts/base.html:12", text)
        self.assertIn("unexpected", text)

    def test_overlay_escapes_message(self) -> None:
        error = BuildError("oops <script>", location=SourceLocation(file=Path("x")))
        html = render_html_overlay(error)
        self.assertIn("BUILD FAILED", html)
        self.assertIn("oops &lt;script&gt;", html)
        self.assertNotIn("<script>", html)

    def test_want_traceback_flag(self) -> None:
        self.assertTrue(want_traceback(True))


class ConfigErrorTest(unittest.TestCase):
    def test_missing_config_is_build_error(self) -> None:
        with self.assertRaises(BuildError) as ctx:
            load_config(Path("/nope/pyssg.config.py"))
        self.assertEqual(ctx.exception.stage, "config")

    def test_syntax_error_reports_location(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "pyssg.config.py"
            cfg.write_text("def config(:\n    pass\n", encoding="utf-8")
            with self.assertRaises(BuildError) as ctx:
                load_config(cfg)
            self.assertIsNotNone(ctx.exception.location)


class TemplateErrorIntegrationTest(unittest.TestCase):
    def _build(self, layout: str) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root / "content" / "index.md", "---\ntitle: Hi\n---\nBody\n")
            write(root / "layouts" / "default.html", layout)
            config = Config(src=root / "content", out=root / "public", plugins=docs())
            Builder(config).run()

    def test_syntax_error_points_at_layout(self) -> None:
        with self.assertRaises(BuildError) as ctx:
            self._build("{% for x %}{% endfor %}")  # missing 'in'
        error = ctx.exception
        self.assertEqual(error.stage, "render")
        self.assertIsNotNone(error.location)
        assert error.location is not None
        self.assertEqual(error.location.file.name, "default.html")
        self.assertIn("syntax", error.message.lower())

    def test_runtime_error_is_located(self) -> None:
        with self.assertRaises(BuildError) as ctx:
            self._build("{{ missing_function() }}")  # calling Undefined raises
        error = ctx.exception
        self.assertEqual(error.stage, "render")
        self.assertIsNotNone(error.location)
        assert error.location is not None
        self.assertEqual(error.location.file.name, "default.html")


class DevServerOverlayTest(unittest.TestCase):
    def _build(self) -> Build:
        return Build(config=Config(src=Path("content"), out=Path("public")))

    def test_failed_after_start_sets_error_and_bumps_token(self) -> None:
        server = DevServer()
        server._started = True
        token = server._token
        server._on_failed(BuildError("boom", stage="render"), self._build())
        self.assertIsNotNone(server._error)
        self.assertEqual(server._token, token + 1)

    def test_done_clears_error(self) -> None:
        server = DevServer()
        server._started = True
        server._error = BuildError("boom")
        server._on_done(self._build())
        self.assertIsNone(server._error)


if __name__ == "__main__":
    unittest.main()
