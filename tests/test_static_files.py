"""Unit tests for the StaticFiles plugin."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pyssg.build import Build
from pyssg.config import Config
from pyssg_plugins.static_files import StaticFiles


class StaticFilesTest(unittest.TestCase):
    def test_copies_tree_into_dest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            assets = root / "assets"
            (assets / "css").mkdir(parents=True)
            (assets / "css" / "style.css").write_text("body{}", encoding="utf-8")
            (assets / "logo.svg").write_text("<svg/>", encoding="utf-8")
            out = root / "public"

            build = Build(config=Config(src=root / "content", out=out))
            StaticFiles(directory=str(assets), dest="static")._emit(build)

            self.assertEqual(
                (out / "static" / "css" / "style.css").read_text(), "body{}"
            )
            self.assertEqual((out / "static" / "logo.svg").read_text(), "<svg/>")

    def test_copies_into_root_when_no_dest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            assets = root / "assets"
            assets.mkdir()
            (assets / "robots.txt").write_text("ok", encoding="utf-8")
            out = root / "public"

            build = Build(config=Config(src=root / "content", out=out))
            StaticFiles(directory=str(assets))._emit(build)

            self.assertEqual((out / "robots.txt").read_text(), "ok")

    def test_missing_directory_is_noop(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build = Build(config=Config(src=root / "content", out=root / "public"))
            StaticFiles(directory=str(root / "nope"))._emit(build)
            self.assertFalse((root / "public").exists())


if __name__ == "__main__":
    unittest.main()
