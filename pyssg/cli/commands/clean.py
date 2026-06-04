"""``pyssg clean`` -- remove the output directory and the build cache."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Annotated

import typer

from pyssg.cli._exit import exit_with
from pyssg.cli.app import app, site_from
from pyssg.cli.common import CACHE_DIRNAME
from pyssg.config import load_config


def run_clean(site: Path, *, yes: bool) -> int:
    """Remove ``output_dir`` and the cache under ``site``; return an exit code.

    Lists what will be removed and asks for confirmation unless ``yes`` is set.
    Returns 1 if the user declines, 0 otherwise (including when there is nothing
    to remove).
    """
    site = site.resolve()
    config = load_config(site)
    targets = [site / config.output_dir, site / CACHE_DIRNAME]
    existing = [t for t in targets if t.exists()]
    if not existing:
        print("nothing to clean")
        return 0
    print("will remove:")
    for t in existing:
        print(f"  {t}")
    if not yes:
        reply = input("proceed? [y/N] ").strip().lower()
        if reply not in {"y", "yes"}:
            print("aborted")
            return 1
    for t in existing:
        shutil.rmtree(t)
    print("cleaned")
    return 0


@app.command(help="remove output_dir + cache")
def clean(
    ctx: typer.Context,
    yes: Annotated[bool, typer.Option("--yes", help="skip confirmation")] = False,
) -> None:
    """Remove ``output_dir`` + cache."""
    exit_with(run_clean(site_from(ctx), yes=yes))
