"""Theme resolution and ``theme.toml`` parsing for ``pyssg new``.

Two kinds of distribution (see ROADMAP section D):

- **Embedded themes** ship inside the package at ``pyssg/themes/<name>`` (a copy
  of the repo-root ``themes/``). Referenced by short name (``docs``, ``blog``)
  they resolve fully offline.
- **Community themes** live on GitHub, referenced as ``owner/repo[/path][@tag]``.
  They are fetched as a tarball with the standard library only (``urllib`` +
  ``tarfile``); no ``git`` dependency.

A theme is a directory containing ``theme.toml`` plus ``layouts/``/``assets/``/
``content/``. ``new`` only reads the manifest and copies files -- it never
executes code from a theme, so a fetched third-party theme cannot run code.
"""

from __future__ import annotations

import tarfile
import tomllib
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

VALID_PRESETS = frozenset({"docs", "blog", "site"})

_DEFAULT_INCLUDE = ("layouts", "assets", "content")
_DEFAULT_SAMPLE = ("content",)


class ThemeError(Exception):
    """A theme could not be resolved, parsed or validated."""


@dataclass(slots=True)
class ThemeConfig:
    """The ``[config]`` table: how to generate ``pyssg.config.py``."""

    preset: str
    src: str = "content"
    out: str = "public"
    options: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class ThemeManifest:
    """A parsed, validated ``theme.toml``."""

    name: str
    config: ThemeConfig
    description: str = ""
    version: str = ""
    requires_pyssg: str = ""
    author: str = ""
    homepage: str = ""
    plugins: list[str] = field(default_factory=list)
    include: list[str] = field(default_factory=lambda: list(_DEFAULT_INCLUDE))
    sample: list[str] = field(default_factory=lambda: list(_DEFAULT_SAMPLE))


def parse_manifest(text: str) -> ThemeManifest:
    """Parse and validate the text of a ``theme.toml`` file."""

    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as error:
        raise ThemeError(f"theme.toml is not valid TOML: {error}") from error

    theme = _table(data, "theme")
    name = theme.get("name")
    if not isinstance(name, str) or not name:
        raise ThemeError("theme.toml: [theme].name is required")

    config = _parse_config(_table(data, "config"))

    dependencies = _table(data, "dependencies", required=False)
    scaffold = _table(data, "scaffold", required=False)

    return ThemeManifest(
        name=name,
        config=config,
        description=_str(theme, "description"),
        version=_str(theme, "version"),
        requires_pyssg=_str(theme, "requires_pyssg"),
        author=_str(theme, "author"),
        homepage=_str(theme, "homepage"),
        plugins=_str_list(dependencies, "plugins"),
        include=_str_list(scaffold, "include") or list(_DEFAULT_INCLUDE),
        sample=_str_list(scaffold, "sample") or list(_DEFAULT_SAMPLE),
    )


def load_manifest(theme_dir: Path) -> ThemeManifest:
    """Read and parse ``<theme_dir>/theme.toml``."""

    manifest_path = theme_dir / "theme.toml"
    if not manifest_path.is_file():
        raise ThemeError(f"No theme.toml found in {theme_dir}")
    return parse_manifest(manifest_path.read_text(encoding="utf-8"))


def embedded_themes_dir() -> Path:
    """Directory holding the official embedded themes.

    The themes ship next to this package at ``pyssg_cli/themes`` -- both in an
    installed wheel (via the ``force-include`` in ``pyproject.toml``) and in an
    editable checkout (the directory lives under ``src/pyssg_cli``).
    """

    return Path(__file__).resolve().parent.parent / "themes"


def list_embedded_themes() -> list[str]:
    root = embedded_themes_dir()
    if not root.is_dir():
        return []
    return sorted(
        entry.name for entry in root.iterdir() if (entry / "theme.toml").is_file()
    )


def resolve_theme(ref: str, *, workdir: Path) -> Path:
    """Resolve a theme reference to a local directory containing ``theme.toml``.

    ``ref`` is either a short embedded name (``docs``) or a GitHub reference
    (``owner/repo[/path][@tag]``). For GitHub references the tarball is fetched
    and extracted under ``workdir``.
    """

    if "/" in ref:
        return fetch_github_theme(ref, workdir=workdir)

    path = embedded_themes_dir() / ref
    if not (path / "theme.toml").is_file():
        available = ", ".join(list_embedded_themes()) or "(none)"
        raise ThemeError(
            f"Unknown theme '{ref}'. Available embedded themes: {available}. "
            f"For a community theme use 'owner/repo[/path][@tag]'."
        )
    return path


def parse_github_ref(ref: str) -> tuple[str, str, str, str]:
    """Split ``owner/repo[/path][@tag]`` into (owner, repo, subpath, ref).

    ``ref`` defaults to ``main`` when no ``@tag`` is given.
    """

    location, _, tag = ref.partition("@")
    parts = location.strip("/").split("/")
    if len(parts) < 2 or not parts[0] or not parts[1]:
        raise ThemeError(
            f"Invalid theme reference '{ref}'. Expected 'owner/repo[/path][@tag]'."
        )
    owner, repo, *rest = parts
    subpath = "/".join(rest)
    return owner, repo, subpath, tag or "main"


def github_tarball_url(owner: str, repo: str, git_ref: str) -> str:
    return f"https://codeload.github.com/{owner}/{repo}/tar.gz/{git_ref}"


def fetch_github_theme(ref: str, *, workdir: Path) -> Path:
    """Download and extract a GitHub theme tarball; return its directory."""

    owner, repo, subpath, git_ref = parse_github_ref(ref)
    url = github_tarball_url(owner, repo, git_ref)

    extract_root = workdir / "download"
    extract_root.mkdir(parents=True, exist_ok=True)
    try:
        with urllib.request.urlopen(url) as response:  # noqa: S310 - https only
            with tarfile.open(fileobj=response, mode="r|gz") as archive:
                archive.extractall(extract_root, filter="data")
    except OSError as error:
        raise ThemeError(
            f"Could not fetch theme '{ref}' from {url}: {error}. "
            f"Check the reference and your network, or use an embedded theme."
        ) from error

    # The tarball wraps everything in a single '<repo>-<ref>/' top-level folder.
    roots = [entry for entry in extract_root.iterdir() if entry.is_dir()]
    if len(roots) != 1:
        raise ThemeError(f"Unexpected tarball layout for theme '{ref}'")
    theme_dir = roots[0] / subpath if subpath else roots[0]

    if not (theme_dir / "theme.toml").is_file():
        raise ThemeError(
            f"Theme '{ref}' has no theme.toml at {subpath or '<repo root>'}"
        )
    return theme_dir


def _parse_config(table: dict[str, object]) -> ThemeConfig:
    preset = table.get("preset")
    if not isinstance(preset, str) or preset not in VALID_PRESETS:
        raise ThemeError(
            f"theme.toml: [config].preset must be one of {sorted(VALID_PRESETS)}"
        )
    options = table.get("options", {})
    if not isinstance(options, dict):
        raise ThemeError("theme.toml: [config.options] must be a table")
    return ThemeConfig(
        preset=preset,
        src=_str(table, "src") or "content",
        out=_str(table, "out") or "public",
        options=options,
    )


def _table(
    data: dict[str, object], key: str, *, required: bool = True
) -> dict[str, object]:
    value = data.get(key)
    if value is None:
        if required:
            raise ThemeError(f"theme.toml: missing required [{key}] table")
        return {}
    if not isinstance(value, dict):
        raise ThemeError(f"theme.toml: [{key}] must be a table")
    return value


def _str(table: dict[str, object], key: str) -> str:
    value = table.get(key)
    return value if isinstance(value, str) else ""


def _str_list(table: dict[str, object], key: str) -> list[str]:
    value = table.get(key)
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]
