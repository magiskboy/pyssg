"""Collections plugin: group pages into ordered collections.

Taps ``collect`` early so later plugins (Listing, Navigation) can read the
result from ``build.meta["collections"]``.

Hybrid behaviour:

- ``by_tag``   -- one collection per frontmatter tag (kind ``tag``).
- ``by_folder``-- one collection per containing folder (kind ``folder``).
- ``custom``   -- declarative collections: ``name -> predicate`` (kind
  ``custom``), e.g. ``{"featured": lambda s: s.frontmatter.get("featured")}``.

Each collection is sorted by a strategy (default ``auto``: by date desc when
the pages carry dates, otherwise by ``order`` then title). Draft and generated
pages are excluded by default.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path

from pyssg.build import Build
from pyssg.builder import Builder
from pyssg.content import (
    KIND_CUSTOM,
    KIND_FOLDER,
    KIND_TAG,
    Collection,
    collections,
    is_draft,
    is_generated,
)
from pyssg.models import Source
from pyssg.schema import FieldSpec

Predicate = Callable[[Source], bool]

# Collections runs before Listing and Navigation within the collect pass.
_COLLECT_STAGE = -100


class Collections:
    def __init__(
        self,
        *,
        by_tag: bool = True,
        by_folder: bool = False,
        custom: dict[str, Predicate] | None = None,
        sort: str = "auto",
        include_drafts: bool = False,
        tags_field: str = "tags",
    ) -> None:
        self._by_tag = by_tag
        self._by_folder = by_folder
        self._custom = custom or {}
        self._sort = sort
        self._include_drafts = include_drafts
        self._tags_field = tags_field

    def apply(self, builder: Builder) -> None:
        builder.schema.declare(FieldSpec("date", type="date", example="2026-01-31"))
        builder.schema.declare(FieldSpec("order", type="int", example="10"))
        builder.schema.declare(FieldSpec("draft", type="bool", example="true"))
        if self._by_tag:
            builder.schema.declare(
                FieldSpec(self._tags_field, type="list", example="[python, web]")
            )
        builder.hooks.collect.tap("Collections", self._collect, stage=_COLLECT_STAGE)

    def _collect(self, build: Build) -> None:
        registry = collections(build)
        pages = [
            source
            for source in build.sources
            if not is_generated(source)
            and (self._include_drafts or not is_draft(source))
        ]

        if self._by_folder:
            self._add_folders(registry, pages)
        if self._by_tag:
            self._add_tags(registry, pages)
        for name, predicate in self._custom.items():
            collection = registry.setdefault(
                name, Collection(name=name, kind=KIND_CUSTOM)
            )
            collection.pages.extend(p for p in pages if predicate(p))

        for collection in registry.values():
            collection.pages = sort_pages(collection.pages, self._sort)

    def _add_folders(
        self, registry: dict[str, Collection], pages: list[Source]
    ) -> None:
        for page in pages:
            folder = page.relpath.parent
            if folder == Path("."):
                continue
            name = folder.as_posix()
            collection = registry.setdefault(
                name, Collection(name=name, kind=KIND_FOLDER)
            )
            collection.pages.append(page)

    def _add_tags(self, registry: dict[str, Collection], pages: list[Source]) -> None:
        for page in pages:
            for tag in _tags(page, self._tags_field):
                collection = registry.setdefault(
                    tag, Collection(name=tag, kind=KIND_TAG)
                )
                collection.pages.append(page)


def _tags(source: Source, field: str) -> list[str]:
    value = source.frontmatter.get(field)
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, str):
        return [value]
    return []


def sort_pages(pages: Sequence[Source], strategy: str) -> list[Source]:
    if strategy == "auto":
        strategy = "date" if any(_date(p) for p in pages) else "order"

    if strategy == "date":
        return sorted(pages, key=_date, reverse=True)
    if strategy == "order":
        return sorted(pages, key=lambda p: (_order(p), _title(p)))
    if strategy == "title":
        return sorted(pages, key=_title)
    return list(pages)


def _date(source: Source) -> str:
    value = source.frontmatter.get("date")
    return value if isinstance(value, str) else ""


def _order(source: Source) -> int:
    value = source.frontmatter.get("order")
    return value if isinstance(value, int) else 0


def _title(source: Source) -> str:
    value = source.frontmatter.get("title")
    return str(value) if value is not None else source.relpath.stem
