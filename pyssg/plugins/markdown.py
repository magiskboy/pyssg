"""Markdown loader + parser plugin.

Loads ``.md`` files (``load_node``) and, in the parse phase, turns the body into
an AST (markdown-it tokens) and rendered ``content_html``. Frontmatter splitting
runs in an earlier parse stage (see the frontmatter plugin), so this plugin reads
``__body__`` if present, falling back to the raw text.

Third-party (``markdown-it-py``) lives only in this peripheral plugin, never in
``pyssg.core``.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from markdown_it import MarkdownIt
from markdown_it.token import Token

from pyssg.core.node import Document
from pyssg.core.types import NodeKind

if TYPE_CHECKING:
    from pyssg.core.build import Build
    from pyssg.core.builder import Builder
    from pyssg.core.node import Node

# Parse-stage ordering: frontmatter (100) strips YAML before markdown (200) renders.
_PARSE_STAGE = 200


def _text(value: object) -> str:
    return value if isinstance(value, str) else ""


def _first_heading(tokens: list[Token]) -> str | None:
    """Text of the first heading in the token stream, if any."""
    for i, tok in enumerate(tokens):
        if tok.type == "heading_open" and i + 1 < len(tokens):
            inline = tokens[i + 1]
            if inline.type == "inline" and inline.content:
                return inline.content
    return None


def _derive_title(node: Document, tokens: list[Token]) -> str:
    """Title precedence: frontmatter ``title`` -> first heading -> file stem."""
    existing = node.meta.get("title")
    if isinstance(existing, str) and existing:
        return existing
    heading = _first_heading(tokens)
    if heading:
        return heading
    return Path(node.source_path).stem if node.source_path else node.id


class MarkdownPlugin:
    """Parses Markdown documents to HTML via markdown-it."""

    name = "markdown"
    cache_version = "1.0.0"

    def __init__(self) -> None:
        # One parser instance, configured deterministically. commonmark preset.
        self._md = MarkdownIt("commonmark")

    def apply(self, builder: Builder) -> None:
        @builder.hooks.this_compilation.tap(self.name)
        def _wire(build: Build) -> None:
            @build.hooks.load_node.tap(self.name)
            def _load(path: str) -> Node | None:
                if not path.endswith(".md"):
                    return None
                node = Document(id=path, kind=NodeKind.MARKDOWN, source_path=path)
                node.meta["__raw__"] = Path(path).read_text(encoding="utf-8")
                return node

            @build.hooks.parse.tap(self.name, stage=_PARSE_STAGE)
            def _parse(node: Node) -> None:
                if node.kind is not NodeKind.MARKDOWN or not isinstance(node, Document):
                    return
                body = node.meta.get("__body__")
                text = _text(body) if body is not None else _text(node.meta.get("__raw__"))
                tokens: list[Token] = self._md.parse(text)
                node.ast = tokens
                html = self._md.render(text)
                node.meta["content_html"] = html
                # Keep the pre-link-resolution HTML so link_resolver can rewrite
                # from a stable source on every finalize.
                node.meta["__content_html_raw__"] = html
                node.meta["title"] = _derive_title(node, tokens)


def markdown() -> MarkdownPlugin:
    """Factory used in ``pyssg.config.py``."""
    return MarkdownPlugin()
