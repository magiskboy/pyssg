"""Unit tests for the Statistics plugin.

Covers the pure helpers (size formatting, disk walk, grouping, formatting), the
hybrid ``collect_stats`` against a real output directory, and the plugin guard
that stays silent while a DevServer is present.
"""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from pyssg.build import Build
from pyssg.config import Config
from pyssg.models import Source
from pyssg_plugins.dev_server import DevServer
from pyssg_plugins.stats import (
    Statistics,
    StatsReport,
    _group_by_type,
    _walk_files,
    collect_stats,
    format_report,
    human_size,
    report_to_dict,
)


class HumanSizeTest(unittest.TestCase):
    def test_bytes(self) -> None:
        self.assertEqual(human_size(0), "0 B")
        self.assertEqual(human_size(512), "512 B")

    def test_kilobytes(self) -> None:
        self.assertEqual(human_size(1024), "1.0 KB")
        self.assertEqual(human_size(1536), "1.5 KB")

    def test_megabytes(self) -> None:
        self.assertEqual(human_size(1024 * 1024), "1.0 MB")


class WalkFilesTest(unittest.TestCase):
    def test_collects_files_with_sizes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            (out / "index.html").write_text("hello", encoding="utf-8")
            (out / "sub").mkdir()
            (out / "sub" / "page.html").write_text("hi", encoding="utf-8")

            files = dict(_walk_files(out))

            self.assertEqual(files[Path("index.html")], 5)
            self.assertEqual(files[Path("sub/page.html")], 2)

    def test_missing_directory_is_empty(self) -> None:
        self.assertEqual(_walk_files(Path("/no/such/dir")), [])


class GroupByTypeTest(unittest.TestCase):
    def test_groups_and_sorts_by_bytes(self) -> None:
        files = [
            (Path("a.html"), 100),
            (Path("b.HTML"), 50),
            (Path("style.css"), 200),
        ]

        rows = _group_by_type(files)

        self.assertEqual(rows[0], (".css", 1, 200))
        self.assertEqual(rows[1], (".html", 2, 150))

    def test_files_without_suffix(self) -> None:
        rows = _group_by_type([(Path("LICENSE"), 10)])
        self.assertEqual(rows, [("(none)", 1, 10)])


class CollectStatsTest(unittest.TestCase):
    def test_hybrid_counts_and_sizes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            (out / "index.html").write_text("12345", encoding="utf-8")
            (out / "style.css").write_text("123", encoding="utf-8")

            build = Build(config=Config(src=Path("content"), out=out))
            build.sources = [
                Source(path=Path("a.md"), relpath=Path("a.md")),
                Source(
                    path=Path("tags.md"),
                    relpath=Path("tags.md"),
                    meta={"generated": True},
                ),
            ]

            report = collect_stats(build, top_n=5)

            self.assertEqual(report.sources, 2)
            self.assertEqual(report.generated, 1)
            self.assertEqual(report.file_count, 2)
            self.assertEqual(report.total_bytes, 8)
            self.assertEqual(report.largest[0], (Path("index.html"), 5))

    def test_top_n_limits_largest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            for index in range(4):
                (out / f"f{index}.html").write_text("x" * index, encoding="utf-8")

            build = Build(config=Config(src=Path("content"), out=out))
            report = collect_stats(build, top_n=2)

            self.assertEqual(len(report.largest), 2)


class FormatReportTest(unittest.TestCase):
    def _report(self) -> StatsReport:
        return StatsReport(
            sources=3,
            generated=1,
            file_count=2,
            total_bytes=2048,
            by_type=[(".html", 1, 1024), (".css", 1, 1024)],
            largest=[(Path("index.html"), 1024)],
        )

    def test_includes_summary_and_sections(self) -> None:
        text = format_report(self._report(), elapsed=0.084)

        self.assertIn("Build summary", text)
        self.assertIn("Sources:  3 (1 generated)", text)
        self.assertIn("Total: 2.0 KB", text)
        self.assertIn("Build: 84 ms", text)
        self.assertIn("By type:", text)
        self.assertIn("Largest:", text)

    def test_omits_timing_and_types_when_disabled(self) -> None:
        text = format_report(self._report(), elapsed=None, by_type=False)

        self.assertNotIn("Build:", text)
        self.assertNotIn("By type:", text)


class ReportToDictTest(unittest.TestCase):
    def _report(self) -> StatsReport:
        return StatsReport(
            sources=3,
            generated=1,
            file_count=2,
            total_bytes=2048,
            by_type=[(".html", 1, 1024)],
            largest=[(Path("index.html"), 1024)],
        )

    def test_serializable_structure(self) -> None:
        data = report_to_dict(self._report(), elapsed=0.084)

        self.assertEqual(data["sources"], 3)
        self.assertEqual(data["total_bytes"], 2048)
        self.assertEqual(data["build_ms"], 84)
        self.assertEqual(
            data["by_type"], [{"suffix": ".html", "count": 1, "bytes": 1024}]
        )
        self.assertEqual(data["largest"], [{"path": "index.html", "bytes": 1024}])
        json.dumps(data)  # must not raise

    def test_omits_build_ms_without_timing(self) -> None:
        self.assertNotIn("build_ms", report_to_dict(self._report(), elapsed=None))


class PluginGuardTest(unittest.TestCase):
    def _build(self, out: Path, *, with_dev_server: bool) -> Build:
        plugins = [DevServer()] if with_dev_server else []
        config = Config(src=Path("content"), out=out, plugins=list(plugins))
        return Build(config=config)

    def test_prints_for_plain_build(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            (out / "index.html").write_text("hi", encoding="utf-8")
            stats = Statistics()
            build = self._build(out, with_dev_server=False)

            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                stats._on_before_run(build)
                stats._on_after_emit(build)

            self.assertIn("Build summary", buffer.getvalue())

    def test_silent_when_dev_server_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            (out / "index.html").write_text("hi", encoding="utf-8")
            stats = Statistics()
            build = self._build(out, with_dev_server=True)

            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                stats._on_after_emit(build)

            self.assertEqual(buffer.getvalue(), "")

    def test_writes_json_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "public"
            out.mkdir()
            (out / "index.html").write_text("hi", encoding="utf-8")
            report_path = Path(tmp) / "reports" / "stats.json"
            stats = Statistics(json_path=str(report_path))
            build = self._build(out, with_dev_server=False)

            with contextlib.redirect_stdout(io.StringIO()):
                stats._on_after_emit(build)

            data = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(data["file_count"], 1)
            self.assertEqual(data["total_bytes"], 2)


if __name__ == "__main__":
    unittest.main()
