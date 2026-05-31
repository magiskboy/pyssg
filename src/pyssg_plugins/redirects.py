"""Redirects plugin: keep old URLs alive after a page moves.

Taps ``generate`` and appends one ``Output`` per redirect (plus an optional
``_redirects`` manifest). Standard library only.

Redirects come from two sources, frontmatter taking priority over config:

1. a page's frontmatter ``aliases`` (its former URLs) -- the common case when a
   slug or section changes;
2. explicit ``rules`` in ``pyssg.config.py`` -- for targets that are not a built
   page (an external URL, a deleted page).

Two emit mechanisms cover every static host:

- **HTML meta-refresh pages** (default, ``emit_html``): one tiny HTML file per
  old URL with ``<meta http-equiv="refresh">``, a canonical link and a script
  fallback. Portable to any host, including GitHub Pages.
- **a ``_redirects`` manifest** (``emit_redirects_file``): the line-based format
  Netlify and Cloudflare Pages read for true server-side 3xx responses.

A redirect whose path collides with a real built page is dropped with a warning
so the page always wins.
"""

from __future__ import annotations

import html
import json
from collections.abc import Mapping
from pathlib import Path

from pyssg.build import Build
from pyssg.builder import Builder
from pyssg.content import (
    OUTPUT_PATH,
    URL,
    absolute_url,
    is_draft,
    site,
    url_to_output_path,
)
from pyssg.errors import warn
from pyssg.models import Output

# Redirects only emit files; run alongside the other generators.
_GENERATE_STAGE = 100


class Redirects:
    def __init__(
        self,
        *,
        rules: Mapping[str, str] | None = None,
        aliases: bool = True,
        alias_key: str = "aliases",
        emit_html: bool = True,
        emit_redirects_file: bool = False,
        redirects_path: str = "_redirects",
        status: int = 301,
    ) -> None:
        self._rules = dict(rules or {})
        self._aliases = aliases
        self._alias_key = alias_key
        self._emit_html = emit_html
        self._emit_redirects_file = emit_redirects_file
        self._redirects_path = redirects_path
        self._status = status

    def apply(self, builder: Builder) -> None:
        builder.hooks.generate.tap("Redirects", self._generate, stage=_GENERATE_STAGE)

    def _generate(self, build: Build) -> None:
        redirects = self._collect(build)
        if not redirects:
            return

        base_url = str(site(build).get("base_url", ""))
        if self._emit_html:
            for from_url, target in redirects.items():
                build.outputs.append(
                    Output(
                        path=Path(url_to_output_path(from_url)),
                        content=_html_page(target, _canonical(base_url, target)),
                    )
                )
        if self._emit_redirects_file:
            build.outputs.append(
                Output(
                    path=Path(self._redirects_path),
                    content=_redirects_file(redirects, self._status),
                )
            )

    def _collect(self, build: Build) -> dict[str, str]:
        """Map each old URL to its target, frontmatter aliases winning ties."""

        taken = _page_paths(build)
        redirects: dict[str, str] = {}

        def add(raw_from: str, target: str) -> None:
            from_url = _normalize(raw_from)
            if not from_url or not target:
                return
            if url_to_output_path(from_url) in taken:
                warn(f"redirect {from_url!r} shadows a built page; skipping")
                return
            redirects.setdefault(from_url, target)

        if self._aliases:
            for source in build.sources:
                url = source.meta.get(URL)
                if not url or is_draft(source):
                    continue
                for alias in _alias_list(source.frontmatter.get(self._alias_key)):
                    add(alias, str(url))
        # Explicit rules fill only the gaps frontmatter left (setdefault).
        for raw_from, target in self._rules.items():
            add(raw_from, target)

        return redirects


def _page_paths(build: Build) -> set[str]:
    """Output paths claimed by real built pages."""

    paths: set[str] = set()
    for source in build.sources:
        output_path = source.meta.get(OUTPUT_PATH)
        if isinstance(output_path, str) and output_path:
            paths.add(output_path)
        elif source.meta.get(URL):
            paths.add(url_to_output_path(str(source.meta[URL])))
    return paths


def _normalize(value: str) -> str:
    """Coerce an alias into a root-relative URL (leading slash, no scheme)."""

    value = value.strip()
    if not value:
        return ""
    return value if value.startswith("/") else "/" + value


def _alias_list(value: object) -> list[str]:
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value if str(item)]
    return []


def _canonical(base_url: str, target: str) -> str:
    """Absolute target for the canonical link; external URLs pass through."""

    if target.startswith(("http://", "https://")):
        return target
    return absolute_url(base_url, target)


def _html_page(target: str, canonical: str) -> str:
    attr = html.escape(target, quote=True)
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        f'<meta http-equiv="refresh" content="0; url={attr}">\n'
        f'<link rel="canonical" href="{html.escape(canonical, quote=True)}">\n'
        '<meta name="robots" content="noindex">\n'
        "<title>Redirecting</title>\n"
        "</head>\n"
        "<body>\n"
        f'<p>This page has moved to <a href="{attr}">{html.escape(target)}</a>.</p>\n'
        f"<script>location.replace({json.dumps(target)})</script>\n"
        "</body>\n"
        "</html>\n"
    )


def _redirects_file(redirects: Mapping[str, str], status: int) -> str:
    lines = [f"{from_url} {target} {status}" for from_url, target in redirects.items()]
    return "\n".join(lines) + "\n"
