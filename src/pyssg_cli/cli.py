"""Thin CLI: load the config then run the builder.

All real functionality lives in plugins; the CLI is just the entry point.

- ``pyssg build`` runs one build and exits.
- ``pyssg serve`` builds, then serves the output with live reload and rebuilds
  on change. The watch loop lives in the DevServer plugin; the CLI just appends
  it to the plugin list when needed and runs the (reusable) builder.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from pyssg.builder import Builder
from pyssg.config import DEFAULT_CONFIG_FILENAME, load_config
from pyssg.errors import BuildError, render_terminal, want_traceback
from pyssg_cli.scaffold import (
    ScaffoldError,
    ScaffoldResult,
    ThemeError,
    new_post,
    new_site,
)
from pyssg_plugins.dev_server import DevServer
from pyssg_plugins.stats import Statistics


def build_command(config_path: Path) -> int:
    config = load_config(config_path)
    builder = Builder(config)
    build = builder.run()
    # The Statistics plugin, when enabled, prints its own richer summary; avoid
    # the duplicate one-liner in that case.
    if not any(isinstance(plugin, Statistics) for plugin in config.plugins):
        print(
            f"Built {len(build.sources)} sources -> "
            f"{len(build.outputs)} files at {config.out}"
        )
    return 0


def serve_command(
    config_path: Path, *, host: str, port: int, livereload: bool, open_browser: bool
) -> int:
    config = load_config(config_path)
    if not any(isinstance(plugin, DevServer) for plugin in config.plugins):
        config.plugins.append(
            DevServer(
                host=host,
                port=port,
                livereload=livereload,
                config_path=str(config_path),
                open_browser=open_browser,
            )
        )
    builder = Builder(config)
    builder.run()  # blocks: the DevServer enters its watch loop in the done hook
    return 0


def new_command(
    target: str,
    name: str | None,
    *,
    theme: str,
    sample: bool,
    section: str | None,
) -> int:
    try:
        if target == "post":
            if not name:
                print("error: 'pyssg new post' requires a title", file=sys.stderr)
                return 2
            path = new_post(name, section=section)
            print(f"Created post: {path}")
            return 0
        result = new_site(target, theme=theme, sample=sample)
        _print_next_steps(result)
        return 0
    except (ScaffoldError, ThemeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


def _print_next_steps(result: ScaffoldResult) -> None:
    print(f"Created '{result.manifest.name}' site in {result.path}/")
    print()
    print("Next steps:")
    print(f"  cd {result.path}")
    deps = result.manifest.plugins
    if deps:
        print(f"  uv add {' '.join(deps)}")
    print("  pyssg serve")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pyssg", description="Static Site Generator")
    subparsers = parser.add_subparsers(dest="command", required=True)

    build_parser = subparsers.add_parser("build", help="Build the site once")
    build_parser.add_argument(
        "-c",
        "--config",
        type=Path,
        default=Path(DEFAULT_CONFIG_FILENAME),
        help=f"Path to the config file (default: {DEFAULT_CONFIG_FILENAME})",
    )
    build_parser.add_argument(
        "--traceback",
        action="store_true",
        help="Show the full Python traceback on a build error",
    )

    serve_parser = subparsers.add_parser(
        "serve", help="Build, serve with live reload, and rebuild on change"
    )
    serve_parser.add_argument(
        "-c",
        "--config",
        type=Path,
        default=Path(DEFAULT_CONFIG_FILENAME),
        help=f"Path to the config file (default: {DEFAULT_CONFIG_FILENAME})",
    )
    serve_parser.add_argument("--host", default="127.0.0.1", help="Host to bind")
    serve_parser.add_argument("--port", type=int, default=8000, help="Port to bind")
    serve_parser.add_argument(
        "--no-livereload",
        action="store_true",
        help="Disable automatic browser reload",
    )
    serve_parser.add_argument(
        "--open",
        action="store_true",
        help="Open the site in the default browser once the server starts",
    )
    serve_parser.add_argument(
        "--traceback",
        action="store_true",
        help="Show the full Python traceback on a build error",
    )

    new_parser = subparsers.add_parser(
        "new", help="Scaffold a new site, or a new post with 'new post <title>'"
    )
    new_parser.add_argument(
        "target", help="Site directory name, or 'post' to create a new post"
    )
    new_parser.add_argument(
        "name", nargs="?", help="Post title (only when target is 'post')"
    )
    new_parser.add_argument(
        "--theme",
        default="docs",
        help="Theme: embedded name (docs, blog) or owner/repo[/path][@tag]",
    )
    new_parser.add_argument(
        "--no-sample",
        action="store_true",
        help="Scaffold without the theme's sample content",
    )
    new_parser.add_argument(
        "--section",
        help="Subfolder under content for a new post (default: auto)",
    )

    args = parser.parse_args(argv)
    # A --traceback flag sets the env the renderers consult, so it reaches the
    # DevServer rebuild loop as well as the one-shot build path.
    if getattr(args, "traceback", False):
        os.environ["PYSSG_TRACEBACK"] = "1"
    try:
        return _dispatch(args)
    except BuildError as error:
        # Known, attributable failures get the concise located report instead of
        # a raw Python traceback (use --traceback to see the full stack).
        print(render_terminal(error, show_traceback=want_traceback()), file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        # Ctrl-C is the normal way to stop `serve`; exit quietly.
        print(file=sys.stderr)
        return 130
    except Exception as error:  # top-level safety net for unexpected bugs
        if want_traceback():
            raise
        print(
            f"error: {error}\n"
            "This is unexpected; re-run with --traceback for the full traceback.",
            file=sys.stderr,
        )
        return 1


def _dispatch(args: argparse.Namespace) -> int:
    if args.command == "new":
        return new_command(
            args.target,
            args.name,
            theme=args.theme,
            sample=not args.no_sample,
            section=args.section,
        )
    if args.command == "build":
        config_path: Path = args.config
        return build_command(config_path)
    if args.command == "serve":
        return serve_command(
            args.config,
            host=args.host,
            port=args.port,
            livereload=not args.no_livereload,
            open_browser=args.open,
        )
    return 1


if __name__ == "__main__":
    sys.exit(main())
