"""Fingerprint plugin: content-hash assets for cache-busting.

Renames ``style.css`` to ``style.<hash>.css`` (the hash derived from the file
content) and rewrites every reference so browsers can cache each asset forever
yet pick up a new file the instant its content changes.

It owns a static asset directory end to end -- use it *instead of* ``StaticFiles``
for that directory. Files whose extension is fingerprinted (``.css``/``.js`` by
default) are copied under their hashed name and recorded in a manifest; every
other file is copied verbatim.

Three taps cover the lifecycle:

- ``collect`` builds the manifest (logical URL -> hashed URL) onto
  ``build.meta["assets"]`` and registers an ``asset()`` template global through
  the shared ``build.meta["template_globals"]`` seam, so a layout can opt in
  explicitly with ``{{ asset('/assets/style.css') }}``.
- ``optimize`` (before ``Minify``) rewrites the logical URLs to hashed URLs in
  every HTML output -- catching references hard-coded in markdown or templates,
  and ``og:image``/canonical tags the Seo plugin emitted, so neither needs to
  know the hash.
- ``emit`` (after ``WriteFile``'s clean) copies the files to the output dir.

Scope: only references inside HTML outputs are rewritten. ``url(...)`` inside CSS
is left untouched, so fingerprinting images that CSS references would break those
links; the default extension set avoids that by fingerprinting ``.css``/``.js``
only.
"""

from __future__ import annotations

import hashlib
import re
import shutil
from collections.abc import Sequence
from pathlib import Path

from pyssg.build import Build
from pyssg.builder import Builder

# build.meta keys
ASSETS = "assets"
_PLAN = "_fingerprint_plan"

# Rewrite before Minify (stage 0); copy after WriteFile's clean (stage 0).
_OPTIMIZE_STAGE = -100
_EMIT_STAGE = 100


class Fingerprint:
    def __init__(
        self,
        directory: str = "assets",
        *,
        dest: str = "assets",
        extensions: Sequence[str] = (".css", ".js"),
        hash_length: int = 8,
        rewrite_suffixes: Sequence[str] = (".html", ".htm"),
        asset_global: bool = True,
    ) -> None:
        self._directory = directory
        self._dest = dest
        self._extensions = {_dot(ext) for ext in extensions}
        self._hash_length = hash_length
        self._rewrite_suffixes = {_dot(suffix) for suffix in rewrite_suffixes}
        self._asset_global = asset_global

    def apply(self, builder: Builder) -> None:
        builder.hooks.collect.tap("Fingerprint", self._collect)
        builder.hooks.optimize.tap("Fingerprint", self._optimize, stage=_OPTIMIZE_STAGE)
        builder.hooks.emit.tap("Fingerprint", self._emit, stage=_EMIT_STAGE)

    def _collect(self, build: Build) -> None:
        directory = Path(self._directory)
        manifest: dict[str, str] = {}
        plan: list[tuple[str, str]] = []

        if directory.is_dir():
            for path in sorted(directory.rglob("*")):
                if not path.is_file():
                    continue
                relpath = path.relative_to(directory)
                if path.suffix.lower() in self._extensions:
                    digest = _content_hash(path, self._hash_length)
                    hashed = relpath.with_name(f"{relpath.stem}.{digest}{path.suffix}")
                    manifest[_url(self._dest, relpath)] = _url(self._dest, hashed)
                    plan.append((str(path), _out_rel(self._dest, hashed)))
                else:
                    plan.append((str(path), _out_rel(self._dest, relpath)))

        build.meta[ASSETS] = manifest
        build.meta[_PLAN] = plan
        self._register_asset_global(build)

    def _optimize(self, build: Build) -> None:
        manifest = build.meta.get(ASSETS)
        if not isinstance(manifest, dict) or not manifest:
            return
        pattern = _rewrite_pattern(manifest)

        def replace(match: re.Match[str]) -> str:
            return str(manifest[match.group(0)])

        for output in build.outputs:
            if output.path.suffix.lower() in self._rewrite_suffixes:
                output.content = pattern.sub(replace, output.content)

    def _emit(self, build: Build) -> None:
        plan = build.meta.get(_PLAN)
        if not isinstance(plan, list):
            return
        out_dir = build.config.out
        for entry in plan:
            src, rel = entry
            dest = out_dir / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)

    def _register_asset_global(self, build: Build) -> None:
        if not self._asset_global:
            return
        try:
            asset = _make_asset_global()
        except ImportError:
            # jinja2 absent: rewriting still works without the template helper.
            return
        template_globals = build.meta.setdefault("template_globals", {})
        if isinstance(template_globals, dict):
            template_globals["asset"] = asset


def _make_asset_global() -> object:
    """Build the ``asset()`` Jinja global mapping a logical URL to its hash.

    Reads the manifest from the render context (``pass_context``) so it needs no
    closure over a specific build and stays correct across dev-server rebuilds.
    """

    import jinja2

    @jinja2.pass_context
    def asset(context: jinja2.runtime.Context, path: str) -> str:
        manifest = context.get(ASSETS)
        if isinstance(manifest, dict):
            resolved = manifest.get(path)
            if isinstance(resolved, str):
                return resolved
        return path

    return asset


def _rewrite_pattern(manifest: dict[str, str]) -> re.Pattern[str]:
    # Longest first so a logical URL that is a prefix of another does not win.
    keys = sorted(manifest, key=len, reverse=True)
    alternation = "|".join(re.escape(key) for key in keys)
    return re.compile(f"(?:{alternation})(?![A-Za-z0-9._-])")


def _content_hash(path: Path, length: int) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:length]


def _url(dest: str, relpath: Path) -> str:
    parts = [part for part in (dest.strip("/"), relpath.as_posix()) if part]
    return "/" + "/".join(parts)


def _out_rel(dest: str, relpath: Path) -> str:
    cleaned = dest.strip("/")
    return f"{cleaned}/{relpath.as_posix()}" if cleaned else relpath.as_posix()


def _dot(value: str) -> str:
    value = value.lower()
    return value if value.startswith(".") else f".{value}"
