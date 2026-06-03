"""Site scaffolding for ``pyssg init`` and ``pyssg eject-layout``.

``init_site`` writes a minimal, ready-to-build site for a chosen preset (a
one-line ``pyssg.config.py`` plus a little sample content), so a new user can go
from nothing to ``pyssg build`` in one step. ``eject_layout`` copies a built-in
theme into the site so it can be customized and pointed at via ``layout=``.

Everything here is deterministic and reads no clock: sample dates are fixed
literals, so scaffolding the same preset twice produces identical files.
"""

from __future__ import annotations

import re
import shutil
import unicodedata
from collections.abc import Sequence
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


def slugify(text: str) -> str:
    """Turn a title into a filesystem- and URL-safe slug.

    Strips accents, lowercases, and collapses every run of non-alphanumeric
    characters into a single hyphen. Pure and deterministic: the same title
    always yields the same slug.
    """
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")


def _yaml_quote(value: str) -> str:
    """Double-quote a scalar for a YAML frontmatter value (escaping as needed)."""
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _render_post(*, title: str, date: str, tags: Sequence[str]) -> str:
    """Render a post's Markdown body (frontmatter + a starter heading)."""
    lines = ["---", f"title: {_yaml_quote(title)}", f"date: {_yaml_quote(date)}"]
    if tags:
        lines.append("tags: [" + ", ".join(tags) + "]")
    lines += ["---", f"# {title}", "", "Write your post here.", ""]
    return "\n".join(lines)


def scaffold_post(
    site_dir: Path,
    *,
    title: str,
    date: str,
    tags: Sequence[str] = (),
    slug: str | None = None,
    force: bool = False,
) -> Path:
    """Create ``content/posts/<slug>.md`` for a new post; return its path.

    The ``date`` is supplied by the caller (the CLI reads the clock, not this
    function) so scaffolding stays pure: the same arguments always write the same
    bytes. ``slug`` defaults to :func:`slugify` of ``title``. Refuses to
    overwrite an existing file unless ``force`` is set.
    """
    resolved_slug = slug if slug is not None else slugify(title)
    if not resolved_slug:
        raise ConfigError(f"could not derive a slug from title {title!r}; pass slug explicitly")
    path = site_dir / "content" / "posts" / f"{resolved_slug}.md"
    if path.exists() and not force:
        raise ConfigError(f"{path} already exists; pass force to overwrite")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_render_post(title=title, date=date, tags=tags), encoding="utf-8")
    return path


def _plugin_class_name(name: str) -> str:
    """``my_plugin`` -> ``MyPluginPlugin`` (CamelCase class name for a factory)."""
    return "".join(part.capitalize() for part in name.split("_")) + "Plugin"


_PLUGIN_TEMPLATE = '''\
"""Custom pyssg plugin: {name}.

Generated by ``pyssg new plugin``. A plugin is a class plus a thin lowercase
factory; customize it by passing options to the factory or by subclassing and
overriding a single method -- never by copy-pasting it to tweak one line.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pyssg.core.build import Build
    from pyssg.core.builder import Builder
    from pyssg.core.node import Document


class {cls}:
    """One-line summary of what this plugin does and why."""

    name = "{name}"
    # Bump whenever a change here alters rendered output, so the render cache
    # stays correct across incremental builds.
    cache_version = "1.0.0"

    def __init__(self, *, enabled: bool = True) -> None:
        self._enabled = enabled

    def apply(self, builder: Builder) -> None:
        """Wire hooks. Keep this stable; subclasses override the steps below."""

        @builder.hooks.this_compilation.tap(self.name)
        def _wire(build: Build) -> None:
            @build.hooks.finalize_content.tap(self.name, stage=300)
            def _rewrite(html: str, doc: Document) -> str:
                return self.transform(html, doc)

    def transform(self, html: str, doc: Document) -> str:
        """Return the rewritten HTML for ``doc``. Override this in a subclass.

        Must be a pure function of its inputs so builds stay byte-identical and
        incremental rebuilds match a full rebuild.
        """
        if not self._enabled:
            return html
        return html


def {name}(*, enabled: bool = True) -> {cls}:
    """Factory: add ``{name}()`` to ``config.plugins`` to enable this plugin."""
    return {cls}(enabled=enabled)
'''


def scaffold_plugin(site_dir: Path, *, name: str, force: bool = False) -> Path:
    """Create ``plugins/<name>.py`` -- a starter plugin -- under the site.

    ``name`` must be a valid Python identifier (it is used as the module name,
    the factory name, and the basis for the class name). Refuses to overwrite an
    existing file unless ``force`` is set. Pure and deterministic.
    """
    if not name.isidentifier():
        raise ConfigError(f"plugin name must be a valid Python identifier: {name!r}")
    path = site_dir / "plugins" / f"{name}.py"
    if path.exists() and not force:
        raise ConfigError(f"{path} already exists; pass force to overwrite")
    body = _PLUGIN_TEMPLATE.format(name=name, cls=_plugin_class_name(name))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path
