"""Command-line interface.

- ``pyssg init`` scaffolds a new site for a preset (``--preset docs|blog|obsidian``).
- ``pyssg build`` runs a full build (``--no-cache``, ``--profile``).
- ``pyssg serve`` watches + incrementally rebuilds + serves with live reload.
- ``pyssg clean`` removes the output dir and cache (with confirmation).
- ``pyssg eject-layout`` copies a built-in theme into the site to customize it.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from pyssg.cli.common import (
    CACHE_DIRNAME,
    build_site,
    build_stats_payload,
    make_builder,
    open_cache,
)
from pyssg.cli.scaffold import PRESETS, eject_layout, init_site, list_themes
from pyssg.cli.serve import serve
from pyssg.config import load_config
from pyssg.core.types import Phase

__all__ = ["build_site", "main", "make_builder"]


def _cmd_init(args: argparse.Namespace) -> int:
    site = Path(args.site)
    created = init_site(site, preset=args.preset, force=args.force)
    print(f"initialized {args.preset} site in {site}:")
    for path in created:
        print(f"  {path}")
    print("next: pyssg --site", str(site), "build")
    return 0


def _cmd_eject(args: argparse.Namespace) -> int:
    site = Path(args.site)
    dest = eject_layout(site, theme=args.theme, dest=args.to)
    rel = dest.relative_to(site) if dest.is_relative_to(site) else dest
    print(f"copied theme '{args.theme}' to {dest}")
    print(f'next: set layout="{rel.as_posix()}" in your pyssg.config.py')
    return 0


def _cmd_build(args: argparse.Namespace) -> int:
    site = Path(args.site)
    if args.json:
        try:
            stats = build_site(site, open_cache(site.resolve(), args.no_cache))
        except Exception as exc:
            print(json.dumps({"command": "build", "ok": False, "error": str(exc)}), flush=True)
            return 1
        payload = {"command": "build", "ok": True, **build_stats_payload(stats)}
        print(json.dumps(payload), flush=True)
        return 0
    stats = build_site(site, open_cache(site.resolve(), args.no_cache))
    print(f"build: {len(stats.changed_outputs)} pages written")
    if args.profile:
        for phase in Phase:
            count = stats.touched_per_phase.get(phase)
            if count:
                print(f"  {phase.name.lower():9} {count}")
        print(f"  cache hits {stats.cache_hits}")
    return 0


def _cmd_serve(args: argparse.Namespace) -> int:
    serve(
        Path(args.site),
        host=args.host,
        port=args.port,
        no_cache=args.no_cache,
        json_output=args.json,
    )
    return 0


def _cmd_clean(args: argparse.Namespace) -> int:
    site = Path(args.site).resolve()
    config = load_config(site)
    targets = [site / config.output_dir, site / CACHE_DIRNAME]
    existing = [t for t in targets if t.exists()]
    if not existing:
        print("nothing to clean")
        return 0
    print("will remove:")
    for t in existing:
        print(f"  {t}")
    if not args.yes:
        reply = input("proceed? [y/N] ").strip().lower()
        if reply not in {"y", "yes"}:
            print("aborted")
            return 1
    for t in existing:
        shutil.rmtree(t)
    print("cleaned")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pyssg", description="Static site generator")
    parser.add_argument("--site", default=".", help="site directory (default: .)")
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="scaffold a new site for a preset")
    init.add_argument("--preset", choices=PRESETS, default="docs", help="site preset")
    init.add_argument("--force", action="store_true", help="overwrite an existing config")

    build = sub.add_parser("build", help="full build to output_dir")
    build.add_argument("--no-cache", action="store_true", help="ignore the persistent cache")
    build.add_argument("--profile", action="store_true", help="print per-phase counts")
    build.add_argument("--json", action="store_true", help="emit a machine-readable summary")

    srv = sub.add_parser("serve", help="watch + incremental + dev server")
    srv.add_argument("--no-cache", action="store_true")
    srv.add_argument("--host", default="127.0.0.1")
    srv.add_argument("--port", type=int, default=8000)
    srv.add_argument("--json", action="store_true", help="emit machine-readable NDJSON events")

    clean = sub.add_parser("clean", help="remove output_dir + cache")
    clean.add_argument("--yes", action="store_true", help="skip confirmation")

    eject = sub.add_parser("eject-layout", help="copy a built-in theme into the site")
    eject.add_argument(
        "--theme", choices=list_themes(), required=True, help="built-in theme to copy"
    )
    eject.add_argument("--to", default="layouts/theme", help="destination dir (relative to site)")

    args = parser.parse_args(argv)
    if args.command == "init":
        return _cmd_init(args)
    if args.command == "build":
        return _cmd_build(args)
    if args.command == "serve":
        return _cmd_serve(args)
    if args.command == "eject-layout":
        return _cmd_eject(args)
    return _cmd_clean(args)
