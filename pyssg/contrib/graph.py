"""Contrib plugin: interactive document-graph output (``graph.json`` + view).

This turns pyssg's internal link graph into a public, renderable artifact -- the
Obsidian / Quartz style "graph view" of how notes connect. It has three layers,
all owned by this one plugin so the feature drops into any theme:

- **Data** -- a deterministic ``/graph.json`` (``{nodes, links, config}``) built
  from the resolved :class:`~pyssg.core.types.ConnectionKind` ``LINK`` edges that
  ``wikilink`` / ``link_resolver`` already record. Nodes are the document-backed
  pages; links are the resolved references between them (covering both
  ``[[wikilinks]]`` and relative ``.md`` links). Optionally tags are promoted to
  first-class nodes so the graph can cluster by topic.
- **View** -- a small client renderer (``graph.js`` + ``graph.css``, emitted by
  the plugin to ``/assets/graph/``) that consumes ``graph.json``. It powers a
  full-page **global** graph at ``/graph/`` (2D force layout with an optional 3D
  mode) and -- opt-in via ``local=True`` -- a per-page **local** graph (the
  current page's neighbourhood out to a configurable depth) injected as a panel
  into each document page.
- **Config** -- a single :class:`GraphConfig` shaping what the graph shows and how
  it looks (filtering, grouping/colour, local depth, tag nodes, node sizing). The
  render-relevant subset is serialized into ``graph.json`` so the client stays a
  dumb consumer of declared facts.

Like the sitemap/rss/llms plugins this is a *summarizer fan-in*: it taps
``evaluate_collections`` (after nav/taxonomy so every virtual page already
exists), reads the finalized graph, and materializes virtual pages carrying their
payload as ``content_html`` with ``template=None`` (the render contract for "emit
verbatim, no layout"). It reads only declared inputs -- page urls, document meta,
the recorded ``LINK`` edges and its own packaged asset files -- and sorts
deterministically, so two builds are byte-identical and an incremental rebuild
matches a full one.

The client renderer is a clean-room reimplementation; its interaction design
(2D cytoscape layout plus a lazily loaded 3D force-graph) follows the prior art in
``magiskboy/wiki``. Per the contrib rules this module is pure, ships tests, passes
``mypy --strict`` and is not auto re-exported into ``pyssg.plugins``. Third-party
graph libraries are loaded at view time from a CDN (see :data:`CYTOSCAPE_URL`),
not vendored.
"""

from __future__ import annotations

import fnmatch
import json
import re
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from functools import cache
from html import escape
from pathlib import Path
from typing import TYPE_CHECKING

from pyssg.core.node import Document, Page
from pyssg.core.types import ConnectionKind, NodeKind

if TYPE_CHECKING:
    from pyssg.core.build import Build
    from pyssg.core.builder import Builder

# -- virtual page ids / urls --------------------------------------------------

_JSON_ID = "page:graph-json"
_JSON_URL = "/graph.json"
_PAGE_ID = "page:graph"
_PAGE_URL = "/graph/"
_ASSET_JS_ID = "page:graph-asset-js"
_ASSET_JS_URL = "/assets/graph/graph.js"
_ASSET_CSS_ID = "page:graph-asset-css"
_ASSET_CSS_URL = "/assets/graph/graph.css"

_ASSET_DIR = Path(__file__).resolve().parent / "_graph_assets"

#: Tag-promoted node id prefix (``tag:python``) and rendered node ``kind`` values.
_TAG_PREFIX = "tag:"

#: HTML-comment marker a theme places to control where the local-graph panel goes
#: (e.g. ``<!-- pyssg:local-graph -->`` inside a sidebar). When present the plugin
#: replaces it with the panel instead of appending to the document body.
LOCAL_PLACEHOLDER = "pyssg:local-graph"
_PLACEHOLDER_RE = re.compile(r"<!--\s*" + re.escape(LOCAL_PLACEHOLDER) + r"\s*-->")

# CDN sources for the client graph libraries. Pinned for reproducible behaviour;
# the 3D libraries are loaded lazily by ``graph.js`` only when the 3D mode is
# toggled, so 2D pages never pay for them.
CYTOSCAPE_URL = "https://unpkg.com/cytoscape@3.30.2/dist/cytoscape.min.js"


# -- configuration ------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class GraphConfig:
    """Declarative shape of the document graph (filter, group, size, depth).

    Every field is optional with a sensible default, so ``graph()`` works with
    zero configuration. The instance is immutable and read-only, so it carries no
    global mutable state and two builds stay byte-identical.

    :param include: Path globs (matched against a document's ``source_path``); when
        set, only matching documents become nodes. ``None`` keeps all.
    :param exclude: Path globs whose matching documents are dropped.
    :param include_tags: When set, keep only documents carrying at least one of
        these tags.
    :param exclude_tags: Drop documents carrying any of these tags.
    :param drop_orphans: Drop nodes whose total degree (in + out) is zero.
    :param min_degree: Drop nodes whose total degree is below this threshold.
    :param group_by: ``"folder"`` groups a node by its top-level path segment;
        ``"tag"`` groups it by its first tag. The group drives node colour.
    :param colors: Map of group name to CSS colour, serialized for the client; any
        group without an entry gets a deterministic palette colour.
    :param local: Inject the per-page local-graph panel into each document page.
        A theme can place the marker ``<!-- pyssg:local-graph -->`` (see
        :data:`LOCAL_PLACEHOLDER`) to control where it renders; otherwise it is
        appended to the body end. Off by default (opt-in), since it adds a panel
        to every page.
    :param local_depth: How many hops out from the current page the local graph
        expands (clamped to >= 1).
    :param global_page: Emit the full-page global graph at ``/graph/``.
    :param tag_nodes: Promote tags to first-class graph nodes (``tag:<name>``) with
        a page->tag edge each, so the graph can cluster by topic.
    :param size_min: Smallest rendered node diameter (px), for the lowest degree.
    :param size_max: Largest rendered node diameter (px), for the highest degree.
    """

    include: tuple[str, ...] | None = None
    exclude: tuple[str, ...] = ()
    include_tags: tuple[str, ...] | None = None
    exclude_tags: tuple[str, ...] = ()
    drop_orphans: bool = False
    min_degree: int = 0
    group_by: str = "folder"
    colors: Mapping[str, str] = field(default_factory=dict)
    local: bool = False
    local_depth: int = 1
    global_page: bool = True
    tag_nodes: bool = False
    size_min: float = 8.0
    size_max: float = 40.0

    def client_config(self) -> dict[str, object]:
        """The render-relevant subset serialized into ``graph.json``.

        The client renderer needs only colours, sizing, depth and the
        tag-node/grouping facts; the filtering knobs are applied server-side
        (so the full graph is never shipped) and are intentionally omitted.
        """
        return {
            "groupBy": self.group_by,
            "colors": dict(self.colors),
            "localDepth": max(1, self.local_depth),
            "tagNodes": self.tag_nodes,
            "sizeMin": self.size_min,
            "sizeMax": self.size_max,
        }


# -- data extraction ----------------------------------------------------------


def _tags_of(doc: Document) -> list[str]:
    """The document's frontmatter tags as a list of strings (order preserved)."""
    raw = doc.meta.get("tags")
    if isinstance(raw, (list, tuple)):
        return [str(t) for t in raw]
    return []


def _group_of(page: Page, tags: list[str], cfg: GraphConfig) -> str:
    """The node's group: first tag (``group_by="tag"``) or top-level URL segment.

    Folder grouping keys on the page's *served* URL rather than the source path,
    so it reflects the site's actual sections and is unaffected by source-only
    prefixes a router strips (e.g. an i18n locale directory). A root page has no
    segment and falls back to ``"root"``.
    """
    if cfg.group_by == "tag":
        return tags[0] if tags else "untagged"
    parts = [p for p in page.url.split("/") if p]
    return parts[0] if parts else "root"


def _selected(doc: Document, tags: list[str], cfg: GraphConfig) -> bool:
    """Whether a document passes the include/exclude path and tag filters."""
    if doc.meta.get("graph") is False:
        return False
    path = doc.source_path or ""
    if cfg.include is not None and not any(fnmatch.fnmatch(path, g) for g in cfg.include):
        return False
    if any(fnmatch.fnmatch(path, g) for g in cfg.exclude):
        return False
    tagset = set(tags)
    if cfg.include_tags is not None and tagset.isdisjoint(cfg.include_tags):
        return False
    return not tagset.intersection(cfg.exclude_tags)


def _candidate_pages(build: Build, cfg: GraphConfig) -> list[tuple[Document, Page]]:
    """Document-backed pages that pass the filters, sorted by document id.

    Only ``Page`` nodes with ``generated_from`` provenance pointing at a Markdown
    ``Document`` are considered, so the virtual sitemap/rss/llms/graph pages -- and
    suppressed/non-page documents -- are excluded by construction.
    """
    out: list[tuple[Document, Page]] = []
    for node in build.graph.nodes():
        if not (isinstance(node, Page) and node.generated_from):
            continue
        doc = build.graph.get(node.generated_from[0])
        if not isinstance(doc, Document) or doc.kind is not NodeKind.MARKDOWN:
            continue
        if not _selected(doc, _tags_of(doc), cfg):
            continue
        out.append((doc, node))
    out.sort(key=lambda dp: dp[0].id)
    return out


def build_graph_data(build: Build, cfg: GraphConfig) -> dict[str, object]:
    """Build the ``{nodes, links, config}`` graph payload from the link graph.

    Pure projection of the finalized graph: nodes are filtered document pages,
    links are the resolved ``LINK`` edges between them (deduplicated to one
    undirected edge per pair, with ``bidirectional`` set when both directions
    exist). ``inDegree`` / ``outDegree`` count the distinct directed links touching
    a node (including page->tag edges when ``tag_nodes`` is on). Node and link
    ordering is stable (by id, then by endpoints), so the serialized JSON is
    byte-identical across rebuilds.

    :returns: ``{"nodes": [...], "links": [...], "config": {...}}``.
    """
    pages = _candidate_pages(build, cfg)
    page_ids = {doc.id for doc, _ in pages}

    # Directed, deduplicated edges over the candidate set (page->page first, then
    # page->tag), used both for degree counts and for the rendered links.
    directed: set[tuple[str, str]] = set()
    for doc, _ in pages:
        for conn in build.graph.out_edges(doc.id, ConnectionKind.LINK):
            dst = conn.dst
            if dst is None or dst == doc.id or dst not in page_ids:
                continue
            directed.add((doc.id, dst))
    if cfg.tag_nodes:
        for doc, _ in pages:
            for tag in _tags_of(doc):
                directed.add((doc.id, f"{_TAG_PREFIX}{tag}"))

    indeg: dict[str, int] = defaultdict(int)
    outdeg: dict[str, int] = defaultdict(int)
    for src, dst in directed:
        outdeg[src] += 1
        indeg[dst] += 1

    # Survival filter (orphans / min-degree) applies to page nodes only; tag nodes
    # always have an incident edge by construction.
    survivors: set[str] = set()
    for doc, _ in pages:
        degree = indeg[doc.id] + outdeg[doc.id]
        if cfg.drop_orphans and degree == 0:
            continue
        if degree < cfg.min_degree:
            continue
        survivors.add(doc.id)

    tag_ids: set[str] = set()
    if cfg.tag_nodes:
        for doc, _ in pages:
            if doc.id in survivors:
                tag_ids.update(f"{_TAG_PREFIX}{t}" for t in _tags_of(doc))
    valid = survivors | tag_ids

    nodes: list[dict[str, object]] = []
    for doc, page in pages:
        if doc.id not in survivors:
            continue
        tags = _tags_of(doc)
        nodes.append(
            {
                "id": doc.id,
                "title": str(doc.meta.get("title") or page.url),
                "url": page.url,
                "tags": tags,
                "group": _group_of(page, tags, cfg),
                "kind": "page",
                "inDegree": indeg[doc.id],
                "outDegree": outdeg[doc.id],
            }
        )
    for tid in sorted(tag_ids):
        nodes.append(
            {
                "id": tid,
                "title": tid[len(_TAG_PREFIX) :],
                "url": "",
                "tags": [],
                "group": "tag",
                "kind": "tag",
                "inDegree": indeg[tid],
                "outDegree": outdeg[tid],
            }
        )
    nodes.sort(key=lambda n: str(n["id"]))

    # Collapse each connected pair to a single undirected link; mark it
    # bidirectional when both directions were recorded.
    pairs: dict[tuple[str, str], set[tuple[str, str]]] = defaultdict(set)
    for src, dst in directed:
        if src in valid and dst in valid:
            lo, hi = (src, dst) if src <= dst else (dst, src)
            pairs[(lo, hi)].add((src, dst))
    links: list[dict[str, object]] = []
    for (a, b), dirs in pairs.items():
        bidirectional = (a, b) in dirs and (b, a) in dirs
        source, target = (a, b) if (a, b) in dirs else (b, a)
        links.append({"source": source, "target": target, "bidirectional": bidirectional})
    links.sort(key=lambda link: (str(link["source"]), str(link["target"])))

    return {"nodes": nodes, "links": links, "config": cfg.client_config()}


# -- asset loading ------------------------------------------------------------


@cache
def _asset(name: str) -> str:
    """Read a packaged client asset (``graph.js`` / ``graph.css``).

    Cached because the file ships with the package and never changes within a
    process; reading it is deterministic (not site content, clock or randomness).
    """
    return (_ASSET_DIR / name).read_text(encoding="utf-8")


# -- page materialization -----------------------------------------------------


def _set_raw_page(build: Build, pid: str, url: str, title: str, text: str) -> None:
    """Create or update a virtual ``template=None`` page emitting ``text`` raw."""
    meta: dict[str, object] = {"title": title, "content_html": text}
    existing = build.graph.get(pid)
    if isinstance(existing, Page):
        existing.url = url
        existing.template = None
        existing.meta = meta
    else:
        build.graph.add_node(Page(id=pid, kind=NodeKind.PAGE, url=url, template=None, meta=meta))


def _embed(blob: str) -> str:
    """Escape a JSON blob for safe inlining inside a ``<script>`` element."""
    return blob.replace("<", "\\u003c")


def render_global_page(title: str, blob: str) -> str:
    """Render the standalone ``/graph/`` HTML page embedding the graph data.

    The page is theme-independent (``template=None``): it inlines the data as a
    ``<script id="graph-data">`` block -- which ``graph.js`` prefers over a network
    fetch -- and pulls in the renderer assets plus the cytoscape CDN bundle.
    """
    return (
        "<!doctype html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{escape(title)}</title>\n"
        f'<link rel="stylesheet" href="{_ASSET_CSS_URL}">\n'
        "</head>\n"
        '<body class="graph-page">\n'
        '<div id="kb-graph" class="graph-stage"></div>\n'
        '<div id="kb-graph-3d" class="graph-stage" hidden></div>\n'
        '<div class="graph-controls">\n'
        '<input id="graph-search" type="search" placeholder="Search nodes...">\n'
        '<button id="graph-3d-toggle" type="button" aria-pressed="false">3D</button>\n'
        '<button id="graph-reset" type="button">Reset</button>\n'
        "</div>\n"
        '<aside id="graph-panel" hidden></aside>\n'
        f'<script id="graph-data" type="application/json">{_embed(blob)}</script>\n'
        f'<script src="{CYTOSCAPE_URL}"></script>\n'
        f'<script src="{_ASSET_JS_URL}" defer></script>\n'
        "</body>\n"
        "</html>\n"
    )


def _has_link_edges(build: Build, doc_id: str) -> bool:
    """Whether a document has any incident ``LINK`` edge (cheap orphan check)."""
    return bool(
        build.graph.out_edges(doc_id, ConnectionKind.LINK)
        or build.graph.in_edges(doc_id, ConnectionKind.LINK)
    )


def _local_container(node_id: str, depth: int) -> str:
    """The local-graph panel element, carrying the current node id and depth."""
    attrs = f'data-node-id="{escape(node_id, quote=True)}" data-depth="{max(1, depth)}"'
    return f'<aside id="kb-local-graph" class="graph-local" {attrs}></aside>'


def _local_includes() -> str:
    """The stylesheet + cytoscape CDN + renderer ``<script>`` includes."""
    return (
        f'\n<link rel="stylesheet" href="{_ASSET_CSS_URL}">\n'
        f'<script src="{CYTOSCAPE_URL}"></script>\n'
        f'<script src="{_ASSET_JS_URL}" defer></script>\n'
    )


def inject_local_graph(html: str, page: Page, build: Build, cfg: GraphConfig) -> str:
    """Inject the local-graph panel into a rendered document page.

    A ``render_page`` waterfall tap (run after the main render) for a real
    document page (a concrete ``template``, Markdown provenance, not opted out via
    ``graph: false`` / ``graph_local: false``). Placement:

    - **Theme-provided placeholder** -- if the page contains the marker comment
      ``<!-- pyssg:local-graph -->`` (see :data:`LOCAL_PLACEHOLDER`), it is
      replaced in place by the panel, so the theme decides where the graph lives
      (e.g. a sidebar). This is the recommended integration.
    - **Fallback** -- with no marker, the panel is appended to the end of the body
      so the feature still works on themes that know nothing about it.

    Either way the renderer assets are loaded before ``</body>``. Virtual/raw
    pages (``template is None``) and pages with no body element are returned
    unchanged.
    """
    if page.template is None or not page.generated_from or "</body>" not in html:
        return html
    doc = build.graph.get(page.generated_from[0])
    if not isinstance(doc, Document) or doc.kind is not NodeKind.MARKDOWN:
        return html
    if doc.meta.get("graph") is False or doc.meta.get("graph_local") is False:
        return html
    # Skip pages that would not be a node anyway (filtered out, or an orphan when
    # orphans are dropped), so they do not load the renderer for an empty panel.
    if not _selected(doc, _tags_of(doc), cfg):
        return html
    if cfg.drop_orphans and not _has_link_edges(build, doc.id):
        return html

    container = _local_container(doc.id, cfg.local_depth)
    includes = _local_includes()
    placeholder = _PLACEHOLDER_RE.search(html)
    if placeholder is not None:
        html = html[: placeholder.start()] + container + html[placeholder.end() :]
        return html.replace("</body>", includes + "</body>", 1)
    return html.replace("</body>", container + includes + "</body>", 1)


def materialize_graph(build: Build, cfg: GraphConfig) -> None:
    """Emit ``/graph.json``, the renderer assets, and the optional global page.

    Idempotent: re-running upserts the same virtual pages in place, and drops a
    stale global page when ``global_page`` is turned off, so an incremental
    rebuild's page-set diff matches a full build.
    """
    data = build_graph_data(build, cfg)
    blob = json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2)
    _set_raw_page(build, _JSON_ID, _JSON_URL, "graph.json", blob + "\n")
    _set_raw_page(build, _ASSET_JS_ID, _ASSET_JS_URL, "graph.js", _asset("graph.js"))
    _set_raw_page(build, _ASSET_CSS_ID, _ASSET_CSS_URL, "graph.css", _asset("graph.css"))

    site = build.builder.config.site if build.builder.config is not None else {}
    site_title = str(site.get("title") or "").strip()
    page_title = f"{site_title} - Graph" if site_title else "Graph"
    if cfg.global_page:
        _set_raw_page(build, _PAGE_ID, _PAGE_URL, page_title, render_global_page(page_title, blob))
    elif isinstance(build.graph.get(_PAGE_ID), Page):
        build.graph.remove(_PAGE_ID)


# -- plugin -------------------------------------------------------------------


@dataclass(slots=True)
class GraphPlugin:
    """Emits the document graph data, renderer assets and graph views."""

    config: GraphConfig = field(default_factory=GraphConfig)
    name: str = "graph"
    cache_version: str = "1.0.0"

    def apply(self, builder: Builder) -> None:
        cfg = self.config

        @builder.hooks.this_compilation.tap(self.name)
        def _wire(build: Build) -> None:
            @build.hooks.evaluate_collections.tap(self.name, after=("nav", "taxonomy"))
            def _eval(b: Build) -> None:
                materialize_graph(b, cfg)

            if cfg.local:

                @build.hooks.render_page.tap(self.name, after=("render",))
                def _inject(html: str, page: Page) -> str:
                    return inject_local_graph(html, page, build, cfg)


def graph(
    *,
    include: Iterable[str] | None = None,
    exclude: Iterable[str] = (),
    include_tags: Iterable[str] | None = None,
    exclude_tags: Iterable[str] = (),
    drop_orphans: bool = False,
    min_degree: int = 0,
    group_by: str = "folder",
    colors: Mapping[str, str] | None = None,
    local: bool = False,
    local_depth: int = 1,
    global_page: bool = True,
    tag_nodes: bool = False,
    size_min: float = 8.0,
    size_max: float = 40.0,
) -> GraphPlugin:
    """Factory used in ``pyssg.config.py``; see :class:`GraphConfig` for the knobs."""
    return GraphPlugin(
        config=GraphConfig(
            include=tuple(include) if include is not None else None,
            exclude=tuple(exclude),
            include_tags=tuple(include_tags) if include_tags is not None else None,
            exclude_tags=tuple(exclude_tags),
            drop_orphans=drop_orphans,
            min_degree=min_degree,
            group_by=group_by,
            colors=dict(colors) if colors is not None else {},
            local=local,
            local_depth=local_depth,
            global_page=global_page,
            tag_nodes=tag_nodes,
            size_min=size_min,
            size_max=size_max,
        )
    )
