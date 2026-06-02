"""``pyssg deploy`` subcommand parser and dispatcher.

The deploy CLI is structured as a two-level subcommand: ``pyssg deploy
<target-or-action>`` where ``target-or-action`` is either a registered hosting
target (``github-pages``, ``cloudflare``, ``netlify``) or one of the meta
actions ``list`` / ``status``.

Built-in targets register themselves lazily: :func:`run` calls
:func:`pyssg.deploy.load_builtin_targets`, which imports each target module
that has landed (a not-yet-implemented target is simply absent from the
registry, and invoking it fails with the pipeline's "unknown deploy target"
message). The meta actions work regardless: ``list`` shows which targets the
site has configured and whether each is implemented, ``status`` summarizes the
persisted last-deploy record for each.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import TYPE_CHECKING

from pyssg.config import load_config
from pyssg.deploy import list_targets, load_builtin_targets
from pyssg.deploy._output import Console
from pyssg.deploy.base import DeployError
from pyssg.deploy.pipeline import run_deploy
from pyssg.deploy.state import read_record

if TYPE_CHECKING:
    from collections.abc import Sequence

# Targets pyssg ships an integration for; each one gets its own subparser even
# before its implementation lands so the CLI surface is stable. Adding a target
# here makes it visible in `--help`; making it runnable means registering the
# implementation in pyssg.deploy.
_BUILT_IN_TARGETS = ("github-pages", "cloudflare", "netlify")


def add_subparser(sub: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the ``deploy`` subcommand on the main ``pyssg`` parser."""
    deploy = sub.add_parser("deploy", help="push the built site to a hosting provider")
    actions = deploy.add_subparsers(dest="deploy_action", required=True)

    actions.add_parser("list", help="list configured deploy targets")
    actions.add_parser("status", help="show last-deploy info per configured target")

    for name in _BUILT_IN_TARGETS:
        target = actions.add_parser(name, help=f"deploy to {name}")
        target.add_argument(
            "--dry-run",
            action="store_true",
            help="run validations and report what would be uploaded, but do not push",
        )
        target.add_argument(
            "--force",
            action="store_true",
            help="redeploy even if the output is byte-identical to the previous deploy",
        )
        target.add_argument(
            "--skip-build",
            action="store_true",
            help="reuse the existing output directory instead of rebuilding",
        )
        target.add_argument(
            "--skip-check",
            action="store_true",
            help="skip the post-build sanity check",
        )


def run(args: argparse.Namespace) -> int:
    """Dispatch a parsed ``deploy ...`` invocation; returns a process exit code."""
    site = Path(args.site)
    action = args.deploy_action
    console = Console()
    # Populate the global registry with whatever built-in targets have landed;
    # `list`/`status`/`<target>` all read it.
    load_builtin_targets()
    if action == "list":
        return _cmd_list(site, console)
    if action == "status":
        return _cmd_status(site, console)
    try:
        run_deploy(
            site,
            action,
            dry_run=args.dry_run,
            force=args.force,
            skip_build=args.skip_build,
            skip_check=args.skip_check,
            console=console,
        )
        return 0
    except DeployError as exc:
        console.error(str(exc))
        return 1


def _cmd_list(site: Path, console: Console) -> int:
    """Print one line per configured target plus its implementation status."""
    config = load_config(site)
    registered = set(list_targets())
    configured = sorted(config.deploy)
    if not configured:
        console.detail("no deploy targets configured in pyssg.config.py")
        return 0
    header = ("target", "configured", "implemented")
    rows: list[tuple[str, str, str]] = [
        (name, "yes", "yes" if name in registered else "no") for name in configured
    ]
    _print_table(console, header, rows)
    return 0


def _cmd_status(site: Path, console: Console) -> int:
    """Print the persisted last-deploy record for each configured target."""
    config = load_config(site)
    configured = sorted(config.deploy)
    if not configured:
        console.detail("no deploy targets configured in pyssg.config.py")
        return 0
    header = ("target", "last deploy", "deployment", "url")
    rows: list[tuple[str, str, str, str]] = []
    for name in configured:
        record = read_record(site, name)
        if record is None:
            rows.append((name, "-", "-", "-"))
        else:
            rows.append((name, record.timestamp, record.deployment_id, record.url))
    _print_table(console, header, rows)
    return 0


def _print_table(
    console: Console,
    header: tuple[str, ...],
    rows: Sequence[tuple[str, ...]],
) -> None:
    """Render a simple left-aligned table to the console's stdout stream."""
    columns = list(zip(header, *rows, strict=True))
    widths = [max(len(str(cell)) for cell in column) for column in columns]
    fmt = "  ".join(f"{{:<{w}}}" for w in widths)
    console.detail(fmt.format(*header))
    console.detail(fmt.format(*("-" * w for w in widths)))
    for row in rows:
        console.detail(fmt.format(*row))
