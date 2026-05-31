"""Unit tests for Config validation and friendly source-directory errors."""

from __future__ import annotations

import io
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path

from pyssg.build import Build
from pyssg.builder import Builder
from pyssg.config import Config, validate_config
from pyssg.errors import BuildError
from pyssg_plugins.read_file import ReadFile


class _DummyPlugin:
    """A plugin that taps emit, so it counts as writing output."""

    def apply(self, builder: Builder) -> None:
        builder.hooks.emit.tap("dummy", lambda _b: None)


def _config(src: str, out: str, *, plugins: list[object] | None = None) -> Config:
    from pyssg.plugin import Plugin

    typed: list[Plugin] = [p for p in (plugins or []) if isinstance(p, Plugin)]
    return Config(src=Path(src), out=Path(out), plugins=typed)


class ValidateConfigTest(unittest.TestCase):
    def test_empty_plugins_is_rejected(self) -> None:
        with self.assertRaises(BuildError) as ctx:
            validate_config(_config("content", "public", plugins=[]))
        self.assertEqual(ctx.exception.stage, "config")
        self.assertIn("no plugins", ctx.exception.message)

    def test_out_equal_to_src_is_rejected(self) -> None:
        with self.assertRaises(BuildError) as ctx:
            validate_config(_config("site", "site", plugins=[_DummyPlugin()]))
        self.assertEqual(ctx.exception.stage, "config")
        self.assertIn("same directory", ctx.exception.message)

    def test_src_inside_out_is_rejected(self) -> None:
        with self.assertRaises(BuildError) as ctx:
            validate_config(
                _config("public/content", "public", plugins=[_DummyPlugin()])
            )
        self.assertIn("inside", ctx.exception.message)

    def test_out_inside_src_is_rejected(self) -> None:
        with self.assertRaises(BuildError) as ctx:
            validate_config(
                _config("content", "content/public", plugins=[_DummyPlugin()])
            )
        self.assertIn("inside", ctx.exception.message)

    def test_sibling_directories_are_valid(self) -> None:
        # Should not raise.
        validate_config(_config("content", "public", plugins=[_DummyPlugin()]))


class BuilderValidationTest(unittest.TestCase):
    def test_run_raises_build_error_for_bad_config(self) -> None:
        captured: list[Exception] = []

        class CatchPlugin:
            def apply(self, builder: Builder) -> None:
                builder.hooks.emit.tap("e", lambda _b: None)
                builder.hooks.failed.tap("catch", lambda err, _b: captured.append(err))

        builder = Builder(_config("site", "site", plugins=[CatchPlugin()]))
        with self.assertRaises(BuildError) as ctx:
            builder.run()
        self.assertEqual(ctx.exception.stage, "config")
        self.assertEqual(len(captured), 1)

    def test_warns_when_nothing_writes_output(self) -> None:
        class NoEmitPlugin:
            def apply(self, builder: Builder) -> None:
                builder.hooks.before_run.tap("noop", lambda _b: None)

        builder = Builder(_config("content", "public", plugins=[NoEmitPlugin()]))
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            builder.run()
        self.assertIn("will not write any files", stderr.getvalue())

    def test_no_warning_when_emit_is_tapped(self) -> None:
        builder = Builder(_config("content", "public", plugins=[_DummyPlugin()]))
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            builder.run()
        self.assertNotIn("will not write", stderr.getvalue())


class ReadFileSourceTest(unittest.TestCase):
    def test_missing_source_directory_is_friendly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "does-not-exist"
            build = Build(config=_config(str(missing), str(Path(tmp) / "out")))
            with self.assertRaises(BuildError) as ctx:
                ReadFile()._discover(build)
            self.assertIn("Source directory not found", ctx.exception.message)

    def test_source_path_must_be_a_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            file_path = Path(tmp) / "a-file"
            file_path.write_text("not a dir", encoding="utf-8")
            build = Build(config=_config(str(file_path), str(Path(tmp) / "out")))
            with self.assertRaises(BuildError) as ctx:
                ReadFile()._discover(build)
            self.assertIn("not a directory", ctx.exception.message)


if __name__ == "__main__":
    unittest.main()
