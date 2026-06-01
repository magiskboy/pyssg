"""Wikilink plugin: Obsidian-style ``[[...]]``.

Resolves ``[[Note]]``, ``[[Note|display]]`` and ``[[Note#Heading]]`` against the
whole document set (by file stem, then title), rewrites them to anchors, and
records a LINK connection (reverse) per resolved link so backlinks work.
Embeds (``![[...]]``) are left for the transclude plugin.

Runs as a ``finalize_content`` tap (stage 100, before internal links at 200), so
every document is already parsed and its page URL is known. A broken wikilink
renders as a ``<span class="broken-link">`` rather than vanishing.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

from pyssg.core.dependency import Dependency
from pyssg.core.node import Document
from pyssg.core.types import ConnectionKind, NodeKind, Phase
from pyssg.plugins._context import page_url_of
from pyssg.plugins.content_meta import slugify

if TYPE_CHECKING:
    from pyssg.core.build import Build
    from pyssg.core.builder import Builder

# [[target]], [[target|display]], [[target#heading]] - but NOT ![[...]] (embed).
_WIKILINK = re.compile(r"(?<!!)\[\[([^\]|#]+?)(#[^\]|]+)?(\|[^\]]+)?\]\]")
_INDEX_KEY = "__wikilink_index__"


def _index(build: Build) -> dict[str, str]:
    """name -> doc id, by file stem and title (lowercased), built once per build."""
    cached = build.site_data.get(_INDEX_KEY)
    if isinstance(cached, dict):
        return {str(k): str(v) for k, v in cached.items()}
    index: dict[str, str] = {}
    for node in build.graph.nodes():
        if not (isinstance(node, Document) and node.kind is NodeKind.MARKDOWN):
            continue
        if node.source_path:
            index.setdefault(Path(node.source_path).stem.lower(), node.id)
        title = node.meta.get("title")
        if isinstance(title, str):
            index.setdefault(title.lower(), node.id)
    build.site_data[_INDEX_KEY] = index
    return index


def rewrite_wikilinks(build: Build, html: str, doc: Document) -> str:
    """finalize_content tap: resolve ``[[...]]`` and record LINK edges."""
    index = _index(build)

    def _replace(match: re.Match[str]) -> str:
        target = match.group(1).strip()
        anchor = match.group(2)
        display = match.group(3)[1:] if match.group(3) else target
        target_id = index.get(target.lower())
        if target_id is None:
            return f'<span class="broken-link">{display}</span>'
        url = page_url_of(build, target_id)
        if url is None:
            return f'<span class="broken-link">{display}</span>'
        if anchor:
            url = f"{url}#{slugify(anchor[1:])}"
        build.create_connection(
            src=doc.id,
            dst=target_id,
            kind=ConnectionKind.LINK,
            dependency=Dependency(kind="wikilink", request=match.group(0)),
            sensitive_to=frozenset({"title", "url", "exists"}),
            restart_phase=Phase.RENDER,
            reverse=True,
        )
        return f'<a href="{url}">{display}</a>'

    return _WIKILINK.sub(_replace, html)


class WikilinkPlugin:
    """Obsidian-style ``[[...]]`` links."""

    name = "wikilink"
    cache_version = "1.0.0"

    def apply(self, builder: Builder) -> None:
        @builder.hooks.this_compilation.tap(self.name)
        def _wire(build: Build) -> None:
            @build.hooks.finalize_content.tap(self.name, stage=100)
            def _rewrite(html: str, doc: Document) -> str:
                return rewrite_wikilinks(build, html, doc)


def wikilink() -> WikilinkPlugin:
    """Factory used in ``pyssg.config.py``."""
    return WikilinkPlugin()
