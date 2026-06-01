"""Permalink plugin.

Generator that turns each markdown ``Document`` into an output ``Page`` with a
URL. The default route is file-based (``content/guide/intro.md`` ->
``/guide/intro/``; an ``index`` file maps to its directory root). The frontmatter
keys ``permalink`` / ``url`` override it, and ``template`` selects the layout
template.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pyssg.core.node import Page
from pyssg.core.types import NodeKind

if TYPE_CHECKING:
    from pyssg.core.build import Build
    from pyssg.core.builder import Builder
    from pyssg.core.node import Node


def compute_url(node: Node) -> str:
    """File-based URL with frontmatter override."""
    override = node.meta.get("permalink") or node.meta.get("url")
    if isinstance(override, str):
        return override
    source = node.source_path or ""
    rel = source[:-3] if source.endswith(".md") else source
    parts = [segment for segment in rel.split("/") if segment]
    if parts and parts[-1] == "index":
        parts = parts[:-1]
    return "/" + "".join(f"{segment}/" for segment in parts)


def _opt_str(value: object) -> str | None:
    return value if isinstance(value, str) else None


class PermalinkPlugin:
    """Generates a routed Page per document."""

    name = "permalink"
    cache_version = "1.0.0"

    def apply(self, builder: Builder) -> None:
        @builder.hooks.this_compilation.tap(self.name)
        def _wire(build: Build) -> None:
            @build.hooks.generate.tap(self.name)
            def _generate(node: Node) -> None:
                if node.kind is not NodeKind.MARKDOWN:
                    return
                if node.meta.get("draft") is True:
                    return  # drafts produce no page
                url = build.hooks.route.call(compute_url(node), node)
                build.emit_page(
                    Page(
                        id=f"page:{node.id}",
                        kind=NodeKind.PAGE,
                        url=url,
                        generated_from=[node.id],
                        template=_opt_str(node.meta.get("template")),
                    )
                )


def permalink() -> PermalinkPlugin:
    """Factory used in ``pyssg.config.py``."""
    return PermalinkPlugin()
