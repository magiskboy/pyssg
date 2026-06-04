"""Command modules for the ``pyssg`` CLI.

Importing this package registers every subcommand on
:data:`pyssg.cli.app.app` as a side effect. The package ``pyssg.cli``
``__init__`` imports it before exposing :func:`pyssg.cli.app.main`, so the
command tree is fully built by the time the CLI runs.
"""

from __future__ import annotations

from pyssg.cli.commands import build, clean, deploy, new, serve

__all__ = ["build", "clean", "deploy", "new", "serve"]
