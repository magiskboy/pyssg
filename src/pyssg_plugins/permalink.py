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

When the I18n plugin marks a source as the default locale (``meta``
``locale_prefix`` is ``""``), the derived URL has its locale segment stripped
so the default locale renders at the site root (``/vi/posts/x/`` -> ``/posts/x/``).
This applies only to the path-derived URL; an explicit ``permalink`` or
``pattern`` is the author's responsibility and is left untouched.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path

from slugify import slugify as _slugify

from pyssg.build import Build
from pyssg.builder import Builder
from pyssg.content import (
    LOCALE,
    LOCALE_PREFIX,
    OUTPUT_PATH,
    URL,
    is_generated,
    url_to_output_path,
)
from pyssg.models import Source

# Permalink runs before Collections (-100), Listing (0) and Navigation (100).
_COLLECT_STAGE = -200

_TOKEN = re.compile(r":([a-zA-Z_][a-zA-Z0-9_]*)")


class Permalink:
    def __init__(self, pattern: str | None = None, *, pretty: bool = True) -> None:
        self._pattern = pattern
        self._pretty = pretty

    def apply(self, builder: Builder) -> None:
        builder.hooks.collect.tap("Permalink", self._collect, stage=_COLLECT_STAGE)

    def _collect(self, build: Build) -> None:
        slug_fn = resolve_slugify(build)
        for source in build.sources:
            self._assign(source, slug_fn)

    def _assign(self, source: Source, slug_fn: Callable[[str], str]) -> None:
        # A page may already have a URL assigned (e.g. a synthetic listing page);
        # do not override it.
        if URL in source.meta:
            return

        explicit = source.frontmatter.get("permalink")
        if isinstance(explicit, str):
            url = _normalize_url(_apply_pattern(explicit, source, slug_fn))
        elif self._pattern is not None and not is_generated(source):
            url = _normalize_url(_apply_pattern(self._pattern, source, slug_fn))
        else:
            url = _default_url(source.relpath, self._pretty)
            url = _strip_locale_prefix(url, source)

        source.meta[URL] = url
        source.meta[OUTPUT_PATH] = url_to_output_path(url)


def slugify(text: str) -> str:
    """Unicode-aware slug: transliterate to ASCII and join words with hyphens.

    ``"Lập trình bất đồng bộ"`` -> ``"lap-trinh-bat-dong-bo"``. Handles every
    Unicode script python-slugify can transliterate (Vietnamese, German, CJK,
    Cyrillic, ...). A site can override slug generation via ``Config.slugify``;
    see :func:`resolve_slugify`.
    """

    return _slugify(text)


def resolve_slugify(build: Build) -> Callable[[str], str]:
    """Return the slug function for this build: ``Config.slugify`` or the default."""

    override = build.config.slugify
    return override if override is not None else slugify


def _strip_locale_prefix(url: str, source: Source) -> str:
    """Drop the leading ``/<locale>/`` for a default-locale page (root rendering).

    A no-op unless I18n marked the source with ``locale_prefix == ""``; Permalink
    used standalone (no I18n) leaves the URL untouched.
    """

    if source.meta.get(LOCALE_PREFIX) != "":
        return url
    locale = source.meta.get(LOCALE)
    if not isinstance(locale, str) or not locale:
        return url
    segment = f"/{locale}/"
    if url == segment:
        return "/"
    if url.startswith(segment):
        return "/" + url[len(segment) :]
    return url


def _apply_pattern(pattern: str, source: Source, slug_fn: Callable[[str], str]) -> str:
    tokens = _tokens(source, slug_fn)

    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key in tokens:
            return tokens[key]
        value = source.frontmatter.get(key)
        return slug_fn(str(value)) if value is not None else match.group(0)

    return _TOKEN.sub(replace, pattern)


def _tokens(source: Source, slug_fn: Callable[[str], str]) -> dict[str, str]:
    stem = source.relpath.stem
    slug_value = source.frontmatter.get("slug")
    slug = str(slug_value) if isinstance(slug_value, str) else stem

    title = source.frontmatter.get("title")
    tokens = {
        "slug": slug,
        "title": slug_fn(str(title)) if title is not None else slug,
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
