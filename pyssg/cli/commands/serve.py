"""``pyssg serve`` -- watch, incrementally rebuild, and serve with live reload."""

from __future__ import annotations

from typing import Annotated

import typer

from pyssg.cli.app import app, site_from
from pyssg.cli.serve import serve as serve_site


@app.command(help="watch + incremental rebuild + dev server")
def serve(
    ctx: typer.Context,
    no_cache: Annotated[
        bool, typer.Option("--no-cache", help="ignore the persistent cache")
    ] = False,
    host: Annotated[str, typer.Option("--host", help="interface to bind")] = "127.0.0.1",
    port: Annotated[int, typer.Option("--port", help="port to listen on")] = 8000,
    json_output: Annotated[
        bool, typer.Option("--json", help="emit machine-readable NDJSON events")
    ] = False,
) -> None:
    """Watch + incremental rebuild + dev server (Ctrl-C to stop)."""
    serve_site(
        site_from(ctx),
        host=host,
        port=port,
        no_cache=no_cache,
        json_output=json_output,
    )
