"""Friendly console output for the ``pyssg deploy`` pipeline.

The deploy CLI is the most user-facing surface pyssg ships: a typo in a token
or a stray network error is something the user has to fix in the next minute,
so the output is tuned for fast scanning rather than density. The conventions
this module enforces:

* Top-level step lines start with ``==>`` (Homebrew-style); detail lines under
  a step are indented four spaces.
* Errors print ``error: <msg>`` to stderr with optional indented hints.
* The final summary is a two-column key/value block, aligned for easy reading.

No colors and no third-party deps -- the goal is "always works in any terminal"
not "looks pretty in iTerm2". A future ``--color`` flag can layer on top.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, TextIO

if TYPE_CHECKING:
    from collections.abc import Iterable

    from pyssg.deploy.base import DeployResult


_STEP_PREFIX = "==>"
_DETAIL_INDENT = "    "


class Console:
    """Tiny wrapper around two text streams with deploy-specific formatting.

    Holding the streams as instance state (instead of always writing to
    ``sys.stdout``/``sys.stderr``) makes the module trivially testable: pass in
    ``io.StringIO`` and assert on the captured text.
    """

    def __init__(self, *, out: TextIO | None = None, err: TextIO | None = None) -> None:
        self._out = out if out is not None else sys.stdout
        self._err = err if err is not None else sys.stderr

    def step(self, message: str) -> None:
        """A top-level pipeline step (``==> message``)."""
        print(f"{_STEP_PREFIX} {message}", file=self._out, flush=True)

    def detail(self, message: str) -> None:
        """A subordinate line under the most recent step (four-space indent)."""
        print(f"{_DETAIL_INDENT}{message}", file=self._out, flush=True)

    def ok(self, message: str) -> None:
        """Successful completion of a step (an indented detail line)."""
        self.detail(message)

    def skip(self, message: str) -> None:
        """A whole step or the run was skipped (still an indented detail)."""
        self.detail(message)

    def error(self, message: str, *, hints: Iterable[str] = ()) -> None:
        """Print an error and, optionally, indented next-step hints.

        Goes to stderr so the exit code and the message stream stay coherent
        for callers that pipe stdout into other tools.
        """
        print(f"error: {message}", file=self._err, flush=True)
        for hint in hints:
            print(f"  {hint}", file=self._err, flush=True)

    def summary(self, result: DeployResult) -> None:
        """Two-column key/value block summarizing a finished deploy."""
        rows: list[tuple[str, str]] = [
            ("deployment", result.deployment_id),
            ("url", result.url),
            (
                "uploaded",
                f"{result.files_uploaded} file(s) ({_format_bytes(result.bytes_uploaded)})",
            ),
        ]
        if result.files_skipped:
            rows.append(("skipped", f"{result.files_skipped} file(s) (already present)"))
        rows.append(("elapsed", f"{result.elapsed_seconds:.1f}s"))
        width = max(len(k) for k, _ in rows)
        print("", file=self._out)
        for key, value in rows:
            print(f"{key.ljust(width)}  {value}", file=self._out)
        self._out.flush()


def _format_bytes(n: int) -> str:
    """Human-readable byte count: ``1.2 MB``, ``842 KB``, ``17 B``.

    Uses 1024-based units (KB/MB/...) which matches what most CLIs report; the
    distinction with KiB/MiB is academic for a friendly summary.
    """
    if n < 1024:
        return f"{n} B"
    units = ["KB", "MB", "GB", "TB"]
    value = float(n) / 1024.0
    for unit in units:
        if value < 1024.0:
            return f"{value:.1f} {unit}"
        value /= 1024.0
    return f"{value:.1f} PB"
