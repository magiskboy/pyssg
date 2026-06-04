"""The root Typer application and the ``main(argv) -> int`` entry point.

The CLI is a Typer (Click) command tree rooted at :data:`app`. A single global
option -- ``--site`` -- lives on the root callback so it can appear *before* the
subcommand (``pyssg --site PATH build``); commands read it back via
:func:`site_from`.

:func:`main` adapts Typer to the process-exit contract the rest of the project
relies on: it returns an ``int`` exit code for application outcomes (so callers
and tests can do ``rc = main([...])``), while usage/parse errors propagate as
``SystemExit`` exactly as ``argparse`` did. It runs the command in Click's
non-standalone mode and maps the result:

- a command that finishes (returning ``None`` or raising ``typer.Exit(code)``)
  yields that exit code as an ``int``;
- a usage error (unknown command, bad option, missing required subcommand) is
  shown and re-raised as ``SystemExit`` with Click's exit code;
- an aborted prompt becomes ``SystemExit(1)``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import typer

# Typer vendors Click under ``typer._click``; usage errors raised in
# non-standalone mode are instances of this vendored ``ClickException``, not the
# stand-alone ``click`` package (which is not installed). Catch the vendored
# types so ``isinstance`` matches what Typer actually raises.
from typer._click.exceptions import Abort, ClickException
from typer.main import get_command


@dataclass(frozen=True)
class AppContext:
    """Process-global CLI state, stored on the Click context's ``obj``.

    Currently just the ``--site`` directory; kept as a small object so new
    global options can be threaded to commands without changing every signature.
    """

    site: Path


app = typer.Typer(
    name="pyssg",
    help="Incremental static site generator for Markdown.",
    add_completion=False,
    no_args_is_help=False,
)

# Referenced (not called) as the ``--site`` default so the default is a literal,
# keeping the option declaration free of a function call in the signature.
_DEFAULT_SITE = Path(".")


@app.callback()
def _root(
    ctx: typer.Context,
    site: Annotated[
        Path, typer.Option("--site", help="site directory (default: .)")
    ] = _DEFAULT_SITE,
) -> None:
    """Root callback: capture the global ``--site`` option for subcommands."""
    ctx.obj = AppContext(site=site)


def site_from(ctx: typer.Context) -> Path:
    """Return the ``--site`` path captured by the root callback.

    Commands call this instead of declaring ``--site`` themselves, so the option
    stays global (parsed before the subcommand) and there is a single source of
    truth for the site directory.
    """
    # _root sets ctx.obj for every invocation, so this never fails in practice.
    assert isinstance(ctx.obj, AppContext)
    return ctx.obj.site


def main(argv: list[str] | None = None) -> int:
    """Run the CLI and return a process exit code.

    See the module docstring for the result/exception mapping. ``argv`` defaults
    to ``sys.argv[1:]`` when ``None``, matching ``argparse``.

    The Click command is resolved on each call (after all command modules have
    registered via the package ``__init__``); ``get_command`` only reads the
    already-built Typer registry, so this is cheap.
    """
    command = get_command(app)
    try:
        result = command.main(args=argv, prog_name="pyssg", standalone_mode=False)
    except ClickException as exc:
        exc.show()
        raise SystemExit(exc.exit_code) from exc
    except Abort:
        typer.echo("Aborted!", err=True)
        raise SystemExit(1) from None
    return int(result or 0)
