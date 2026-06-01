"""Transclusion plugin: Obsidian-style ``![[...]]`` embeds.

Embeds one document's finalized content into another. Runs in ``expand_content``
(after wikilink/link resolution), expanding recursively with **cycle detection**
(A embeds B embeds A is rejected). Embedding is a deterministic
function of the final graph, so incremental output stays identical to a full
build; a host re-renders when an embedded document changes because the render
sweep recomputes its content each finalize.

v1 embeds whole notes; section/block-granular embeds (``#heading`` / ``#^id``)
fall back to the whole note.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

from pyssg.core.dependency import Dependency
from pyssg.core.node import Document
from pyssg.core.types import ConnectionKind, NodeKind, Phase

if TYPE_CHECKING:
    from pyssg.core.build import Build
    from pyssg.core.builder import Builder

_EMBED = re.compile(r"!\[\[([^\]|#]+?)(#[^\]|]+)?(\|[^\]]+)?\]\]")


def _name_index(build: Build) -> dict[str, str]:
    index: dict[str, str] = {}
    for node in build.graph.nodes():
        if not (isinstance(node, Document) and node.kind is NodeKind.MARKDOWN):
            continue
        if node.source_path:
            index.setdefault(Path(node.source_path).stem.lower(), node.id)
        title = node.meta.get("title")
        if isinstance(title, str):
            index.setdefault(title.lower(), node.id)
    return index


def expand_transclusions(build: Build) -> None:
    """``expand_content`` tap: replace ``![[...]]`` with embedded content."""
    index = _name_index(build)
    memo: dict[str, str] = {}

    def content_of(doc: Document) -> str:
        raw = doc.meta.get("content_html")
        return raw if isinstance(raw, str) else ""

    def expand(doc: Document, stack: tuple[str, ...]) -> str:
        if doc.id in memo:
            return memo[doc.id]

        def _replace(match: re.Match[str]) -> str:
            target = match.group(1).strip()
            target_id = index.get(target.lower())
            if target_id is None:
                return f'<div class="broken-embed">missing: {target}</div>'
            if target_id in stack or target_id == doc.id:
                return f'<div class="embed-cycle">transclusion cycle: {target}</div>'
            target_node = build.graph.get(target_id)
            if not isinstance(target_node, Document):
                return f'<div class="broken-embed">missing: {target}</div>'
            build.create_connection(
                src=doc.id,
                dst=target_id,
                kind=ConnectionKind.EMBED,
                dependency=Dependency(kind="embed", request=match.group(0)),
                sensitive_to=frozenset({"content_html"}),
                restart_phase=Phase.RENDER,
                reverse=False,
            )
            inner = expand(target_node, (*stack, doc.id))
            return f'<div class="transclusion">{inner}</div>'

        expanded = _EMBED.sub(_replace, content_of(doc))
        memo[doc.id] = expanded
        return expanded

    for node in build.graph.nodes():
        if isinstance(node, Document) and node.kind is NodeKind.MARKDOWN:
            node.meta["content_html"] = expand(node, ())


class TranscludePlugin:
    """Obsidian-style ``![[...]]`` transclusion."""

    name = "transclude"
    cache_version = "1.0.0"

    def apply(self, builder: Builder) -> None:
        @builder.hooks.this_compilation.tap(self.name)
        def _wire(build: Build) -> None:
            @build.hooks.expand_content.tap(self.name)
            def _expand(b: Build) -> None:
                expand_transclusions(b)


def transclude() -> TranscludePlugin:
    """Factory used in ``pyssg.config.py``."""
    return TranscludePlugin()
