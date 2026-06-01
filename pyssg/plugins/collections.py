"""Collections plugin: declarative, paginated lists of documents.

A *collection* is a named, ordered selection of document pages (e.g. blog posts):
a pure ``select`` predicate picks members, an optional ``sort_key`` orders them,
and an optional :class:`Pagination` materializes index pages (page 1 at the
route, page N at ``<route>page/N/``). The selected member list is also stashed on
``build.site_data[<name>]`` so other templates (a "recent posts" sidebar) can
read it.

Like the taxonomy plugin, collections are recomputed deterministically from the
final graph during ``evaluate_collections``; index pages are stable-id virtual
pages, so the engine's page-set diff cleans pages that vanish and the render
cache re-emits a page only when its slice actually changes. This is what keeps an
incremental rebuild byte-identical to a full build.
"""

from __future__ import annotations

import datetime
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from pyssg.core.node import Document, Page
from pyssg.core.types import NodeKind

if TYPE_CHECKING:
    from pyssg.core.build import Build
    from pyssg.core.builder import Builder


@dataclass(frozen=True, slots=True)
class CollectionItem:
    """One candidate member: the facts a ``select``/``sort_key`` may inspect."""

    url: str
    title: str
    date: str  # ISO string, or "" when the document has no date
    excerpt: str
    tags: tuple[str, ...]
    section: str  # first URL segment, e.g. "posts" for /posts/intro/


@dataclass(frozen=True, slots=True)
class Pagination:
    """How to split a collection into index pages.

    ``route`` is page 1's URL (e.g. ``"/"`` or ``"/blog/"``); page N>1 lives at
    ``<route>page/N/``. ``template`` is the layout template used to render each
    index page (it receives ``page.items`` and ``page.pagination``).
    """

    size: int
    route: str = "/"
    template: str = "list.html.j2"


@dataclass(frozen=True, slots=True)
class CollectionSpec:
    """Declarative definition of one collection."""

    name: str
    select: Callable[[CollectionItem], bool]
    sort_key: Callable[[CollectionItem], str] | None = None
    reverse: bool = False
    pagination: Pagination | None = None
    title: str = ""


def _as_str_list(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(v) for v in value]
    return []


def _date_str(value: object) -> str:
    # PyYAML parses an unquoted ``date:`` into a date/datetime; normalize both
    # (and an explicit string) to a stable ISO string for sorting and display.
    if isinstance(value, datetime.date):
        return value.isoformat()
    if isinstance(value, str):
        return value
    return ""


def _all_items(build: Build) -> list[CollectionItem]:
    """One :class:`CollectionItem` per document-backed page in the graph."""
    items: list[CollectionItem] = []
    for node in build.graph.nodes():
        if not (isinstance(node, Page) and node.generated_from):
            continue
        doc = build.graph.get(node.generated_from[0])
        if not isinstance(doc, Document) or doc.kind is not NodeKind.MARKDOWN:
            continue
        meta = doc.meta
        segments = [s for s in node.url.split("/") if s]
        items.append(
            CollectionItem(
                url=node.url,
                title=str(meta.get("title") or doc.id),
                date=_date_str(meta.get("date")),
                excerpt=str(meta.get("excerpt") or ""),
                tags=tuple(_as_str_list(meta.get("tags"))),
                section=segments[0] if segments else "",
            )
        )
    return items


def _to_dict(item: CollectionItem) -> dict[str, object]:
    return {
        "url": item.url,
        "title": item.title,
        "date": item.date,
        "excerpt": item.excerpt,
        "tags": list(item.tags),
    }


def _set_page(build: Build, pid: str, url: str, template: str, meta: dict[str, object]) -> None:
    existing = build.graph.get(pid)
    if isinstance(existing, Page):
        existing.url = url
        existing.template = template
        existing.meta = meta
    else:
        build.graph.add_node(
            Page(id=pid, kind=NodeKind.PAGE, url=url, template=template, meta=meta)
        )


def _paginate(build: Build, spec: CollectionSpec, members: list[dict[str, object]]) -> set[str]:
    """Materialize one index page per page of ``members``; return owned ids."""
    pag = spec.pagination
    assert pag is not None  # callers guard this
    size = max(1, pag.size)
    total = max(1, (len(members) + size - 1) // size)
    owned: set[str] = set()
    for n in range(1, total + 1):
        chunk = members[(n - 1) * size : n * size]
        url = pag.route if n == 1 else f"{pag.route}page/{n}/"
        if n == 1:
            prev_url: str | None = None
        elif n == 2:
            prev_url = pag.route
        else:
            prev_url = f"{pag.route}page/{n - 1}/"
        next_url = f"{pag.route}page/{n + 1}/" if n < total else None
        pid = f"page:collection:{spec.name}:{n}"
        _set_page(
            build,
            pid,
            url,
            pag.template,
            {
                "title": spec.title or spec.name.title(),
                "kind": "collection",
                "collection": spec.name,
                "items": chunk,
                "pagination": {
                    "current": n,
                    "total": total,
                    "prev": prev_url,
                    "next": next_url,
                },
            },
        )
        owned.add(pid)
    return owned


def build_collections(build: Build, specs: tuple[CollectionSpec, ...]) -> None:
    """Evaluate every spec, publish member lists, materialize index pages."""
    items = _all_items(build)
    owned: set[str] = set()
    for spec in specs:
        members = [it for it in items if spec.select(it)]
        key = spec.sort_key if spec.sort_key is not None else _default_sort_key
        members.sort(key=key, reverse=spec.reverse)
        member_dicts = [_to_dict(it) for it in members]
        build.site_data[spec.name] = member_dicts
        if spec.pagination is not None:
            owned |= _paginate(build, spec, member_dicts)
    # Drop index pages from a previous evaluation that are no longer wanted, so
    # the finalize page-set diff deletes their stale output.
    for node in list(build.graph.nodes()):
        if node.id.startswith("page:collection:") and node.id not in owned:
            build.graph.remove(node.id)


def _default_sort_key(item: CollectionItem) -> str:
    return item.date


@dataclass(slots=True)
class CollectionsPlugin:
    """Materializes the configured collections each build."""

    specs: tuple[CollectionSpec, ...] = ()
    name: str = "collections"
    cache_version: str = "1.0.0"

    def apply(self, builder: Builder) -> None:
        @builder.hooks.this_compilation.tap(self.name)
        def _wire(build: Build) -> None:
            @build.hooks.evaluate_collections.tap(self.name, after=("nav",))
            def _eval(b: Build) -> None:
                build_collections(b, self.specs)


def collections(*specs: CollectionSpec) -> CollectionsPlugin:
    """Factory used in ``pyssg.config.py``."""
    return CollectionsPlugin(specs=tuple(specs))
