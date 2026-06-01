"""Taxonomy plugin: tags + categories, zero-config.

A taxonomy is a named classification dimension; ``tag`` and ``category`` are two
built-in instances of one mechanism, so adding another dimension is
configuration, not engine code. During ``evaluate_collections`` it reads the
relevant frontmatter keys from every document, builds each term's member list,
and materializes virtual pages: a term page per term (``/tags/<term>/``,
``/categories/<a>/<b>/``) and an index page per taxonomy (``/tags/``). Categories
are hierarchical: ``category: a/b`` makes the document a member of both ``a`` and
``a/b``.

Incremental: term pages are recomputed deterministically each
finalize, so adding/removing a term adds/removes the right page (the engine's
page-set diff cleans vanished outputs) and a term page re-emits only when its
membership actually changes (render cache + emit cutoff).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from pyssg.core.node import Document, Page
from pyssg.core.types import NodeKind
from pyssg.plugins._context import page_url_of
from pyssg.plugins.content_meta import slugify

if TYPE_CHECKING:
    from pyssg.core.build import Build
    from pyssg.core.builder import Builder

type Link = dict[str, str]


@dataclass(frozen=True, slots=True)
class Taxonomy:
    """One classification dimension."""

    name: str  # "tag"
    plural: str  # "tags"
    route: str  # "/tags/"
    frontmatter_keys: tuple[str, ...]
    hierarchical: bool = False


def tag() -> Taxonomy:
    return Taxonomy("tag", "tags", "/tags/", ("tags",))


def category() -> Taxonomy:
    return Taxonomy("category", "categories", "/categories/", ("category", "categories"), True)


def _term_slug(term: str, taxo: Taxonomy) -> str:
    if taxo.hierarchical:
        return "/".join(slugify(seg) for seg in term.split("/") if seg)
    return slugify(term)


def _expand(term: str, taxo: Taxonomy) -> list[str]:
    """A hierarchical term yields itself and its ancestors: a/b -> [a, a/b]."""
    if not taxo.hierarchical:
        return [term]
    parts = [p for p in term.split("/") if p]
    return ["/".join(parts[: i + 1]) for i in range(len(parts))]


def _doc_terms(meta: dict[str, object], taxo: Taxonomy) -> set[str]:
    raw: set[str] = set()
    for key in taxo.frontmatter_keys:
        value = meta.get(key)
        if isinstance(value, str):
            raw.add(value)
        elif isinstance(value, list):
            raw.update(str(v) for v in value)
    terms: set[str] = set()
    for term in raw:
        terms.update(_expand(term, taxo))
    return terms


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


def _build_one(build: Build, taxo: Taxonomy) -> set[str]:
    """Materialize one taxonomy; return the page ids it owns this build."""
    terms: dict[str, list[Link]] = {}
    for node in build.graph.nodes():
        if not (isinstance(node, Document) and node.kind is NodeKind.MARKDOWN):
            continue
        url = page_url_of(build, node.id)
        if url is None:
            continue
        title = str(node.meta.get("title") or node.id)
        for term in _doc_terms(node.meta, taxo):
            terms.setdefault(term, []).append({"title": title, "url": url})
    for members in terms.values():
        members.sort(key=lambda m: m["url"])

    all_terms = sorted(
        (
            {
                "term": term,
                "count": len(members),
                "url": f"{taxo.route}{_term_slug(term, taxo)}/",
            }
            for term, members in terms.items()
        ),
        key=lambda t: str(t["term"]),
    )
    build.site_data[f"all_{taxo.plural}"] = all_terms

    index_id = f"page:taxindex:{taxo.name}"
    owned = {index_id}
    for term, members in terms.items():
        pid = f"page:term:{taxo.name}:{_term_slug(term, taxo)}"
        owned.add(pid)
        _set_page(
            build,
            pid,
            f"{taxo.route}{_term_slug(term, taxo)}/",
            "term.html.j2",
            {
                "title": f"{taxo.name.title()}: {term}",
                "term": term,
                "taxonomy": taxo.name,
                "count": len(members),
                "members": members,
                "kind": "term",
            },
        )
    _set_page(
        build,
        index_id,
        taxo.route,
        "terms.html.j2",
        {"title": taxo.plural.title(), "terms": all_terms, "kind": "term-index"},
    )
    return owned


def build_taxonomies(build: Build, taxonomies: list[Taxonomy]) -> None:
    desired: set[str] = set()
    for taxo in taxonomies:
        desired |= _build_one(build, taxo)
    for node in list(build.graph.nodes()):
        if (
            node.id.startswith("page:term:") or node.id.startswith("page:taxindex:")
        ) and node.id not in desired:
            build.graph.remove(node.id)


@dataclass(slots=True)
class TaxonomyPlugin:
    """Built-in taxonomies; defaults to tag + category."""

    name: str = "taxonomy"
    cache_version: str = "1.1.0"
    taxonomies: list[Taxonomy] = field(default_factory=lambda: [tag(), category()])

    def apply(self, builder: Builder) -> None:
        @builder.hooks.this_compilation.tap(self.name)
        def _wire(build: Build) -> None:
            @build.hooks.evaluate_collections.tap(self.name, after=("nav",))
            def _eval(b: Build) -> None:
                build_taxonomies(b, self.taxonomies)


def taxonomy(*taxonomies: Taxonomy) -> TaxonomyPlugin:
    """Factory. No args -> tag + category zero-config."""
    if taxonomies:
        return TaxonomyPlugin(taxonomies=list(taxonomies))
    return TaxonomyPlugin()
