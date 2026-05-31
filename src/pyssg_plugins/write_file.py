"""WriteFile plugin: write collected outputs to the output directory.

Taps ``emit`` and writes every ``Output`` in the build to ``config.out``,
creating parent directories as needed.
"""

from __future__ import annotations

import shutil

from pyssg.build import Build
from pyssg.builder import Builder


class WriteFile:
    def __init__(self, *, clean: bool = False) -> None:
        self._clean = clean

    def apply(self, builder: Builder) -> None:
        builder.hooks.emit.tap("WriteFile", self._emit)

    def _emit(self, build: Build) -> None:
        out_dir = build.config.out
        if self._clean and out_dir.exists():
            shutil.rmtree(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        for output in build.outputs:
            dest = out_dir / output.path
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(output.content, encoding="utf-8")
