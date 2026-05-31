"""Unit tests for the ReadFile and WriteFile plugins (filesystem based)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pyssg.build import Build
from pyssg.builder import Builder
from pyssg.config import Config
from pyssg.models import Output
from pyssg_plugins.read_file import ReadFile
from pyssg_plugins.write_file import WriteFile


class ReadFileTest(unittest.TestCase):
    def test_discovers_and_reads_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "content"
            (src / "blog").mkdir(parents=True)
            (src / "a.md").write_text("alpha", encoding="utf-8")
            (src / "blog" / "b.md").write_text("beta", encoding="utf-8")
            (src / "ignore.txt").write_text("nope", encoding="utf-8")

            config = Config(src=src, out=root / "out", plugins=[ReadFile()])
            build = Builder(config).run()

            by_rel = {str(s.relpath): s.raw for s in build.sources}
            self.assertEqual(by_rel, {"a.md": "alpha", "blog/b.md": "beta"})

    def test_custom_patterns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "content"
            src.mkdir(parents=True)
            (src / "a.md").write_text("md", encoding="utf-8")
            (src / "b.markdown").write_text("ext", encoding="utf-8")

            config = Config(
                src=src,
                out=root / "out",
                plugins=[ReadFile(patterns=("*.md", "*.markdown"))],
            )
            build = Builder(config).run()

            self.assertEqual(len(build.sources), 2)


class WriteFileTest(unittest.TestCase):
    def test_writes_outputs_with_nested_dirs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = root / "public"
            config = Config(src=root / "content", out=out)
            build = Build(config=config)
            build.outputs.append(Output(path=Path("index.html"), content="home"))
            build.outputs.append(Output(path=Path("blog/post.html"), content="post"))

            WriteFile()._emit(build)

            self.assertEqual((out / "index.html").read_text(), "home")
            self.assertEqual((out / "blog" / "post.html").read_text(), "post")

    def test_clean_removes_stale_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = root / "public"
            out.mkdir(parents=True)
            (out / "stale.html").write_text("old", encoding="utf-8")

            config = Config(src=root / "content", out=out)
            build = Build(config=config)
            build.outputs.append(Output(path=Path("fresh.html"), content="new"))

            WriteFile(clean=True)._emit(build)

            self.assertFalse((out / "stale.html").exists())
            self.assertTrue((out / "fresh.html").exists())


if __name__ == "__main__":
    unittest.main()
