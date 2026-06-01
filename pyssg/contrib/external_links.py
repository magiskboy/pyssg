"""Contrib plugin: open external links in a new tab, safely.

Rewrites anchors pointing at an absolute ``http(s)://`` URL so they carry
``target="_blank"`` and a ``rel`` that prevents the new tab from reaching back
into the opener (``noopener noreferrer`` by default). Internal links (resolved
to site-relative URLs by the ``link_resolver`` plugin) are left untouched.

It taps ``finalize_content`` at stage 300 -- after wikilink (100) and internal
link resolution (200) -- so it only sees the final hrefs. The rewrite is a pure
function of the HTML, so builds stay byte-identical and incremental rebuilds
match full rebuilds.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pyssg.core.build import Build
    from pyssg.core.builder import Builder
    from pyssg.core.node import Document

# A full anchor opening tag; ``[^>]*`` captures every attribute so we can both
# detect an external href and tell whether a target is already present.
_ANCHOR = re.compile(r"<a (?P<attrs>[^>]*)>")
_EXTERNAL_HREF = re.compile(r'href="https?://[^"]*"')


def rewrite_external_links(html: str, *, target: str, rel: str) -> str:
    """Add ``target``/``rel`` to external http(s) anchors that lack them."""

    def _augment(match: re.Match[str]) -> str:
        attrs = match.group("attrs")
        # Only external links, and stay idempotent: skip tags already carrying a
        # target (checking the whole attribute string, wherever the href sits).
        if not _EXTERNAL_HREF.search(attrs) or "target=" in attrs:
            return match.group(0)
        return f'<a {attrs} target="{target}" rel="{rel}">'

    return _ANCHOR.sub(_augment, html)


class ExternalLinksPlugin:
    """Marks external links to open in a new, isolated tab."""

    name = "external_links"
    cache_version = "1.0.0"

    def __init__(self, *, target: str = "_blank", rel: str = "noopener noreferrer") -> None:
        self._target = target
        self._rel = rel

    def apply(self, builder: Builder) -> None:
        @builder.hooks.this_compilation.tap(self.name)
        def _wire(build: Build) -> None:
            @build.hooks.finalize_content.tap(self.name, stage=300)
            def _rewrite(html: str, _doc: Document) -> str:
                return rewrite_external_links(html, target=self._target, rel=self._rel)


def external_links(
    *, target: str = "_blank", rel: str = "noopener noreferrer"
) -> ExternalLinksPlugin:
    """Factory used in ``pyssg.config.py``."""
    return ExternalLinksPlugin(target=target, rel=rel)
