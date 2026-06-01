"""Asset-copy plugin.

Copies the active layout's ``assets/`` directory into the build output under
``/assets/...``, preserving the directory structure. A file is (re)written only
when it is missing from the output or its bytes differ from the source, so
rebuilds stay cheap and the output is byte-identical to a full rebuild.

The copy is keyed on ``evaluate_collections`` because that hook fires once per
finalize and the layout's ``assets_dir`` is the only input -- the copy is a
deterministic function of the source bytes (no clock, no globals). It never
deletes files it did not place, so user/output files are left untouched.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pyssg.core.build import Build
    from pyssg.core.builder import Builder

_OUTPUT_SUBDIR = "assets"


def _output_assets_root(build: Build) -> Path | None:
    """Resolve the output ``assets/`` directory, or None if unavailable."""
    config = build.builder.config
    if config is None:
        return None
    return build.builder.site_dir / config.output_dir / _OUTPUT_SUBDIR


def _needs_copy(src: Path, dst: Path) -> bool:
    """True when ``dst`` is absent or its bytes differ from ``src``.

    Comparing bytes (rather than mtime/size) keeps the result independent of the
    filesystem clock, so an unchanged asset is never rewritten on rebuild.
    """
    if not dst.exists():
        return True
    return src.read_bytes() != dst.read_bytes()


def copy_assets(build: Build) -> None:
    """Mirror the layout ``assets/`` tree into the output ``assets/`` tree."""
    layout = build.builder.layout
    if layout is None or layout.assets_dir is None:
        return
    dest_root = _output_assets_root(build)
    if dest_root is None:
        return

    src_root = layout.assets_dir
    # Deterministic traversal order; copying order has no observable effect but
    # a stable walk keeps behaviour predictable and easy to reason about.
    for src in sorted(p for p in src_root.rglob("*") if p.is_file()):
        rel = src.relative_to(src_root)
        dst = dest_root / rel
        if _needs_copy(src, dst):
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dst)


class AssetCopyPlugin:
    """Built-in copier for the layout's static assets."""

    name = "asset_copy"
    cache_version = "1.0.0"

    def apply(self, builder: Builder) -> None:
        @builder.hooks.this_compilation.tap(self.name)
        def _wire(build: Build) -> None:
            @build.hooks.evaluate_collections.tap(self.name)
            def _eval(b: Build) -> None:
                copy_assets(b)


def asset_copy() -> AssetCopyPlugin:
    """Factory used in ``pyssg.config.py``."""
    return AssetCopyPlugin()
