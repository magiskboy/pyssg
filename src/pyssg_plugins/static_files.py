"""StaticFiles plugin: copy a directory of static assets into the output.

Taps ``emit`` (after the page outputs are written) and copies every file under
``directory`` into ``out/dest``, preserving the subtree. Use it for CSS, JS,
images and any other file that should be served verbatim.

``directory`` is resolved relative to the current working directory, like
``Config.src`` and ``Config.out``.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from pyssg.build import Build
from pyssg.builder import Builder

# StaticFiles runs after WriteFile (stage 0) so a clean build does not wipe it.
_EMIT_STAGE = 100


class StaticFiles:
    def __init__(self, directory: str, *, dest: str = "") -> None:
        self._directory = directory
        self._dest = dest

    def apply(self, builder: Builder) -> None:
        builder.hooks.emit.tap("StaticFiles", self._emit, stage=_EMIT_STAGE)

    def _emit(self, build: Build) -> None:
        source_dir = Path(self._directory)
        if not source_dir.is_dir():
            return

        dest_root = build.config.out / self._dest
        for path in source_dir.rglob("*"):
            if not path.is_file():
                continue
            relative = path.relative_to(source_dir)
            dest = dest_root / relative
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dest)
