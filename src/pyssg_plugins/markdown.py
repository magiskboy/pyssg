"""Markdown plugin: render ``source.body`` to HTML into ``source.content``.

Taps ``transform`` (waterfall). Uses python-markdown, imported lazily so the
dependency is only required when the plugin is actually used -- the kernel
stays dependency-free. Install with ``pip install pyssg[markdown]``.
"""

from __future__ import annotations

from collections.abc import Sequence

from pyssg.build import Build
from pyssg.builder import Builder
from pyssg.models import Source


class Markdown:
    def __init__(self, extensions: Sequence[str] = ()) -> None:
        self._extensions = list(extensions)

    def apply(self, builder: Builder) -> None:
        builder.hooks.transform.tap("Markdown", self._transform)

    def _transform(self, source: Source, build: Build) -> Source:
        import markdown

        source.content = markdown.markdown(source.body, extensions=self._extensions)
        return source
