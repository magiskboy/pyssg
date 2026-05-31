"""Configuration and loading of ``pyssg.config.py``.

The user's config file is a Python module exposing a ``config`` function that
returns a :class:`Config` object. This allows passing plugin instances and
arbitrary logic directly, similar to ``webpack.config.js``.
"""

from __future__ import annotations

import importlib.util
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from pyssg.errors import BuildError, SourceLocation
from pyssg.plugin import Plugin

DEFAULT_CONFIG_FILENAME = "pyssg.config.py"


@dataclass(slots=True)
class Config:
    src: Path
    out: Path
    plugins: list[Plugin] = field(default_factory=list)
    options: dict[str, object] = field(default_factory=dict)
    # Optional override for URL slug generation. When None, plugins use the
    # built-in Unicode-aware slugify. A custom callable receives the raw text
    # and must return the slug (e.g. to enforce a project-specific transliteration).
    slugify: Callable[[str], str] | None = None

    def __post_init__(self) -> None:
        self.src = Path(self.src)
        self.out = Path(self.out)


def validate_config(config: Config) -> None:
    """Check a :class:`Config` for fatal mistakes before the build runs.

    Raises a :class:`BuildError` (``stage="config"``) on problems that would
    silently produce a broken build or destroy data. The most dangerous case is
    ``out`` overlapping ``src``: ``WriteFile(clean=True)`` removes the output
    directory on each build, so an overlap would delete the user's source files.
    """

    if not config.plugins:
        raise BuildError(
            "Config has no plugins, so the build would do nothing. "
            "Set plugins to a preset like docs()/blog()/site(), "
            "or assemble plugins by hand.",
            stage="config",
        )

    src = config.src.resolve()
    out = config.out.resolve()
    if out == src:
        raise BuildError(
            f"Config 'out' and 'src' are the same directory ({config.out}). "
            "The output directory is cleaned on each build, which would delete "
            "your source files. Use a separate output directory, e.g. 'public'.",
            stage="config",
        )
    if src.is_relative_to(out):
        raise BuildError(
            f"Config 'src' ({config.src}) is inside 'out' ({config.out}). "
            "Cleaning the output directory on each build would delete your "
            "source files. Move the output directory outside the source tree.",
            stage="config",
        )
    if out.is_relative_to(src):
        raise BuildError(
            f"Config 'out' ({config.out}) is inside 'src' ({config.src}). "
            "Generated files would be picked up as sources on the next build. "
            "Move the output directory outside the source tree.",
            stage="config",
        )


def load_config(path: Path) -> Config:
    """Load the Python config file and call its ``config()`` function."""

    if not path.exists():
        raise BuildError(
            f"Config file not found: {path}. "
            f"Run 'pyssg new <name>' to scaffold a project, or pass -c <path>.",
            stage="config",
        )

    spec = importlib.util.spec_from_file_location("pyssg_user_config", path)
    if spec is None or spec.loader is None:
        raise BuildError(f"Could not load config file: {path}", stage="config")

    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except SyntaxError as error:
        location = SourceLocation(
            file=Path(error.filename) if error.filename else path,
            line=error.lineno,
            column=error.offset,
        )
        raise BuildError(
            f"Config has a syntax error: {error.msg}",
            stage="config",
            source_path=path,
            location=location,
        ) from error
    except Exception as error:
        raise BuildError(
            f"Config failed to import: {error}", stage="config", source_path=path
        ) from error

    factory = getattr(module, "config", None)
    if not callable(factory):
        raise BuildError(
            f"{path} must define a 'config() -> Config' function", stage="config"
        )

    try:
        result: object = factory()
    except Exception as error:
        raise BuildError(
            f"config() raised: {error}", stage="config", source_path=path
        ) from error
    if not isinstance(result, Config):
        raise BuildError(
            "The config() function must return a Config object", stage="config"
        )
    return result


# Type of the factory function the config file must expose.
ConfigFactory = Callable[[], Config]
