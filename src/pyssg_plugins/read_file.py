"""ReadFile plugin: discover source files and read their raw content.

Taps ``discover`` to walk the input directory and ``load`` to read each file.
Only files matching ``patterns`` are picked up, so other plugins can own other
extensions. Reading is bail-style: the first plugin to return text for a source
wins, leaving room for binary/asset loaders later.
"""

from __future__ import annotations

from pyssg.build import Build
from pyssg.builder import Builder
from pyssg.errors import BuildError
from pyssg.models import Source


class ReadFile:
    def __init__(self, patterns: tuple[str, ...] = ("*.md",)) -> None:
        self._patterns = patterns

    def apply(self, builder: Builder) -> None:
        builder.hooks.discover.tap("ReadFile", self._discover)
        builder.hooks.load.tap("ReadFile", self._load)

    def _discover(self, build: Build) -> None:
        src = build.config.src
        if not src.exists():
            raise BuildError(
                f"Source directory not found: {src}. Are you running from the "
                "project root? Create it, or set 'src' in pyssg.config.py."
            )
        if not src.is_dir():
            raise BuildError(f"Source path is not a directory: {src}.")
        seen: set[str] = set()
        for pattern in self._patterns:
            for path in sorted(src.rglob(pattern)):
                if not path.is_file():
                    continue
                key = str(path)
                if key in seen:
                    continue
                seen.add(key)
                build.sources.append(Source(path=path, relpath=path.relative_to(src)))

    def _load(self, source: Source, build: Build) -> None:
        if not source.raw:
            source.raw = source.path.read_text(encoding="utf-8")
