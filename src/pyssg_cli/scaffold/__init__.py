"""Scaffolding for ``pyssg new``: themes, config generation, new posts."""

from __future__ import annotations

from pyssg_cli.scaffold.generate import (
    ScaffoldError,
    ScaffoldResult,
    new_post,
    new_site,
    render_config,
)
from pyssg_cli.scaffold.themes import (
    ThemeConfig,
    ThemeError,
    ThemeManifest,
    list_embedded_themes,
    load_manifest,
    parse_manifest,
    resolve_theme,
)

__all__ = [
    "ScaffoldError",
    "ScaffoldResult",
    "ThemeConfig",
    "ThemeError",
    "ThemeManifest",
    "list_embedded_themes",
    "load_manifest",
    "new_post",
    "new_site",
    "parse_manifest",
    "render_config",
    "resolve_theme",
]
