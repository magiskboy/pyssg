"""Translate an integer exit code into Typer's control flow.

Typer ignores a command callback's return value; a command signals a nonzero
process status by raising :class:`typer.Exit`. Commands here keep their logic in
plain functions that *return* an ``int`` (easy to unit-test and reuse), then
hand that code to :func:`exit_with` so a zero finishes cleanly and a nonzero
exits with that status.
"""

from __future__ import annotations

import typer


def exit_with(code: int) -> None:
    """Raise :class:`typer.Exit` when ``code`` is nonzero; return on success."""
    if code:
        raise typer.Exit(code)
