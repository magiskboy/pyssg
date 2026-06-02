"""Frontmatter plugin.

Splits a leading YAML frontmatter block (delimited by ``---`` lines) off the raw
content, merges its keys into ``node.meta`` (the ``frontmatter`` aspect), and
stores the remaining body under ``__body__`` for the markdown parser. Runs in an
early parse stage so the markdown plugin sees the stripped body.

Third-party (``PyYAML``) is confined to this peripheral plugin.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import yaml

from pyssg.core.types import NodeKind

if TYPE_CHECKING:
    from pyssg.core.build import Build
    from pyssg.core.builder import Builder
    from pyssg.core.node import Node

# Frontmatter must start at the very top: '---\n' ... '\n---' then the body.
_FRONTMATTER = re.compile(r"^---\n(?P<meta>.*?)\n---[ \t]*\n?(?P<body>.*)$", re.DOTALL)

_PARSE_STAGE = 100  # before markdown (200)


def split_frontmatter(raw: str) -> tuple[dict[str, object], str]:
    """Return ``(metadata, body)``; metadata is empty if there is no frontmatter.

    Malformed YAML in the block is tolerated rather than fatal: a document whose
    frontmatter cannot be parsed (e.g. an Obsidian template note containing
    ``date: {{date}}``) is treated as having no frontmatter, keeping its body, so
    one stray file never aborts the whole build. The outcome is a deterministic
    function of the input, so the build-twice invariant still holds.
    """
    match = _FRONTMATTER.match(raw)
    if match is None:
        return {}, raw
    try:
        parsed: object = yaml.safe_load(match.group("meta"))
    except yaml.YAMLError:
        return {}, match.group("body")
    if not isinstance(parsed, dict):
        return {}, match.group("body")
    meta = {str(key): value for key, value in parsed.items()}
    return meta, match.group("body")


class FrontmatterPlugin:
    """Extracts YAML frontmatter into ``node.meta``."""

    name = "frontmatter"
    cache_version = "1.0.0"

    def apply(self, builder: Builder) -> None:
        @builder.hooks.this_compilation.tap(self.name)
        def _wire(build: Build) -> None:
            @build.hooks.parse.tap(self.name, stage=_PARSE_STAGE)
            def _parse(node: Node) -> None:
                if node.kind is not NodeKind.MARKDOWN:
                    return
                raw = node.meta.get("__raw__")
                if not isinstance(raw, str):
                    return
                meta, body = split_frontmatter(raw)
                node.meta.update(meta)
                node.meta["__body__"] = body


def frontmatter() -> FrontmatterPlugin:
    """Factory used in ``pyssg.config.py``."""
    return FrontmatterPlugin()
