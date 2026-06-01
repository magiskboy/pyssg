"""Helpers shared by the presets."""

from __future__ import annotations


def site_title(site: dict[str, object] | None) -> str | None:
    """Read a string ``title`` from the site variables, if present."""
    if site is None:
        return None
    title = site.get("title")
    return title if isinstance(title, str) else None
