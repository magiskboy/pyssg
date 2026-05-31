"""Link resolver plugin: rewrite relative ``.md`` links to their final URLs.

Taps ``transform`` at a stage after Markdown (stage 0), so it post-processes
the rendered HTML rather than the raw markdown. Working on HTML is what removes
the fragility of regex over raw markdown: a link inside a code span or fence
never became an ``<a>`` tag, and angle-bracket links and percent/entity-escaped
names are already normalized into plain ``href`` attributes.

For every ``<a href="...">`` whose target is an internal content link -- a
relative (or root-relative) path ending in ``.md``/``.markdown``, optionally with
a ``?query`` and/or ``#anchor`` -- the href is rewritten to the target page's
final URL. The target is resolved against a registry built from ``build.sources``
keyed by source relpath; ``..`` segments are normalized and percent-encoded names
are decoded before lookup. The ``?query`` and ``#anchor`` are preserved.

External, scheme/protocol-relative and anchor-only links are left untouched. An
internal ``.md`` link whose target is absent from the registry is also left
untouched, but is recorded in ``build.meta["broken_links"]`` so the BrokenLinks
plugin can report it (see issue #22). This step is the foundation for wikilinks,
broken-link detection and backlinks.

The plugin uses the standard library only.
"""

from __future__ import annotations

import posixpath
import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from urllib.parse import unquote

from pyssg.build import Build
from pyssg.builder import Builder
from pyssg.content import URL
from pyssg.models import Source

# Run after Markdown's transform (stage 0) so the anchors already exist.
_TRANSFORM_STAGE = 50

# Capture the href value of every anchor tag. Attribute values cannot contain
# the literal ``>`` that terminates the tag, so the non-greedy ``[^>]*?`` cannot
# overrun. Both quote styles are matched; python-markdown emits double quotes.
_HREF_RE = re.compile(r'(<a\s[^>]*?\bhref=)(["\'])(.*?)\2', re.IGNORECASE | re.DOTALL)

# A leading ``scheme:`` (http, https, mailto, tel, ...) marks an external link.
_SCHEME_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9+.-]*:")

_REGISTRY_KEY = "_link_registry"

# build.meta key holding the internal links the resolver could not resolve. The
# BrokenLinks plugin reads it to report or fail the build (see issue #22).
BROKEN_LINKS = "broken_links"


@dataclass(frozen=True, slots=True)
class BrokenLink:
    """An internal ``.md`` link whose target is absent from the page registry."""

    source: str  # relpath (posix) of the page containing the link
    href: str  # the original, unresolved href


class LinkResolver:
    def __init__(self, *, suffixes: Sequence[str] = (".md", ".markdown")) -> None:
        self._suffixes = tuple(suffix.lower() for suffix in suffixes)

    def apply(self, builder: Builder) -> None:
        builder.hooks.transform.tap(
            "LinkResolver", self._transform, stage=_TRANSFORM_STAGE
        )

    def _transform(self, source: Source, build: Build) -> Source:
        if not source.content:
            return source
        registry = _registry(build)
        broken = _broken_links(build)

        def replace(match: re.Match[str]) -> str:
            resolved = self._resolve(match.group(3), source.relpath, registry, broken)
            if resolved is None:
                return match.group(0)
            return f"{match.group(1)}{match.group(2)}{resolved}{match.group(2)}"

        source.content = _HREF_RE.sub(replace, source.content)
        return source

    def _resolve(
        self,
        href: str,
        relpath: Path,
        registry: dict[str, str],
        broken: list[BrokenLink],
    ) -> str | None:
        parsed = self._parse_internal(href, relpath)
        if parsed is None:
            # Not an internal ``.md`` link (external, anchor-only, ...): skip it.
            return None

        key, query_sep, query, hash_sep, fragment = parsed
        url = registry.get(key) if key is not None else None
        if url is None:
            # Internal link to a page the registry doesn't know: record and leave
            # the href untouched for the BrokenLinks plugin to report.
            broken.append(BrokenLink(relpath.as_posix(), href))
            return None

        suffix = ("?" + query if query_sep else "") + (
            "#" + fragment if hash_sep else ""
        )
        return url + suffix

    def _parse_internal(
        self, href: str, relpath: Path
    ) -> tuple[str | None, str, str, str, str] | None:
        """Parse an internal ``.md`` link into ``(key, qsep, query, hsep, frag)``.

        Returns ``None`` when ``href`` is not an internal content link at all. For
        an internal link the ``key`` is the resolved registry key, or ``None`` when
        the target escapes the content root (treated as broken by the caller).
        """

        if not href or href.startswith("#") or href.startswith("//"):
            return None
        if _SCHEME_RE.match(href):
            return None

        target, hash_sep, fragment = href.partition("#")
        path_part, query_sep, query = target.partition("?")
        if not path_part:
            return None

        decoded = unquote(path_part)
        if PurePosixPath(decoded).suffix.lower() not in self._suffixes:
            return None

        return _normalize(decoded, relpath), query_sep, query, hash_sep, fragment


def _registry(build: Build) -> dict[str, str]:
    """Build (once per run) the ``relpath -> url`` index, cached on ``build.meta``."""

    cached = build.meta.get(_REGISTRY_KEY)
    if isinstance(cached, dict):
        return cached
    registry = {
        source.relpath.as_posix(): url
        for source in build.sources
        if isinstance((url := source.meta.get(URL)), str)
    }
    build.meta[_REGISTRY_KEY] = registry
    return registry


def _broken_links(build: Build) -> list[BrokenLink]:
    """Return the accumulator for unresolved internal links, creating it once."""

    existing = build.meta.get(BROKEN_LINKS)
    if isinstance(existing, list):
        return existing
    fresh: list[BrokenLink] = []
    build.meta[BROKEN_LINKS] = fresh
    return fresh


def _normalize(path: str, relpath: Path) -> str | None:
    """Resolve an internal link target to a registry key (a source relpath).

    Root-relative paths (``/foo/Bar.md``) are taken from the content root; every
    other path is resolved relative to the linking source's directory. Returns
    ``None`` when the target escapes the content root.
    """

    if path.startswith("/"):
        combined = path.lstrip("/")
    else:
        combined = posixpath.join(relpath.parent.as_posix(), path)
    normalized = posixpath.normpath(combined)
    if normalized == "." or normalized == ".." or normalized.startswith("../"):
        return None
    return normalized
