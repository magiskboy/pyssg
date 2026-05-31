"""Listing plugin: turn a collection into one or more list pages.

This single plugin covers both "aggregate pages" (a tag page, a section index)
and "pagination" -- pagination is just an option. A tag page is a listing with
no page size; a blog index is a listing with a page size.

Two modes:

- ``collection="blog"`` -- a single listing for one named collection.
- ``kind="tag"``        -- one listing per collection of that kind (e.g. a page
  for every tag). ``base_url``/``title`` may contain a ``:name`` placeholder.

Listing runs in the ``collect`` pass (after Collections, before Navigation) and
appends synthetic ``Source`` objects flagged ``generated``. They flow through
the normal transform/render passes, so the chosen ``layout`` renders them like
any other page. The template receives ``page.entries`` (a list of page refs
with ``url``/``title``/...) and, when paginated, ``page.paginator``.

The list key is ``entries`` rather than ``items`` on purpose: in a template
``page`` is a dict, so ``page.items`` would resolve to the ``dict.items``
method instead of the listing data.
"""

from __future__ import annotations

from pathlib import Path

from pyssg.build import Build
from pyssg.builder import Builder
from pyssg.content import (
    GENERATED,
    OUTPUT_PATH,
    URL,
    Collection,
    collections,
    page_ref,
    url_to_output_path,
)
from pyssg.models import Source
from pyssg_plugins.collections import sort_pages
from pyssg_plugins.permalink import slugify

# Listing runs after Collections (-100) and before Navigation (100).
_COLLECT_STAGE = 0


class Listing:
    def __init__(
        self,
        *,
        collection: str | None = None,
        kind: str | None = None,
        base_url: str,
        layout: str = "list.html",
        title: str | None = None,
        page_size: int | None = None,
        sort: str | None = None,
    ) -> None:
        if (collection is None) == (kind is None):
            raise ValueError("Listing needs exactly one of 'collection' or 'kind'")
        self._collection = collection
        self._kind = kind
        self._base_url = base_url
        self._layout = layout
        self._title = title
        self._page_size = page_size
        self._sort = sort

    def apply(self, builder: Builder) -> None:
        builder.hooks.collect.tap("Listing", self._collect, stage=_COLLECT_STAGE)

    def _collect(self, build: Build) -> None:
        registry = collections(build)
        for collection in self._targets(registry):
            self._build_listing(build, collection)

    def _targets(self, registry: dict[str, Collection]) -> list[Collection]:
        if self._collection is not None:
            found = registry.get(self._collection)
            return [found] if found is not None else []
        return [c for c in registry.values() if c.kind == self._kind]

    def _build_listing(self, build: Build, collection: Collection) -> None:
        pages = collection.pages
        if self._sort is not None:
            pages = sort_pages(pages, self._sort)

        # The URL slugifies the collection name; the title keeps it verbatim.
        base = self._base_url.replace(":name", slugify(collection.name))
        if self._title is not None:
            title = self._title.replace(":name", collection.name)
        else:
            title = collection.name

        if self._page_size is None or self._page_size <= 0:
            self._make_page(build, base, title, pages, collection)
            return

        chunks = _chunk(pages, self._page_size)
        total = len(chunks)
        for index, chunk in enumerate(chunks, start=1):
            url = base if index == 1 else f"{base}page/{index}/"
            paginator: dict[str, object] = {
                "number": index,
                "total_pages": total,
                "prev_url": _page_url(base, index - 1) if index > 1 else None,
                "next_url": _page_url(base, index + 1) if index < total else None,
            }
            self._make_page(build, url, title, chunk, collection, paginator)

    def _make_page(
        self,
        build: Build,
        url: str,
        title: str,
        items: list[Source],
        collection: Collection,
        paginator: dict[str, object] | None = None,
    ) -> None:
        output_path = url_to_output_path(url)
        source = Source(path=Path(output_path), relpath=Path(output_path))
        source.frontmatter = {"title": title, "layout": self._layout}
        source.meta[GENERATED] = True
        source.meta[URL] = url
        source.meta[OUTPUT_PATH] = output_path
        # Key is "entries" (not "items") because `page` is a dict in templates
        # and `page.items` would resolve to the dict method, not this list.
        source.meta["entries"] = [page_ref(page) for page in items]
        source.meta["collection"] = collection.name
        if paginator is not None:
            source.meta["paginator"] = paginator
        build.sources.append(source)


def _page_url(base: str, number: int) -> str:
    return base if number == 1 else f"{base}page/{number}/"


def _chunk(pages: list[Source], size: int) -> list[list[Source]]:
    if not pages:
        return [[]]
    return [pages[i : i + size] for i in range(0, len(pages), size)]
