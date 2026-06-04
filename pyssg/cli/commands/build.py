"""``pyssg build`` -- full build to the output directory."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from pyssg.cli._exit import exit_with
from pyssg.cli.app import app, site_from
from pyssg.cli.common import build_site, build_stats_payload, open_cache
from pyssg.core.types import Phase


def run_build(site: Path, *, no_cache: bool, profile: bool, json_output: bool) -> int:
    """Run one full build; return a process exit code.

    With ``json_output`` a single JSON object is printed to stdout -- ``{"ok":
    true, ...}`` on success or ``{"ok": false, "error": ...}`` on failure -- and
    the build exception is swallowed into that object (the stable contract the
    Obsidian adapter parses). Otherwise a human-readable summary is printed and a
    build error propagates.
    """
    if json_output:
        try:
            stats = build_site(site, open_cache(site.resolve(), no_cache))
        # Any build failure is reported as a JSON error object, not a crash.
        except Exception as exc:
            print(json.dumps({"command": "build", "ok": False, "error": str(exc)}), flush=True)
            return 1
        payload = {"command": "build", "ok": True, **build_stats_payload(stats)}
        print(json.dumps(payload), flush=True)
        return 0
    stats = build_site(site, open_cache(site.resolve(), no_cache))
    print(f"build: {len(stats.changed_outputs)} pages written")
    if profile:
        for phase in Phase:
            count = stats.touched_per_phase.get(phase)
            if count:
                print(f"  {phase.name.lower():9} {count}")
        print(f"  cache hits {stats.cache_hits}")
    return 0


@app.command(help="full build to output_dir")
def build(
    ctx: typer.Context,
    no_cache: Annotated[
        bool, typer.Option("--no-cache", help="ignore the persistent cache")
    ] = False,
    profile: Annotated[bool, typer.Option("--profile", help="print per-phase counts")] = False,
    json_output: Annotated[
        bool, typer.Option("--json", help="emit a machine-readable summary")
    ] = False,
) -> None:
    """Full build to ``output_dir``."""
    exit_with(
        run_build(
            site_from(ctx),
            no_cache=no_cache,
            profile=profile,
            json_output=json_output,
        )
    )
