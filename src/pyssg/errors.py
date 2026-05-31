"""Structured build errors with source locations.

A :class:`BuildError` carries enough context -- lifecycle ``stage``, the source
file being processed, and an optional :class:`SourceLocation` (the template or
content file plus line/column) -- to render a clear ``file:line`` message in the
terminal and a full-page HTML overlay in ``pyssg serve``.

The kernel stays dependency-free: rendering is plain stdlib string formatting.
"""

from __future__ import annotations

import html
import os
import sys
import traceback
from dataclasses import dataclass
from pathlib import Path

_TRACEBACK_ENV = "PYSSG_TRACEBACK"

# Minimal ANSI styling, only used when writing to a TTY.
_RED = "\033[31m"
_YELLOW = "\033[33m"
_BOLD = "\033[1m"
_DIM = "\033[2m"
_RESET = "\033[0m"


def warn(message: str, *, color: bool | None = None) -> None:
    """Print a non-fatal warning to stderr in a consistent ``warning:`` format."""

    use_color = sys.stderr.isatty() if color is None else color
    label = f"{_YELLOW}{_BOLD}warning{_RESET}:" if use_color else "warning:"
    print(f"{label} {message}", file=sys.stderr)


@dataclass(slots=True)
class SourceLocation:
    """A position inside a file: the origin of an error."""

    file: Path
    line: int | None = None
    column: int | None = None
    snippet: str | None = None


class BuildError(Exception):
    """A build failed in a way we can attribute to a file and lifecycle stage."""

    def __init__(
        self,
        message: str,
        *,
        stage: str | None = None,
        source_path: Path | None = None,
        location: SourceLocation | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.stage = stage
        self.source_path = source_path
        self.location = location

    def with_context(
        self, *, stage: str | None = None, source_path: Path | None = None
    ) -> BuildError:
        """Fill in stage/source only when not already set (used when wrapping)."""

        if self.stage is None and stage is not None:
            self.stage = stage
        if self.source_path is None and source_path is not None:
            self.source_path = source_path
        return self


def wrap(error: Exception, *, stage: str, source_path: Path | None) -> BuildError:
    """Attach stage/source context to any exception, preserving the cause."""

    if isinstance(error, BuildError):
        return error.with_context(stage=stage, source_path=source_path)
    message = str(error) or error.__class__.__name__
    wrapped = BuildError(message, stage=stage, source_path=source_path)
    wrapped.__cause__ = error
    return wrapped


def read_snippet(
    file: Path, line: int, *, column: int | None = None, context: int = 2
) -> str | None:
    """Render a few lines around ``line`` with line numbers and a caret."""

    try:
        lines = file.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    if not lines or line < 1:
        return None

    start = max(1, line - context)
    end = min(len(lines), line + context)
    width = len(str(end))
    out: list[str] = []
    for number in range(start, end + 1):
        marker = ">" if number == line else " "
        out.append(f"{marker} {number:>{width}} | {lines[number - 1]}")
        if number == line and column is not None and column >= 1:
            pad = " " * (width + 4 + column)
            out.append(f"{pad}^")
    return "\n".join(out)


def _ensure_snippet(location: SourceLocation) -> str | None:
    if location.snippet is not None:
        return location.snippet
    if location.line is not None:
        return read_snippet(location.file, location.line, column=location.column)
    return None


def want_traceback(explicit: bool = False) -> bool:
    """Whether to include a full traceback (flag or ``PYSSG_TRACEBACK`` env)."""

    return explicit or os.environ.get(_TRACEBACK_ENV, "") not in ("", "0", "false")


def render_terminal(
    error: BuildError, *, color: bool | None = None, show_traceback: bool = False
) -> str:
    """Render a concise, optionally colored, terminal report."""

    use_color = sys.stderr.isatty() if color is None else color

    def style(text: str, *codes: str) -> str:
        return f"{''.join(codes)}{text}{_RESET}" if use_color else text

    lines = [style("Build failed", _BOLD, _RED)]
    if error.stage:
        lines.append(f"  stage: {error.stage}")
    if error.source_path is not None:
        lines.append(f"  in:    {error.source_path}")

    location = error.location
    if location is not None:
        where = str(location.file)
        if location.line is not None:
            where += f":{location.line}"
            if location.column is not None:
                where += f":{location.column}"
        lines.append(style(f"  at:    {where}", _BOLD))

    lines.append("")
    lines.append(f"  {error.message}")

    if location is not None:
        snippet = _ensure_snippet(location)
        if snippet:
            lines.append("")
            lines.append(
                style(_indent(snippet), _DIM) if use_color else _indent(snippet)
            )

    if show_traceback and error.__cause__ is not None:
        lines.append("")
        lines.append(style("Traceback:", _DIM) if use_color else "Traceback:")
        tb = "".join(
            traceback.format_exception(
                type(error.__cause__), error.__cause__, error.__cause__.__traceback__
            )
        )
        lines.append(_indent(tb.rstrip()))

    return "\n".join(lines)


def render_html_overlay(error: BuildError) -> str:
    """Render a full-page HTML overlay describing the error."""

    def esc(text: str) -> str:
        return html.escape(text)

    rows: list[str] = []
    if error.stage:
        rows.append(_row("stage", error.stage))
    if error.source_path is not None:
        rows.append(_row("in", str(error.source_path)))
    location = error.location
    snippet_html = ""
    if location is not None:
        where = str(location.file)
        if location.line is not None:
            where += f":{location.line}"
            if location.column is not None:
                where += f":{location.column}"
        rows.append(_row("at", where))
        snippet = _ensure_snippet(location)
        if snippet:
            snippet_html = f"<pre class='snippet'>{esc(snippet)}</pre>"

    meta = "\n".join(rows)
    return _OVERLAY_TEMPLATE.format(
        message=esc(error.message),
        meta=meta,
        snippet=snippet_html,
    )


def _row(label: str, value: str) -> str:
    return (
        f"<div class='row'><span class='label'>{html.escape(label)}</span>"
        f"<span class='value'>{html.escape(value)}</span></div>"
    )


def _indent(text: str, prefix: str = "  ") -> str:
    return "\n".join(prefix + line for line in text.splitlines())


_OVERLAY_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Build failed - pyssg</title>
<style>
  body {{ margin: 0; background: #1b1d23; color: #e6e6e6;
    font: 15px/1.6 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }}
  .wrap {{ max-width: 900px; margin: 0 auto; padding: 48px 24px; }}
  .badge {{ display: inline-block; background: #e5484d; color: #fff;
    padding: 4px 10px; border-radius: 6px; font-weight: 700; letter-spacing: .04em; }}
  .message {{ margin: 18px 0; padding: 16px 18px; background: #2a1416;
    border-left: 3px solid #e5484d; border-radius: 6px; white-space: pre-wrap;
    font-size: 16px; }}
  .row {{ display: flex; gap: 12px; padding: 3px 0; }}
  .label {{ color: #9aa0a6; min-width: 56px; }}
  .value {{ color: #e6e6e6; }}
  .snippet {{ margin-top: 18px; padding: 16px 18px; background: #141519;
    border: 1px solid #2a2f3a; border-radius: 6px; overflow-x: auto;
    color: #c8ccd4; }}
  .hint {{ margin-top: 28px; color: #6b7280; }}
</style>
</head>
<body>
  <div class="wrap">
    <span class="badge">BUILD FAILED</span>
    <div class="message">{message}</div>
    {meta}
    {snippet}
    <p class="hint">Fix the error and save; this page reloads automatically.</p>
  </div>
</body>
</html>
"""
