"""Built-in layout themes shipped with pyssg.

A theme is an ordinary layout package (``layout.toml`` + ``templates/`` +
``assets/``) bundled inside the installed package so presets (see
:mod:`pyssg.presets`) can reference a ready-made layout without the user copying
any files. ``theme_path`` resolves a theme name to its on-disk directory; pass
the result as ``Config.layout`` (an absolute :class:`~pathlib.Path` is used
as-is, unlike a relative ``str`` which is joined against the site directory).

Users who want to customize a theme can copy it into their site and point
``layout`` at the copy.
"""

from __future__ import annotations

from pathlib import Path

from pyssg.core.errors import LayoutError

# Themes live as sibling directories of this module.
_THEMES_ROOT = Path(__file__).resolve().parent


def theme_path(name: str) -> Path:
    """Return the directory of the built-in theme ``name``.

    Raises :class:`LayoutError` if no such theme ships with pyssg, listing the
    available names so a typo is obvious.
    """
    path = _THEMES_ROOT / name
    if not (path / "layout.toml").is_file():
        available = ", ".join(sorted(available_themes())) or "(none)"
        raise LayoutError(f"unknown built-in theme '{name}'; available: {available}")
    return path


def available_themes() -> list[str]:
    """List the names of the built-in themes."""
    return [p.name for p in _THEMES_ROOT.iterdir() if (p / "layout.toml").is_file()]
