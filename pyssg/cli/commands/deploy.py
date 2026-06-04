"""``pyssg deploy`` -- push the built site to a hosting provider.

A two-level command: ``pyssg deploy <target-or-action>`` where the leaf is
either a registered hosting target (``github-pages``, ``cloudflare``,
``netlify``) or a meta action (``list`` / ``status``).

Built-in targets register themselves lazily: each command calls
:func:`pyssg.deploy.load_builtin_targets`, which imports each target module that
has landed (a not-yet-implemented target is simply absent from the registry, and
invoking it fails with the pipeline's "unknown deploy target" message). The meta
actions work regardless: ``list`` shows which targets the site has configured and
whether each is implemented, ``status`` summarizes the persisted last-deploy
record for each.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Annotated

import typer

from pyssg.cli._exit import exit_with
from pyssg.cli.app import app, site_from
from pyssg.config import load_config
from pyssg.deploy import list_targets, load_builtin_targets
from pyssg.deploy._output import Console
from pyssg.deploy.base import DeployError
from pyssg.deploy.pipeline import run_deploy
from pyssg.deploy.state import read_record

# Targets pyssg ships an integration for; each one gets its own subcommand even
# before its implementation lands so the CLI surface is stable. Adding a target
# here makes it visible in `--help`; making it runnable means registering the
# implementation in pyssg.deploy.
_BUILT_IN_TARGETS = ("github-pages", "cloudflare", "netlify")

deploy_app = typer.Typer(
    name="deploy",
    help="push the built site to a hosting provider",
    no_args_is_help=False,
)
app.add_typer(deploy_app, name="deploy")


def run_list(site: Path) -> int:
    """Print one line per configured target plus its implementation status."""
    load_builtin_targets()
    console = Console()
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


def run_status(site: Path) -> int:
    """Print the persisted last-deploy record for each configured target."""
    load_builtin_targets()
    console = Console()
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


def run_target(
    site: Path,
    target: str,
    *,
    dry_run: bool,
    force: bool,
    skip_build: bool,
    skip_check: bool,
) -> int:
    """Run the deploy pipeline for ``target``; return a process exit code."""
    load_builtin_targets()
    console = Console()
    try:
        run_deploy(
            site,
            target,
            dry_run=dry_run,
            force=force,
            skip_build=skip_build,
            skip_check=skip_check,
            console=console,
        )
        return 0
    except DeployError as exc:
        console.error(str(exc))
        return 1


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


@deploy_app.command("list", help="list configured deploy targets")
def deploy_list(ctx: typer.Context) -> None:
    """List configured deploy targets."""
    exit_with(run_list(site_from(ctx)))


@deploy_app.command("status", help="show last-deploy info per configured target")
def deploy_status(ctx: typer.Context) -> None:
    """Show last-deploy info per configured target."""
    exit_with(run_status(site_from(ctx)))


def _register_target(target_name: str) -> None:
    """Register a per-target subcommand carrying the standard deploy flags."""

    @deploy_app.command(target_name, help=f"deploy to {target_name}")
    def _target(
        ctx: typer.Context,
        dry_run: Annotated[
            bool,
            typer.Option(
                "--dry-run",
                help="run validations and report what would be uploaded, but do not push",
            ),
        ] = False,
        force: Annotated[
            bool,
            typer.Option(
                "--force",
                help="redeploy even if the output is byte-identical to the previous deploy",
            ),
        ] = False,
        skip_build: Annotated[
            bool,
            typer.Option(
                "--skip-build",
                help="reuse the existing output directory instead of rebuilding",
            ),
        ] = False,
        skip_check: Annotated[
            bool, typer.Option("--skip-check", help="skip the post-build sanity check")
        ] = False,
    ) -> None:
        exit_with(
            run_target(
                site_from(ctx),
                target_name,
                dry_run=dry_run,
                force=force,
                skip_build=skip_build,
                skip_check=skip_check,
            )
        )


for _name in _BUILT_IN_TARGETS:
    _register_target(_name)
