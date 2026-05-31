"""MarkdownPage plugin: serve a raw-markdown twin of every page for AI agents.

As agents increasingly read web pages on a human's behalf, a faithful markdown
source is cheaper and more reliable for them to consume than rendered HTML. This
plugin exposes that source through three complementary, individually toggleable
layers, all standard library only:

1. A per-page ``.md`` companion. Following the widely used "append ``.md`` to the
   URL" convention (Mintlify, Anthropic docs), the page at ``/guide/intro/`` is
   also served at ``/guide/intro.md`` and the home page ``/`` at ``/index.md``.
2. An ``llms.txt`` index at the site root (see llmstxt.org): a single markdown
   file listing every page and linking to its ``.md`` twin, so an agent can
   discover the whole site from one entry point.
3. A ``<link rel="alternate" type="text/markdown">`` hint injected into each
   page's ``<head>``, so an agent that landed on the HTML can find the twin.

Layers 2 and 3 default on but can be disabled. The companion file's contents are
configurable: ``source.body`` only by default, optionally prefixed with the
original frontmatter block and/or a title heading.

Taps ``generate`` (read-only over rendered sources) to emit the ``.md`` files and
``llms.txt``, and ``optimize`` (before Minify) to inject the discovery hint.
"""

from __future__ import annotations

import re
from pathlib import Path

from pyssg.build import Build
from pyssg.builder import Builder
from pyssg.content import (
    URL,
    absolute_url,
    is_generated,
    public_pages,
    site,
)
from pyssg.models import Output, Source

# Emit alongside the other generators (Sitemap/Robots), after listing pages
# exist -- they are skipped anyway, but the timing keeps the model consistent.
_GENERATE_STAGE = 100
# Inject the discovery hint before Minify (optimize stage 0) collapses the head.
_OPTIMIZE_STAGE = -100

_HEADING_RE = re.compile(r"^\s{0,3}#")
_HEAD_CLOSE_RE = re.compile(r"</head\s*>", re.IGNORECASE)
_HTML_SUFFIXES = (".html", ".htm")
_FRONTMATTER_DELIMITER = "---"


class MarkdownPage:
    def __init__(
        self,
        *,
        llms_txt: bool = True,
        llms_path: str = "llms.txt",
        html_link: bool = True,
        include_title: bool = False,
        include_frontmatter: bool = False,
    ) -> None:
        self._llms_txt = llms_txt
        self._llms_path = llms_path
        self._html_link = html_link
        self._include_title = include_title
        self._include_frontmatter = include_frontmatter

    def apply(self, builder: Builder) -> None:
        builder.hooks.generate.tap(
            "MarkdownPage", self._generate, stage=_GENERATE_STAGE
        )
        if self._html_link:
            builder.hooks.optimize.tap(
                "MarkdownPage", self._inject_links, stage=_OPTIMIZE_STAGE
            )

    def _generate(self, build: Build) -> None:
        pages = _markdown_pages(build)
        for source in pages:
            md_url = markdown_url(str(source.meta[URL]))
            build.outputs.append(
                Output(
                    path=Path(md_url.lstrip("/")),
                    content=self._content(source),
                    source=source,
                )
            )
        if self._llms_txt:
            base_url = str(site(build).get("base_url", ""))
            document = _llms_index(site(build), pages, base_url)
            build.outputs.append(Output(path=Path(self._llms_path), content=document))

    def _inject_links(self, build: Build) -> None:
        for output in build.outputs:
            source = output.source
            if source is None or output.path.suffix.lower() not in _HTML_SUFFIXES:
                continue
            url = source.meta.get(URL)
            if not isinstance(url, str) or not url:
                continue
            output.content = _inject_alternate(output.content, markdown_url(url))

    def _content(self, source: Source) -> str:
        parts: list[str] = []
        if self._include_frontmatter:
            block = _frontmatter_block(source.raw)
            if block:
                parts.append(block)
        if self._include_title and not _HEADING_RE.match(source.body):
            title = source.frontmatter.get("title")
            if isinstance(title, str) and title:
                parts.append(f"# {title}")
        if source.body:
            parts.append(source.body)
        return "\n\n".join(parts).rstrip("\n") + "\n"


def _markdown_pages(build: Build) -> list[Source]:
    """Public, non-synthetic pages -- the ones backed by real markdown source."""

    return [source for source in public_pages(build) if not is_generated(source)]


def markdown_url(url: str) -> str:
    """Map a page URL to its ``.md`` twin URL.

    ``/guide/intro/`` -> ``/guide/intro.md``; ``/`` -> ``/index.md``;
    ``/foo.html`` -> ``/foo.md``.
    """

    if url.endswith("/"):
        return "/index.md" if url == "/" else url[:-1] + ".md"
    if url.endswith(".html"):
        return url[: -len(".html")] + ".md"
    return url + ".md"


def _inject_alternate(html: str, md_url: str) -> str:
    if 'type="text/markdown"' in html:
        return html
    tag = (
        f'<link rel="alternate" type="text/markdown" href="{md_url}" title="Markdown">'
    )
    match = _HEAD_CLOSE_RE.search(html)
    if match is None:
        return html
    return html[: match.start()] + tag + html[match.start() :]


def _frontmatter_block(raw: str) -> str:
    """Return the verbatim leading ``---`` frontmatter block, or ``""``."""

    if not raw.startswith(_FRONTMATTER_DELIMITER):
        return ""
    lines = raw.splitlines()
    if not lines or lines[0].strip() != _FRONTMATTER_DELIMITER:
        return ""
    for index in range(1, len(lines)):
        if lines[index].strip() == _FRONTMATTER_DELIMITER:
            return "\n".join(lines[: index + 1])
    return ""


def _llms_index(options: dict[str, object], pages: list[Source], base_url: str) -> str:
    title = str(options.get("title") or "Site")
    summary = str(options.get("tagline") or options.get("description") or "")

    lines = [f"# {title}", ""]
    if summary:
        lines.extend([f"> {summary}", ""])
    lines.append("## Pages")
    lines.append("")
    for source in sorted(pages, key=lambda s: str(s.meta[URL])):
        md_url = markdown_url(str(source.meta[URL]))
        link = absolute_url(base_url, md_url) if base_url else md_url
        page_title = str(source.frontmatter.get("title") or md_url)
        description = source.frontmatter.get("description") or source.frontmatter.get(
            "summary"
        )
        entry = f"- [{page_title}]({link})"
        if isinstance(description, str) and description.strip():
            entry += f": {description.strip()}"
        lines.append(entry)
    return "\n".join(lines) + "\n"
