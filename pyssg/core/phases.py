"""Phase orchestration: full build and incremental rebuild.

The full build and the incremental rebuild share the *same* per-document and
per-page processing so that, by construction, an incremental rebuild is
byte-identical to a full rebuild (the critical invariant). The full build is
just "every node dirty-from LOAD"; the incremental path seeds a worklist from
FS events and converges to a fixpoint with early-cutoff.

Stdlib only: all third-party work happens inside the plugins tapped onto the
hooks, never here. The watcher feeds neutral ``FsEvent``-shaped objects; core
never imports the watchdog backend.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from pyssg.core.build import Build, BuildStats
from pyssg.core.incremental.hashing import compute_raw_hash, hash_aspect
from pyssg.core.incremental.invalidation import WorkList, propagate_aspect_changes
from pyssg.core.node import Document, Node, Page
from pyssg.core.types import ConnectionKind, NodeId, NodeKind, Phase

if TYPE_CHECKING:
    from collections.abc import Sequence

    from pyssg.core.builder import Builder


class FsEventLike(Protocol):
    """Structural shape of a filesystem event.

    Declared here so core stays decoupled from ``pyssg.watch`` (and thus from
    watchdog). The watch layer's ``FsEvent`` satisfies it.
    """

    @property
    def kind(self) -> str: ...

    @property
    def path(self) -> str: ...

    @property
    def dest(self) -> str | None: ...


# -- path / output helpers -----------------------------------------------------


def _roots(build: Build) -> tuple[Path, Path]:
    """Resolved (content_root, output_root) for the current site."""
    builder = build.builder
    config = builder.config
    if config is None:
        raise ValueError("Builder has no config; cannot run a build")
    content_root = (builder.site_dir / config.content_dir).resolve()
    out_root = (builder.site_dir / config.output_dir).resolve()
    return content_root, out_root


def output_path_for(out_root: Path, url: str) -> Path:
    """Map a page URL to its output file.

    A URL whose final segment has a file extension (``/sitemap.xml``) maps to
    that exact file; a pretty URL (``/guide/``) maps to ``.../index.html``.
    """
    rel = url.strip("/")
    if rel == "":
        return out_root / "index.html"
    last = rel.rsplit("/", 1)[-1]
    if "." in last:
        return out_root / rel
    return out_root / rel / "index.html"


def _node_id_for(content_root: Path, abs_path: str) -> NodeId | None:
    """Stable path-based NodeId for a markdown file, or None if not eligible."""
    path = Path(abs_path)
    if path.suffix != ".md":
        return None
    try:
        rel = path.resolve().relative_to(content_root)
    except ValueError:
        return None
    return f"path:{rel.with_suffix('').as_posix()}"


# -- shared per-document / per-page processing ---------------------------------


def _hash_document_aspects(build: Build, doc: Node) -> None:
    """Hash the doc aspects a page depends on: ``content_html`` and ``meta``."""
    hash_aspect(doc, "content_html", doc.meta.get("content_html", ""))
    public_meta = {
        key: value
        for key, value in doc.meta.items()
        if not key.startswith("__") and key != "content_html"
    }
    hash_aspect(doc, "meta", public_meta)


def _generate_doc_pages(build: Build, doc: Node) -> list[Page]:
    """Run the generate hook for one document and collect the pages it emits."""
    build.take_generated_pages()  # discard any stale accumulation
    build.hooks.generate.call(doc)
    return build.take_generated_pages()


def _emit_page(build: Build, page: Page, out_root: Path, html: str) -> None:
    path = output_path_for(out_root, page.url)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
    build.record_emit(page.id, path.relative_to(out_root).as_posix())
    build.stats.changed_outputs.add(page.url)


def _delete_output(build: Build, page_id: NodeId, out_root: Path) -> None:
    """Delete a vanished page's output file and forget its bookkeeping."""
    rel = build.emitted_output(page_id)
    if rel is not None:
        target = out_root / rel
        if target.is_file():
            target.unlink()
    build.forget_node(page_id)


def _bump(build: Build, phase: Phase, count: int = 1) -> None:
    counts = build.stats.touched_per_phase
    counts[phase] = counts.get(phase, 0) + count


def _all_pages(build: Build) -> list[Page]:
    return sorted((n for n in build.graph.nodes() if isinstance(n, Page)), key=lambda p: p.id)


def _render_page_sweep(build: Build, page: Page, out_root: Path) -> None:
    """Render a page and emit only if its HTML changed (early-cutoff).

    The render hook (the render plugin) owns the render cache, so re-rendering a
    page whose inputs are unchanged is a cache hit; the emit-cutoff here means an
    unchanged page touches no output. This sweep over *all* pages is what makes
    site-wide derived data (nav, tags) correct under incremental builds: a page
    is re-emitted iff its rendered HTML actually differs.
    """
    html = build.hooks.render_page.call("", page)
    page.payload = html
    hash_aspect(page, "rendered_html", html)
    _bump(build, Phase.RENDER)
    if build.prev_hashes(page.id).get("rendered_html") != page.hashes["rendered_html"]:
        _emit_page(build, page, out_root, html)
    build.commit_hashes(page.id)


def _markdown_docs(build: Build) -> list[Document]:
    return sorted(
        (n for n in build.graph.nodes() if isinstance(n, Document) and n.kind is NodeKind.MARKDOWN),
        key=lambda d: d.id,
    )


def _finalize_content(build: Build) -> None:
    """Resolve cross-document references in every document's HTML.

    Runs once all documents are parsed: a per-document rewrite chain
    (``finalize_content``: wikilink, then internal links) starting from the
    pre-resolution HTML, then a whole-build expansion pass (``expand_content``:
    transclusion). Re-hashing ``content_html`` is what makes the render sweep
    re-render a page whose resolved content changed -- keeping incremental == full.
    """
    docs = _markdown_docs(build)
    for doc in docs:
        raw = doc.meta.get("__content_html_raw__") or doc.meta.get("content_html")
        if not isinstance(raw, str):
            continue
        # Rebuild this document's reference edges from scratch each finalize.
        for kind in (ConnectionKind.LINK, ConnectionKind.EMBED):
            for conn in build.graph.out_edges(doc.id, kind):
                build.graph.disconnect(conn)
        doc.meta["content_html"] = build.hooks.finalize_content.call(raw, doc)

    build.hooks.expand_content.call(build)  # transclusion embeds finalized content

    for doc in docs:
        hash_aspect(doc, "content_html", doc.meta.get("content_html", ""))


def _finalize(build: Build, out_root: Path) -> None:
    """Recompute site-wide data, then render-sweep every page (full + incremental).

    Both the full build and an incremental rebuild end here, so by construction
    they produce identical output (the critical invariant): ``_finalize`` is a
    pure function of the final graph.
    """
    build.site_data = {}
    _finalize_content(build)
    build.hooks.evaluate_collections.call(build)
    pages = _all_pages(build)
    current = {page.id for page in pages}
    for pid in sorted(build.known_pages() - current):  # pages that vanished
        _delete_output(build, pid, out_root)
    for page in pages:
        _render_page_sweep(build, page, out_root)
    build.set_known_pages(current)


# -- full build ----------------------------------------------------------------


async def full_build(build: Build) -> BuildStats:
    """Discover, parse, generate, render and emit the whole site."""
    builder = build.builder
    content_root, out_root = _roots(build)

    await builder.hooks.make.call(build)  # loaders populate the graph

    documents = [n for n in build.graph.nodes() if n.kind is NodeKind.MARKDOWN]
    for doc in documents:
        if doc.source_path is not None:
            build.register_path(str(content_root / doc.source_path), doc.id)

    for doc in documents:
        build.hooks.parse.call(doc)
        _hash_document_aspects(build, doc)
        build.commit_hashes(doc.id)
    _bump(build, Phase.PARSE, len(documents))

    for doc in documents:
        doc_pages = _generate_doc_pages(build, doc)
        build.set_pages_of(doc.id, [p.id for p in doc_pages])
        for page in doc_pages:
            build.graph.add_node(page)

    _finalize(build, out_root)
    return build.stats


# -- incremental rebuild -------------------------------------------------------


def _rebuild_document(build: Build, doc: Document, out_root: Path, work: WorkList) -> None:
    """Reparse a document and diff its page set.

    Page rendering is deferred to ``_finalize``; here we only refresh the
    expensive per-document content/aspects and add/remove generated page nodes.
    """
    build.hooks.parse.call(doc)
    _hash_document_aspects(build, doc)
    _bump(build, Phase.PARSE)

    old_ids = set(build.pages_of(doc.id))
    new_pages = _generate_doc_pages(build, doc)
    new_ids = [p.id for p in new_pages]

    for pid in old_ids - set(new_ids):  # page-set diff: removed (output cleaned in finalize)
        build.graph.remove(pid)

    for page in new_pages:
        existing = build.graph.get(page.id)
        if existing is None:
            build.graph.add_node(page)
        elif isinstance(existing, Page):  # update route/template in place
            if existing.url != page.url:
                old_rel = build.emitted_output(page.id)
                if old_rel is not None and (out_root / old_rel).is_file():
                    (out_root / old_rel).unlink()
            existing.url = page.url
            existing.template = page.template
            existing.generated_from = page.generated_from

    build.set_pages_of(doc.id, new_ids)
    # Cross-document propagation (e.g. a link target's title changed) wakes the
    # linking documents; page rendering is reconciled in _finalize.
    propagate_aspect_changes(build, doc.id, work)


def run_passes(build: Build, work: WorkList, out_root: Path) -> BuildStats:
    """Process the dirty document frontier to a fixpoint, then finalize."""
    while work:
        seeds = work.drain()
        for nid in sorted(seeds):
            node = build.graph.get(nid)
            if node is None:
                continue
            if node.kind is NodeKind.MARKDOWN and isinstance(node, Document):
                _rebuild_document(build, node, out_root, work)
    _finalize(build, out_root)
    return build.stats


def _resolved(path: str) -> str:
    """Normalize a path to its resolved absolute string (stable map key)."""
    return str(Path(path).resolve())


def _handle_modify(build: Build, abs_path: str, content_root: Path, work: WorkList) -> None:
    nid = build.id_of_path(_resolved(abs_path))
    if nid is None:
        _handle_add(build, abs_path, content_root, work)
        return
    doc = build.graph.get(nid)
    if doc is None:
        return
    text = Path(abs_path).read_text(encoding="utf-8")
    raw_hash = compute_raw_hash(text.encode("utf-8"))
    if doc.hashes.get("raw") == raw_hash:
        return  # raw unchanged -> spurious event short-circuit
    doc.meta = {"__raw__": text}  # clean slate so removed frontmatter keys vanish
    doc.hashes["raw"] = raw_hash
    work.add(nid, Phase.PARSE)


def _handle_add(build: Build, abs_path: str, content_root: Path, work: WorkList) -> None:
    nid = _node_id_for(content_root, abs_path)
    if nid is None:
        return
    text = Path(abs_path).read_text(encoding="utf-8")
    rel = Path(abs_path).resolve().relative_to(content_root).as_posix()
    doc = Document(id=nid, kind=NodeKind.MARKDOWN, source_path=rel)
    doc.meta["__raw__"] = text
    doc.hashes["raw"] = compute_raw_hash(text.encode("utf-8"))
    build.graph.add_node(doc)
    build.register_path(str(content_root / rel), nid)
    work.add(nid, Phase.PARSE)


def _handle_delete(build: Build, abs_path: str, content_root: Path, work: WorkList) -> None:
    key = _resolved(abs_path)
    nid = build.id_of_path(key)
    if nid is None:
        return
    for pid in list(build.pages_of(nid)):
        build.graph.remove(pid)  # output cleaned by the finalize page-set diff
    build.graph.remove(nid)
    build.forget_node(nid)
    build.forget_path(key)


def seed_from_events(
    build: Build, events: Sequence[FsEventLike], content_root: Path, work: WorkList
) -> None:
    """Translate (already coalesced) FS events into dirty seeds."""
    for event in events:
        if event.kind == "modify":
            _handle_modify(build, event.path, content_root, work)
        elif event.kind == "add":
            _handle_add(build, event.path, content_root, work)
        elif event.kind == "delete":
            _handle_delete(build, event.path, content_root, work)
        elif event.kind == "move":
            # Path-based identity: a move is delete(src) + add(dst). Output ends
            # up identical to a fresh build (identity-preserving move-detect for
            # backlinks arrives with links in M6).
            _handle_delete(build, event.path, content_root, work)
            if event.dest is not None:
                _handle_add(build, event.dest, content_root, work)


class IncrementalSession:
    """A persistent build driven by FS events.

    Keeps one ``Build`` (graph + hashes + bookkeeping) across rebuild passes and
    reuses the builder's cache, so each rebuild only recomputes the dirty
    frontier. ``apply`` returns the set of changed output URLs (for live-reload).
    """

    __slots__ = ("build", "builder", "content_root", "out_root")

    def __init__(self, builder: Builder) -> None:
        self.builder = builder
        self.build = builder.create_build()
        # Wire the per-build hooks once for this persistent build.
        builder.hooks.this_compilation.call(self.build)
        self.content_root, self.out_root = _roots(self.build)

    async def initial_build(self) -> BuildStats:
        return await full_build(self.build)

    def apply(self, events: Sequence[FsEventLike]) -> BuildStats:
        """Rebuild for a batch of FS events; returns this rebuild's stats."""
        self.build.stats = BuildStats()
        work = WorkList()
        seed_from_events(self.build, events, self.content_root, work)
        run_passes(self.build, work, self.out_root)
        return self.build.stats
