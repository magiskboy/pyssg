"""Permalink plugin: decide each page's URL and output path.

Taps ``collect`` at an early stage. URLs are site-wide data: every page must
have a URL before any page renders (so listings and navigation can link to
them), and before Collections/Listing/Navigation run. It sets, per source:

- ``source.meta["url"]``         -- the public URL (pretty, ends with "/")
- ``source.meta["output_path"]`` -- the file path relative to the out dir

Resolution order (highest priority first):

1. Frontmatter ``permalink`` -- an explicit override per page.
2. A configured ``pattern`` -- e.g. ``/blog/:year/:slug/`` applied to pages.
3. Default pretty URL derived from the source path (``foo.md`` -> ``/foo/``).

Placeholders in patterns / permalinks: ``:slug``, ``:year``, ``:month``,
``:day``, ``:title`` and ``:<key>`` for any frontmatter value.
"""

from __future__ import annotations

import re
from pathlib import Path

from pyssg.build import Build
from pyssg.builder import Builder
from pyssg.content import OUTPUT_PATH, URL, is_generated, url_to_output_path
from pyssg.models import Source

# Permalink runs before Collections (-100), Listing (0) and Navigation (100).
_COLLECT_STAGE = -200

_SLUG_STRIP = re.compile(r"[^a-z0-9]+")
_TOKEN = re.compile(r":([a-zA-Z_][a-zA-Z0-9_]*)")


class Permalink:
    def __init__(self, pattern: str | None = None, *, pretty: bool = True) -> None:
        self._pattern = pattern
        self._pretty = pretty

    def apply(self, builder: Builder) -> None:
        builder.hooks.collect.tap("Permalink", self._collect, stage=_COLLECT_STAGE)

    def _collect(self, build: Build) -> None:
        for source in build.sources:
            self._assign(source)

    def _assign(self, source: Source) -> None:
        # A page may already have a URL assigned (e.g. a synthetic listing page);
        # do not override it.
        if URL in source.meta:
            return

        explicit = source.frontmatter.get("permalink")
        if isinstance(explicit, str):
            url = _normalize_url(_apply_pattern(explicit, source))
        elif self._pattern is not None and not is_generated(source):
            url = _normalize_url(_apply_pattern(self._pattern, source))
        else:
            url = _default_url(source.relpath, self._pretty)

        source.meta[URL] = url
        source.meta[OUTPUT_PATH] = url_to_output_path(url)


def slugify(text: str) -> str:
    return _SLUG_STRIP.sub("-", text.strip().lower()).strip("-")


def _apply_pattern(pattern: str, source: Source) -> str:
    tokens = _tokens(source)

    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key in tokens:
            return tokens[key]
        value = source.frontmatter.get(key)
        return slugify(str(value)) if value is not None else match.group(0)

    return _TOKEN.sub(replace, pattern)


def _tokens(source: Source) -> dict[str, str]:
    stem = source.relpath.stem
    slug_value = source.frontmatter.get("slug")
    slug = str(slug_value) if isinstance(slug_value, str) else stem

    title = source.frontmatter.get("title")
    tokens = {
        "slug": slug,
        "title": slugify(str(title)) if title is not None else slug,
    }

    year, month, day = _date_parts(source.frontmatter.get("date"))
    if year:
        tokens["year"] = year
    if month:
        tokens["month"] = month
    if day:
        tokens["day"] = day
    return tokens


def _date_parts(value: object) -> tuple[str, str, str]:
    if not isinstance(value, str):
        return "", "", ""
    parts = value.split("T", 1)[0].split("-")
    if len(parts) < 3:
        return "", "", ""
    year, month, day = parts[0], parts[1], parts[2]
    return year, month.zfill(2), day.zfill(2)


def _default_url(relpath: Path, pretty: bool) -> str:
    if relpath.stem == "index":
        folder = relpath.parent
        if folder == Path("."):
            return "/"
        return "/" + folder.as_posix() + "/"

    if pretty:
        return "/" + relpath.with_suffix("").as_posix() + "/"
    return "/" + relpath.with_suffix(".html").as_posix()


def _normalize_url(url: str) -> str:
    if not url.startswith("/"):
        url = "/" + url
    # A path without a file extension is treated as a directory (pretty URL).
    last = url.rsplit("/", 1)[-1]
    if last and "." not in last:
        url += "/"
    return url
