"""``pyssg new`` -- scaffold a site, post, theme, or plugin.

The ``new`` group is the single home for project scaffolding. The historical
top-level commands ``pyssg init`` and ``pyssg eject-layout`` are preserved as
hidden aliases for ``new site`` / ``new theme`` so existing docs, scripts, and
the published Obsidian adapter keep working.
"""

from __future__ import annotations

from datetime import date as date_cls
from pathlib import Path
from typing import Annotated

import typer

from pyssg.cli._exit import exit_with
from pyssg.cli.app import app, site_from
from pyssg.cli.scaffold import (
    PRESETS,
    eject_layout,
    init_site,
    list_themes,
    scaffold_plugin,
    scaffold_post,
)
from pyssg.core.errors import ConfigError

new_app = typer.Typer(
    name="new",
    help="scaffold a site, post, theme, or plugin",
    no_args_is_help=True,
)
app.add_typer(new_app, name="new")


def run_new_site(site: Path, *, preset: str, force: bool) -> int:
    """Scaffold a new site for ``preset`` under ``site``; return an exit code."""
    if preset not in PRESETS:
        raise typer.BadParameter(
            f"unknown preset {preset!r}; available: {', '.join(PRESETS)}",
            param_hint="--preset",
        )
    try:
        created = init_site(site, preset=preset, force=force)
    except ConfigError as exc:
        typer.echo(f"error: {exc}", err=True)
        return 1
    print(f"initialized {preset} site in {site}:")
    for path in created:
        print(f"  {path}")
    print("next: pyssg --site", str(site), "build")
    return 0


def run_new_theme(site: Path, *, theme: str, to: str) -> int:
    """Copy a built-in ``theme`` into ``site/to`` (the eject); return an exit code."""
    if theme not in list_themes():
        raise typer.BadParameter(
            f"unknown theme {theme!r}; available: {', '.join(list_themes())}",
            param_hint="--name",
        )
    try:
        dest = eject_layout(site, theme=theme, dest=to)
    except ConfigError as exc:
        typer.echo(f"error: {exc}", err=True)
        return 1
    rel = dest.relative_to(site) if dest.is_relative_to(site) else dest
    print(f"copied theme '{theme}' to {dest}")
    print(f'next: set layout="{rel.as_posix()}" in your pyssg.config.py')
    return 0


def run_new_post(
    site: Path,
    *,
    title: str,
    date: str,
    tags: list[str],
    slug: str | None,
    force: bool,
) -> int:
    """Scaffold ``content/posts/<slug>.md`` for a new post; return an exit code."""
    try:
        path = scaffold_post(site, title=title, date=date, tags=tags, slug=slug, force=force)
    except ConfigError as exc:
        typer.echo(f"error: {exc}", err=True)
        return 1
    print(f"created post {path}")
    return 0


def run_new_plugin(site: Path, *, name: str, force: bool) -> int:
    """Scaffold ``plugins/<name>.py`` -- a starter plugin; return an exit code."""
    try:
        path = scaffold_plugin(site, name=name, force=force)
    except ConfigError as exc:
        typer.echo(f"error: {exc}", err=True)
        return 1
    print(f"created plugin {path}")
    print(f"next: add {name}() to config.plugins")
    return 0


@new_app.command("site", help="scaffold a new site for a preset")
def new_site(
    ctx: typer.Context,
    preset: Annotated[
        str, typer.Option("--preset", help="site preset: docs|blog|obsidian")
    ] = "docs",
    force: Annotated[bool, typer.Option("--force", help="overwrite an existing config")] = False,
) -> None:
    """Scaffold a new site for a preset."""
    exit_with(run_new_site(site_from(ctx), preset=preset, force=force))


@new_app.command("theme", help="copy a built-in theme into the site")
def new_theme(
    ctx: typer.Context,
    name: Annotated[str, typer.Option("--name", help="built-in theme to copy")],
    to: Annotated[
        str, typer.Option("--to", help="destination dir (relative to site)")
    ] = "layouts/theme",
) -> None:
    """Copy a built-in theme into the site so it can be customized."""
    exit_with(run_new_theme(site_from(ctx), theme=name, to=to))


@new_app.command("post", help="scaffold a new blog post under content/posts")
def new_post(
    ctx: typer.Context,
    title: Annotated[str, typer.Option("--title", help="post title")] = "New Post",
    tag: Annotated[list[str] | None, typer.Option("--tag", help="a tag (repeatable)")] = None,
    date: Annotated[str | None, typer.Option("--date", help="ISO date (default: today)")] = None,
    slug: Annotated[
        str | None, typer.Option("--slug", help="file slug (default: from title)")
    ] = None,
    force: Annotated[bool, typer.Option("--force", help="overwrite an existing post")] = False,
) -> None:
    """Scaffold a new blog post under ``content/posts``."""
    # The default date is the only place the CLI reads the clock; passing it
    # explicitly into the (pure) scaffolder keeps scaffolding deterministic and
    # lets ``--date`` produce reproducible output.
    resolved_date = date if date is not None else date_cls.today().isoformat()
    exit_with(
        run_new_post(
            site_from(ctx),
            title=title,
            date=resolved_date,
            tags=tag or [],
            slug=slug,
            force=force,
        )
    )


@new_app.command("plugin", help="scaffold a starter plugin module under plugins/")
def new_plugin(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="plugin name (a Python identifier)")],
    force: Annotated[bool, typer.Option("--force", help="overwrite an existing file")] = False,
) -> None:
    """Scaffold a starter plugin module under ``plugins/``."""
    exit_with(run_new_plugin(site_from(ctx), name=name, force=force))


@app.command("init", hidden=True)
def init(
    ctx: typer.Context,
    preset: Annotated[
        str, typer.Option("--preset", help="site preset: docs|blog|obsidian")
    ] = "docs",
    force: Annotated[bool, typer.Option("--force", help="overwrite an existing config")] = False,
) -> None:
    """Deprecated alias for ``new site``."""
    exit_with(run_new_site(site_from(ctx), preset=preset, force=force))


@app.command("eject-layout", hidden=True)
def eject_layout_command(
    ctx: typer.Context,
    theme: Annotated[str, typer.Option("--theme", help="built-in theme to copy")],
    to: Annotated[
        str, typer.Option("--to", help="destination dir (relative to site)")
    ] = "layouts/theme",
) -> None:
    """Deprecated alias for ``new theme``."""
    exit_with(run_new_theme(site_from(ctx), theme=theme, to=to))
