"""Contrib plugin: ``llms.txt`` / ``llms-full.txt`` output.

Emits an AI-consumable index of the site following the `llms.txt
<https://llmstxt.org/>`_ convention:

- ``/llms.txt`` -- a Markdown index: an ``# H1`` site title, a ``> blockquote``
  summary, then one ``## Section`` per top-level URL segment listing each page as
  ``- [title](absolute-url): excerpt``.
- ``/llms-full.txt`` -- the selected pages' Markdown bodies concatenated into a
  single document (separated by ``---``), so an agent can ingest the whole site in
  one fetch. Relative ``.md`` links inside the bodies are resolved to absolute
  site URLs (the bodies are pre-resolution Markdown, so the raw ``foo.md`` links
  would otherwise 404 on a site that serves clean URLs).

Honest positioning: the value is for IDE agents (Cursor/Cline/Aider) and MCP doc
servers that ingest a site as context -- not "SEO for AI". Prior art:
``mkdocs-llmstxt``.

Like the sitemap/rss plugins this is a *summarizer fan-in*: it taps
``evaluate_collections`` (after nav/taxonomy so every virtual page already
exists), scans the final graph for document-backed pages, and materializes one or
two virtual pages carrying the rendered text as ``content_html`` with
``template=None`` (the render contract for "emit verbatim, no layout"). It reads
only declared inputs -- page urls, document meta and the Markdown body kept on the
node (``__body__``), never the clock or the filesystem -- and sorts
deterministically, so two builds are byte-identical and an incremental rebuild
matches a full one.

Selection: pages are grouped/filtered by *section* (the first URL segment).
``include`` keeps only the listed sections (``None`` = all), ``exclude`` drops
sections, and a document can opt out entirely with ``llms: false`` in its
frontmatter. This plugin is stdlib only and pure; per the contrib rules it ships
tests and is not auto re-exported into ``pyssg.plugins``.
"""

from __future__ import annotations

import posixpath
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from pyssg.core.node import Document, Page
from pyssg.core.types import NodeKind
from pyssg.plugins._context import page_url_of
from pyssg.plugins.content_meta import slugify

if TYPE_CHECKING:
    from pyssg.core.build import Build
    from pyssg.core.builder import Builder

_INDEX_ID = "page:llms"
_INDEX_URL = "/llms.txt"
_FULL_ID = "page:llms-full"
_FULL_URL = "/llms-full.txt"

# Block separator and per-page header for llms-full.txt.
_SEPARATOR = "\n\n---\n\n"

# An inline Markdown link ``[text](target)``. Reference-style links and titled
# targets (``(foo.md "t")``) are intentionally left alone -- only bare relative
# ``.md`` targets are rewritten.
_MD_LINK = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")
_EXTERNAL = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")  # has a URL scheme (http:, mailto:)


@dataclass(frozen=True, slots=True)
class _Entry:
    """One selected page: the facts the two renderers consume."""

    section: str  # first URL segment, "" for a root page
    url: str
    link: str  # base_url + url
    title: str
    excerpt: str
    body: str  # raw Markdown body (frontmatter already stripped)


def _section_title(section: str) -> str:
    """Human header for a section; root pages (no segment) go under "Pages"."""
    return section.title() if section else "Pages"


def _body(doc: Document) -> str:
    """The document's Markdown body: ``__body__`` if frontmatter was split, else
    the raw file text, else empty. Mirrors the markdown plugin's own fallback."""
    body = doc.meta.get("__body__")
    if isinstance(body, str):
        return body
    raw = doc.meta.get("__raw__")
    return raw if isinstance(raw, str) else ""


def _resolve_links(build: Build, source_path: str | None, base_url: str, body: str) -> str:
    """Rewrite relative ``.md`` links in a Markdown body to absolute site URLs.

    The body kept on the node is the *pre-resolution* Markdown, so internal links
    still point at ``foo.md`` -- which 404s on a site that serves clean URLs. This
    resolves them the same way the ``link_resolver`` plugin resolves the HTML: a
    relative ``.md`` href maps to the target document's page URL (made absolute
    with ``base_url``), with any ``#fragment`` re-slugified. External/absolute/
    anchor links and links whose target has no page are left untouched.
    """
    if source_path is None:
        return body
    base_dir = posixpath.dirname(source_path)

    def _replace(match: re.Match[str]) -> str:
        text, href = match.group(1), match.group(2)
        if _EXTERNAL.match(href) or href.startswith(("/", "#")):
            return match.group(0)
        path, _, fragment = href.partition("#")
        if not path.endswith(".md"):
            return match.group(0)
        resolved = posixpath.normpath(posixpath.join(base_dir, path))
        target_url = page_url_of(build, f"path:{resolved[:-3]}")
        if target_url is None:
            return match.group(0)  # broken/suppressed target: leave it as-is
        url = f"{base_url}{target_url}"
        if fragment:
            url = f"{url}#{slugify(fragment)}"
        return f"[{text}]({url})"

    return _MD_LINK.sub(_replace, body)


def _entries(
    build: Build, include: tuple[str, ...] | None, exclude: tuple[str, ...]
) -> list[_Entry]:
    """Collect one :class:`_Entry` per selected document page, section/url-sorted.

    Only ``Page`` nodes with ``generated_from`` provenance are considered, so the
    virtual sitemap/rss/taxonomy pages -- and the llms pages themselves -- are
    excluded. A document opts out with ``llms: false``.
    """
    config = build.builder.config
    base_url = config.base_url if config is not None else ""

    out: list[_Entry] = []
    for node in build.graph.nodes():
        if not (isinstance(node, Page) and node.generated_from):
            continue
        doc = build.graph.get(node.generated_from[0])
        if not isinstance(doc, Document) or doc.kind is not NodeKind.MARKDOWN:
            continue
        if doc.meta.get("llms") is False:
            continue
        segments = [s for s in node.url.split("/") if s]
        section = segments[0] if segments else ""
        if include is not None and section not in include:
            continue
        if section in exclude:
            continue
        excerpt = doc.meta.get("excerpt")
        out.append(
            _Entry(
                section=section,
                url=node.url,
                link=f"{base_url}{node.url}",
                title=str(doc.meta.get("title") or node.url),
                excerpt=str(excerpt) if isinstance(excerpt, str) else "",
                body=_resolve_links(build, doc.source_path, base_url, _body(doc)),
            )
        )
    out.sort(key=lambda e: (e.section, e.url))
    return out


def render_index(*, title: str, summary: str, entries: list[_Entry]) -> str:
    """Render the ``/llms.txt`` Markdown index from selected entries."""
    lines = [f"# {title}"]
    if summary:
        lines.append("")
        lines.append(f"> {summary}")
    current: str | None = None
    for entry in entries:
        if entry.section != current:
            current = entry.section
            lines.append("")
            lines.append(f"## {_section_title(entry.section)}")
        suffix = f": {entry.excerpt}" if entry.excerpt else ""
        lines.append(f"- [{entry.title}]({entry.link}){suffix}")
    return "\n".join(lines) + "\n"


def render_full(entries: list[_Entry]) -> str:
    """Render ``/llms-full.txt``: each page's body under a title + source line."""
    blocks = [
        f"# {entry.title}\nSource: {entry.link}\n\n{entry.body.rstrip()}" for entry in entries
    ]
    return _SEPARATOR.join(blocks) + "\n"


def _set_page(build: Build, pid: str, url: str, title: str, text: str) -> None:
    """Create or update a virtual ``template=None`` page emitting ``text`` raw."""
    meta: dict[str, object] = {"title": title, "content_html": text}
    existing = build.graph.get(pid)
    if isinstance(existing, Page):
        existing.url = url
        existing.template = None
        existing.meta = meta
    else:
        build.graph.add_node(Page(id=pid, kind=NodeKind.PAGE, url=url, template=None, meta=meta))


def build_llms(
    build: Build,
    *,
    include: tuple[str, ...] | None = None,
    exclude: tuple[str, ...] = (),
    full: bool = True,
    title: str | None = None,
    summary: str | None = None,
) -> None:
    """Materialize the ``/llms.txt`` (and optional ``/llms-full.txt``) pages."""
    config = build.builder.config
    site = config.site if config is not None else {}
    index_title = title if title is not None else str(site.get("title") or "")
    index_summary = summary if summary is not None else str(site.get("description") or "")

    entries = _entries(build, include, exclude)
    _set_page(
        build,
        _INDEX_ID,
        _INDEX_URL,
        "llms.txt",
        render_index(title=index_title, summary=index_summary, entries=entries),
    )
    if full:
        _set_page(build, _FULL_ID, _FULL_URL, "llms-full.txt", render_full(entries))
    elif isinstance(build.graph.get(_FULL_ID), Page):
        # Drop a stale full page from a previous evaluation so the finalize
        # page-set diff deletes its output.
        build.graph.remove(_FULL_ID)


@dataclass(slots=True)
class LlmsPlugin:
    """Emits an ``llms.txt`` index (and optional ``llms-full.txt``) of the site."""

    include: tuple[str, ...] | None = None
    exclude: tuple[str, ...] = ()
    full: bool = True
    title: str | None = None
    summary: str | None = None
    name: str = "llms"
    cache_version: str = "1.0.0"

    def apply(self, builder: Builder) -> None:
        @builder.hooks.this_compilation.tap(self.name)
        def _wire(build: Build) -> None:
            @build.hooks.evaluate_collections.tap(self.name, after=("nav", "taxonomy"))
            def _eval(b: Build) -> None:
                build_llms(
                    b,
                    include=self.include,
                    exclude=self.exclude,
                    full=self.full,
                    title=self.title,
                    summary=self.summary,
                )


def llms(
    *,
    include: tuple[str, ...] | None = None,
    exclude: tuple[str, ...] = (),
    full: bool = True,
    title: str | None = None,
    summary: str | None = None,
) -> LlmsPlugin:
    """Factory used in ``pyssg.config.py``."""
    return LlmsPlugin(include=include, exclude=exclude, full=full, title=title, summary=summary)
