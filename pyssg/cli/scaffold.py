"""Site scaffolding for ``pyssg init`` and ``pyssg eject-layout``.

``init_site`` writes a minimal, ready-to-build site for a chosen preset (a
one-line ``pyssg.config.py`` plus a little sample content), so a new user can go
from nothing to ``pyssg build`` in one step. ``eject_layout`` copies a built-in
theme into the site so it can be customized and pointed at via ``layout=``.

Everything here is deterministic and reads no clock: sample dates are fixed
literals, so scaffolding the same preset twice produces identical files.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from pyssg.config import CONFIG_FILENAME
from pyssg.core.errors import ConfigError
from pyssg.themes import available_themes, theme_path

# Presets that ``init`` knows how to scaffold.
PRESETS = ("docs", "blog", "obsidian")

_DOCS_CONFIG = """\
from __future__ import annotations

from pyssg.presets import docs

config = docs(
    site={"title": "My Docs"},
    base_url="https://example.com",
)
"""

_BLOG_CONFIG = """\
from __future__ import annotations

from pyssg.presets import blog

config = blog(
    site={"title": "My Blog"},
    base_url="https://example.com",
)
"""

_DOCS_INDEX = """\
---
title: Home
---
# Welcome

This is your new docs site. Edit `content/index.md` to change this page, and see
[[Getting Started]] to learn more.
"""

_DOCS_GETTING_STARTED = """\
---
title: Getting Started
---
## Getting Started

1. Edit the pages under `content/`.
2. Run `pyssg build` to render the site into `dist/`.
3. Run `pyssg serve` to preview with live reload.
"""

_BLOG_POST = """\
---
title: Hello, world
date: "2024-01-01"
tags: [intro]
---
# Hello, world

Welcome to your new blog. Posts live under `content/posts/`; the home page lists
them newest-first. Edit this file or add more `.md` files alongside it.
"""

_OBSIDIAN_CONFIG = """\
from __future__ import annotations

from pyssg.presets import obsidian

config = obsidian(
    site={"title": "My Vault"},
    base_url="https://example.com",
)
"""

_OBSIDIAN_INDEX = """\
---
title: Home
---
# My Vault

Welcome. Every note is published by default; mark a note `publish: false` to keep
it private. See [[Getting Started]] to learn more.
"""

_OBSIDIAN_GETTING_STARTED = """\
---
title: Getting Started
---
## Getting Started

- Link notes with `[[wikilinks]]`; embed a note with `![[Note]]`.
- Embed an image with `![[diagram.png]]` (attachments are copied automatically).
- Mark a note `publish: false` to keep it out of the site.
- Run `pyssg build` to render, or `pyssg serve` for live preview.
"""

# Per-preset scaffold: config file plus the content tree (relative path -> body).
_SCAFFOLDS: dict[str, dict[str, str]] = {
    "docs": {
        CONFIG_FILENAME: _DOCS_CONFIG,
        "content/index.md": _DOCS_INDEX,
        "content/guide/getting-started.md": _DOCS_GETTING_STARTED,
    },
    "blog": {
        CONFIG_FILENAME: _BLOG_CONFIG,
        "content/posts/hello-world.md": _BLOG_POST,
    },
    "obsidian": {
        CONFIG_FILENAME: _OBSIDIAN_CONFIG,
        "content/index.md": _OBSIDIAN_INDEX,
        "content/Getting Started.md": _OBSIDIAN_GETTING_STARTED,
    },
}


def init_site(site_dir: Path, *, preset: str, force: bool = False) -> list[Path]:
    """Scaffold a new site for ``preset`` under ``site_dir``; return new files.

    Refuses to overwrite an existing ``pyssg.config.py`` unless ``force`` is set,
    so re-running ``init`` in a real site does not clobber it.
    """
    if preset not in _SCAFFOLDS:
        available = ", ".join(PRESETS)
        raise ConfigError(f"unknown preset '{preset}'; available: {available}")

    config_path = site_dir / CONFIG_FILENAME
    if config_path.exists() and not force:
        raise ConfigError(
            f"{CONFIG_FILENAME} already exists in {site_dir}; pass force to overwrite"
        )

    created: list[Path] = []
    for rel, body in _SCAFFOLDS[preset].items():
        path = site_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
        created.append(path)
    return sorted(created)


def eject_layout(site_dir: Path, *, theme: str, dest: str) -> Path:
    """Copy the built-in ``theme`` into ``site_dir/dest``; return the destination.

    Raises :class:`LayoutError` if the theme is unknown and :class:`ConfigError`
    if the destination already exists (to avoid clobbering a customized layout).
    """
    source = theme_path(theme)  # raises LayoutError listing available themes
    destination = site_dir / dest
    if destination.exists():
        raise ConfigError(f"destination already exists: {destination}")
    shutil.copytree(source, destination)
    return destination


def list_themes() -> list[str]:
    """Names of the built-in themes (for CLI help / messages)."""
    return sorted(available_themes())
