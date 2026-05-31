"""Statistics plugin: print a build summary after artifacts are written.

Opt-in only -- add ``Statistics()`` to ``config.plugins``. It taps ``before_run``
to stamp the start time and ``after_emit`` (last, after StaticFiles) to report.

The data is hybrid by design:

- Logical counts (sources, derived/generated pages) come from the in-memory
  ``Build``.
- File sizes and types are read from disk under ``config.out`` -- the only place
  that also captures static assets, which ``StaticFiles`` copies straight to
  disk and never turns into ``Output`` objects.

The summary is meant for one-shot ``pyssg build`` runs, so it stays silent while
``pyssg serve`` is running (detected by a ``DevServer`` in the plugin list) to
avoid spamming the rebuild loop.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

from pyssg.build import Build
from pyssg.builder import Builder
from pyssg_plugins.dev_server import DevServer

# Run last among after_emit taps so every artifact is on disk before we read it.
_AFTER_EMIT_STAGE = 1000
_SIZE_UNITS = ("B", "KB", "MB", "GB", "TB")


@dataclass(slots=True)
class StatsReport:
    """A snapshot of one build's artifacts, ready to be formatted."""

    sources: int
    generated: int
    file_count: int
    total_bytes: int
    by_type: list[tuple[str, int, int]]  # (suffix, count, bytes), largest first
    largest: list[tuple[Path, int]]  # (relpath, bytes), largest first


class Statistics:
    def __init__(
        self, *, top_n: int = 5, by_type: bool = True, json_path: str | None = None
    ) -> None:
        self._top_n = top_n
        self._by_type = by_type
        self._json_path = json_path
        self._start: float | None = None

    def apply(self, builder: Builder) -> None:
        builder.hooks.before_run.tap("Statistics", self._on_before_run)
        builder.hooks.after_emit.tap(
            "Statistics", self._on_after_emit, stage=_AFTER_EMIT_STAGE
        )

    def _on_before_run(self, build: Build) -> None:
        self._start = time.monotonic()

    def _on_after_emit(self, build: Build) -> None:
        if any(isinstance(plugin, DevServer) for plugin in build.config.plugins):
            return  # the dev server rebuilds constantly; stay quiet
        elapsed = None if self._start is None else time.monotonic() - self._start
        report = collect_stats(build, top_n=self._top_n)
        print(format_report(report, elapsed=elapsed, by_type=self._by_type))
        if self._json_path is not None:
            path = Path(self._json_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(report_to_dict(report, elapsed=elapsed), indent=2),
                encoding="utf-8",
            )
            print(f"  Stats written to {path}")


def collect_stats(build: Build, *, top_n: int) -> StatsReport:
    files = _walk_files(build.config.out.resolve())
    generated = sum(1 for source in build.sources if source.meta.get("generated"))
    largest = sorted(files, key=lambda item: item[1], reverse=True)[:top_n]
    return StatsReport(
        sources=len(build.sources),
        generated=generated,
        file_count=len(files),
        total_bytes=sum(size for _, size in files),
        by_type=_group_by_type(files),
        largest=largest,
    )


def _walk_files(out_dir: Path) -> list[tuple[Path, int]]:
    """Every file under ``out_dir`` as ``(path relative to out, size)``."""

    if not out_dir.is_dir():
        return []
    files: list[tuple[Path, int]] = []
    for path in out_dir.rglob("*"):
        if not path.is_file():
            continue
        try:
            size = path.stat().st_size
        except OSError:
            continue
        files.append((path.relative_to(out_dir), size))
    return files


def _group_by_type(files: list[tuple[Path, int]]) -> list[tuple[str, int, int]]:
    grouped: dict[str, tuple[int, int]] = {}
    for relpath, size in files:
        suffix = relpath.suffix.lower() or "(none)"
        count, total = grouped.get(suffix, (0, 0))
        grouped[suffix] = (count + 1, total + size)
    rows = [(suffix, count, total) for suffix, (count, total) in grouped.items()]
    rows.sort(key=lambda row: row[2], reverse=True)
    return rows


def human_size(num_bytes: int) -> str:
    """Format a byte count as a short human-readable string (B/KB/MB/...)."""

    size = float(num_bytes)
    for unit in _SIZE_UNITS:
        if size < 1024 or unit == _SIZE_UNITS[-1]:
            return f"{int(size)} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} {_SIZE_UNITS[-1]}"  # unreachable; keeps the type checker happy


def report_to_dict(
    report: StatsReport, *, elapsed: float | None = None
) -> dict[str, object]:
    """A JSON-serializable view of the report (for CI / machine consumption)."""

    data: dict[str, object] = {
        "sources": report.sources,
        "generated": report.generated,
        "file_count": report.file_count,
        "total_bytes": report.total_bytes,
        "by_type": [
            {"suffix": suffix, "count": count, "bytes": total}
            for suffix, count, total in report.by_type
        ],
        "largest": [
            {"path": str(relpath), "bytes": size} for relpath, size in report.largest
        ],
    }
    if elapsed is not None:
        data["build_ms"] = round(elapsed * 1000)
    return data


def format_report(
    report: StatsReport, *, elapsed: float | None = None, by_type: bool = True
) -> str:
    lines = ["Build summary"]

    sources_line = f"  Sources:  {report.sources}"
    if report.generated:
        sources_line += f" ({report.generated} generated)"
    lines.append(sources_line)

    files_line = (
        f"  Files:    {report.file_count}    Total: {human_size(report.total_bytes)}"
    )
    if elapsed is not None:
        files_line += f"    Build: {elapsed * 1000:.0f} ms"
    lines.append(files_line)

    if by_type and report.by_type:
        lines.append("  By type:")
        width = max(len(suffix) for suffix, _, _ in report.by_type)
        for suffix, count, total in report.by_type:
            lines.append(
                f"    {suffix.ljust(width)}  {count:>4}  {human_size(total):>10}"
            )

    if report.largest:
        lines.append("  Largest:")
        width = max(len(str(relpath)) for relpath, _ in report.largest)
        for relpath, size in report.largest:
            lines.append(f"    {str(relpath).ljust(width)}  {human_size(size):>10}")

    return "\n".join(lines)
