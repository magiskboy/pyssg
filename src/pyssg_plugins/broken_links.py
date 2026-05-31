"""Broken-link plugin: report internal ``.md`` links that don't resolve.

The LinkResolver records every internal link whose target is absent from the
page registry into ``build.meta["broken_links"]``. This plugin reads that list
after the transform pass and reports it; it parses nothing of its own, reusing
the single resolution pass LinkResolver already ran.

Severity is configurable: a warning per broken link by default, or a failed
build (``BuildError``) when ``strict`` is set. It taps ``optimize`` -- after
every source's ``transform`` recorded its misses, but before ``emit`` writes
files -- so a strict build fails without producing output that contains dead
links.

The plugin uses the standard library only and requires LinkResolver to run.
"""

from __future__ import annotations

from pyssg.build import Build
from pyssg.builder import Builder
from pyssg.errors import BuildError, warn
from pyssg_plugins.link_resolver import BROKEN_LINKS, BrokenLink


class BrokenLinks:
    def __init__(self, *, strict: bool = False) -> None:
        self._strict = strict

    def apply(self, builder: Builder) -> None:
        builder.hooks.optimize.tap("BrokenLinks", self._report)

    def _report(self, build: Build) -> None:
        recorded = build.meta.get(BROKEN_LINKS)
        if not isinstance(recorded, list) or not recorded:
            return

        unique = _dedupe(recorded)
        if self._strict:
            detail = "\n".join(f"  {link.source} -> {link.href}" for link in unique)
            raise BuildError(f"{len(unique)} broken internal link(s):\n{detail}")
        for link in unique:
            warn(f"broken internal link in {link.source}: {link.href}")


def _dedupe(links: list[BrokenLink]) -> list[BrokenLink]:
    """Drop duplicate ``(source, href)`` pairs while preserving first-seen order."""

    seen: set[tuple[str, str]] = set()
    unique: list[BrokenLink] = []
    for link in links:
        key = (link.source, link.href)
        if key not in seen:
            seen.add(key)
            unique.append(link)
    return unique
