"""Internal link resolver.

Rewrites Markdown links to local ``.md`` files into the target page's resolved
URL, and records a LINK connection (reverse) per resolved link so backlinks work.
Runs during ``evaluate_collections`` -- after all documents are parsed and their
pages generated -- so every target URL is known.

Rewriting always starts from the document's pre-resolution HTML
(``__content_html_raw__``), so a target moving/renaming updates the link on the
*next* finalize even though the linking document was not itself re-parsed. The
rewritten ``content_html`` is re-hashed, which is what makes the render sweep
re-render a page whose link targets changed (keeping incremental == full).
"""

from __future__ import annotations

import posixpath
import re
from typing import TYPE_CHECKING
from urllib.parse import unquote

from pyssg.core.dependency import Dependency
from pyssg.core.node import Document
from pyssg.core.types import ConnectionKind, Phase
from pyssg.plugins._context import page_url_of
from pyssg.plugins.content_meta import slugify

if TYPE_CHECKING:
    from pyssg.core.build import Build
    from pyssg.core.builder import Builder

_HREF = re.compile(r'href="([^"]+)"')
_EXTERNAL = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")  # has a URL scheme (http:, mailto:)


def _target_id(linking_source: str, href_path: str) -> str:
    """Resolve a relative ``.md`` href to a path-based NodeId.

    ``href_path`` is percent-decoded first: a Markdown link to a file with spaces
    or non-ASCII characters (common in Obsidian vaults, e.g. Vietnamese titles) is
    stored URL-encoded in the source, but node ids use the real on-disk path, so
    the two only match once the href is decoded.
    """
    base_dir = posixpath.dirname(linking_source)
    resolved = posixpath.normpath(posixpath.join(base_dir, unquote(href_path)))
    return f"path:{resolved[:-3] if resolved.endswith('.md') else resolved}"


def _resolve_one(build: Build, doc: Document, href: str) -> str | None:
    """Resolve one href to a URL (and record a LINK edge), or None to leave it."""
    if _EXTERNAL.match(href) or href.startswith("/") or href.startswith("#"):
        return None
    path, _, fragment = href.partition("#")
    if not path.endswith(".md") or doc.source_path is None:
        return None
    target_id = _target_id(doc.source_path, path)
    target_url = page_url_of(build, target_id)
    if target_url is None:
        return None  # broken internal link: leave the original href (diagnostics later)
    build.create_connection(
        src=doc.id,
        dst=target_id,
        kind=ConnectionKind.LINK,
        dependency=Dependency(kind="link", request=href),
        sensitive_to=frozenset({"title", "url", "exists"}),
        restart_phase=Phase.RENDER,
        reverse=True,
    )
    return f"{target_url}#{slugify(fragment)}" if fragment else target_url


def rewrite_links(build: Build, html: str, doc: Document) -> str:
    """finalize_content tap: rewrite internal ``.md`` links + record LINK edges."""

    def _replace(match: re.Match[str]) -> str:
        resolved = _resolve_one(build, doc, match.group(1))
        return f'href="{resolved}"' if resolved is not None else match.group(0)

    return _HREF.sub(_replace, html)


class LinkResolverPlugin:
    """Resolves and rewrites internal Markdown links."""

    name = "link_resolver"
    cache_version = "1.1.0"

    def apply(self, builder: Builder) -> None:
        @builder.hooks.this_compilation.tap(self.name)
        def _wire(build: Build) -> None:
            # Stage 200: after wikilink (100), so both rewrite the same HTML.
            @build.hooks.finalize_content.tap(self.name, stage=200)
            def _rewrite(html: str, doc: Document) -> str:
                return rewrite_links(build, html, doc)


def link_resolver() -> LinkResolverPlugin:
    """Factory used in ``pyssg.config.py``."""
    return LinkResolverPlugin()
