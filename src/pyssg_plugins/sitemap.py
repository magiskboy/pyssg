"""Sitemap plugin: generate a ``sitemap.xml`` for the built site.

Taps ``generate`` (after every page, including synthetic listing pages, has been
rendered) and appends one ``Output``. Standard library only.

Each public page (one with a URL, not a draft) becomes a ``<url>`` entry. The
absolute location uses ``site["base_url"]``; if it is unset, root-relative URLs
are emitted. A page's frontmatter ``date`` becomes ``<lastmod>``.
"""

from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape

from pyssg.build import Build
from pyssg.builder import Builder
from pyssg.content import URL, absolute_url, public_pages, site
from pyssg.models import Output

# Sitemap reads what render produced; run after generators that add pages.
_GENERATE_STAGE = 100


class Sitemap:
    def __init__(self, *, path: str = "sitemap.xml") -> None:
        self._path = path

    def apply(self, builder: Builder) -> None:
        builder.hooks.generate.tap("Sitemap", self._generate, stage=_GENERATE_STAGE)

    def _generate(self, build: Build) -> None:
        base_url = str(site(build).get("base_url", ""))

        entries: list[str] = []
        for source in public_pages(build):
            loc = absolute_url(base_url, str(source.meta[URL]))
            parts = [f"    <loc>{escape(loc)}</loc>"]
            lastmod = source.frontmatter.get("date")
            if isinstance(lastmod, str) and lastmod:
                parts.append(f"    <lastmod>{escape(_date_only(lastmod))}</lastmod>")
            entries.append("  <url>\n" + "\n".join(parts) + "\n  </url>")

        document = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            + "\n".join(entries)
            + "\n</urlset>\n"
        )
        build.outputs.append(Output(path=Path(self._path), content=document))


def _date_only(value: str) -> str:
    return value.split("T", 1)[0]
