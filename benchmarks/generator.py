"""Deterministic synthetic-site generator for the benchmarks.

Given a target document count, this writes a complete, buildable pyssg site into
a destination directory: a ``pyssg.config.py``, a copy of the example ``docs``
layout (templates + assets), and ``content/`` populated with Markdown documents.

Generation is fully deterministic -- the same inputs always produce byte-identical
files. No ``random``, no ``datetime.now()``: every varying value is derived from
the document index. That keeps benchmark runs reproducible and lets the
incremental-equals-full check stay meaningful.

The generated documents are wired to exercise the incremental engine's fan-out:
each carries frontmatter tags drawn from a fixed pool (so the taxonomy builds
real term pages) and internal Markdown links to its neighbours (so the link
resolver and backlinks have work to do).
"""

from __future__ import annotations

import datetime as dt
import shutil
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
LAYOUT_SRC = REPO_ROOT / "examples" / "docs" / "layout"

# A fixed epoch so each document gets a stable, blog-like publication date
# derived from its index -- deterministic, never a wall clock.
_EPOCH = dt.date(2020, 1, 1)


def _date(index: int) -> str:
    """A deterministic ISO date for document ``index`` (drives RSS ordering)."""
    return (_EPOCH + dt.timedelta(days=index)).isoformat()


# A fixed tag pool; each document takes a deterministic two-tag slice of it.
TAG_POOL = (
    "guide",
    "reference",
    "tutorial",
    "concept",
    "howto",
    "internals",
    "api",
    "design",
)

# A few fixed sentences cycled by index to give each document a stable body with
# enough words for reading-time and excerpt computation, without any randomness.
_SENTENCES = (
    "The incremental engine recomputes only the dirty frontier of the graph.",
    "Each plugin declares facts while the engine owns the algorithm.",
    "Aspect hashing lets a rebuild stop early when nothing observable changed.",
    "Collections are evaluated in function form and diffed against the prior run.",
    "A persistent cache serves unchanged renders straight from disk.",
    "Navigation and taxonomy pages fan out across the whole site on structural edits.",
)

CONFIG_SOURCE = """\
from __future__ import annotations

from pyssg import Config
from pyssg.plugins import (
    asset_copy,
    content_meta,
    directory_loader,
    frontmatter,
    highlight,
    link_resolver,
    markdown,
    nav,
    permalink,
    render,
    rss,
    sitemap,
    taxonomy,
)

# A realistic basic blog/docs stack: directory loading, frontmatter, Markdown,
# code highlighting, reading-time/TOC/excerpt metadata, clean permalinks,
# internal-link rewriting + backlinks, navigation (sidebar/breadcrumbs/
# prev-next), a tag taxonomy, sitemap, an RSS feed, and asset copying. It mirrors
# the example "docs" site minus the more niche mermaid/wikilink/transclude
# plugins, so the benchmark exercises the same fan-out a real site would.
config = Config(
    content_dir="content",
    output_dir="dist",
    layout="layout",
    base_url="https://bench.pyssg.example.com",
    site={"title": "pyssg benchmark site"},
    plugins=[
        directory_loader(),
        frontmatter(),
        markdown(),
        highlight(style="friendly"),
        content_meta(),
        permalink(),
        link_resolver(),
        nav(),
        taxonomy(),
        sitemap(),
        rss(title="pyssg benchmark site"),
        asset_copy(),
        render(),
    ],
)
"""


def doc_rel_path(index: int, docs_per_section: int) -> str:
    """The content-relative path of document ``index`` (POSIX, no leading slash)."""
    section = index // docs_per_section
    return f"section-{section:03d}/doc-{index:05d}.md"


def _body(index: int) -> str:
    """A deterministic Markdown body for document ``index``.

    Includes a fenced code block so the highlight plugin does real work, like a
    typical docs page.
    """
    s = _SENTENCES
    intro = " ".join(s[(index + k) % len(s)] for k in range(3))
    detail = " ".join(s[(index + k) % len(s)] for k in range(2, 5))
    code = (
        "```python\n"
        f"def build_page_{index:05d}(graph):\n"
        '    """Recompute only the dirty frontier."""\n'
        "    return [node for node in graph.dirty() if node.observable]\n"
        "```"
    )
    return f"{intro}\n\n## Overview\n\n{detail}\n\n{code}\n\n## Details\n\n{intro} {detail}\n"


def _document(index: int, n_docs: int, docs_per_section: int) -> str:
    """Render the full Markdown source (frontmatter + body) for one document."""
    tag_a = TAG_POOL[index % len(TAG_POOL)]
    tag_b = TAG_POOL[(index * 3 + 1) % len(TAG_POOL)]
    tags = sorted({tag_a, tag_b})

    # Link to the previous and next documents to give the link resolver and the
    # backlink builder real cross-document edges to track.
    links: list[str] = []
    if index > 0:
        prev_rel = doc_rel_path(index - 1, docs_per_section)
        links.append(f"- See also [previous]({_link_to(index, prev_rel, docs_per_section)})")
    if index + 1 < n_docs:
        next_rel = doc_rel_path(index + 1, docs_per_section)
        links.append(f"- See also [next]({_link_to(index, next_rel, docs_per_section)})")
    links_block = ("\n".join(links) + "\n\n") if links else ""

    tags_line = "[" + ", ".join(tags) + "]"
    return (
        f"---\n"
        f"title: Document {index:05d}\n"
        f"date: {_date(index)}\n"
        f"order: {index}\n"
        f"tags: {tags_line}\n"
        f"---\n\n"
        f"# Document {index:05d}\n\n"
        f"{links_block}"
        f"{_body(index)}"
    )


def _link_to(from_index: int, target_rel: str, docs_per_section: int) -> str:
    """A relative ``.md`` link from one document to another (resolved by the engine)."""
    from_rel = doc_rel_path(from_index, docs_per_section)
    return _relative(from_rel, target_rel)


def _relative(from_rel: str, target_rel: str) -> str:
    """POSIX relative link from ``from_rel`` to ``target_rel`` (both content-relative)."""
    from_dir = Path(from_rel).parent
    rel = Path(target_rel)
    # Compute a ../ style path manually to stay deterministic and OS-independent.
    from_parts = from_dir.parts
    to_parts = rel.parts
    common = 0
    for a, b in zip(from_parts, to_parts[:-1], strict=False):
        if a != b:
            break
        common += 1
    ups = [".."] * (len(from_parts) - common)
    downs = list(to_parts[common:])
    return "/".join([*ups, *downs]) or rel.name


def generate_site(dest: Path, n_docs: int, docs_per_section: int) -> Path:
    """Write a complete, buildable site of ``n_docs`` documents into ``dest``.

    Any existing ``dest`` is removed first so generation is idempotent. Returns
    the resolved site directory.
    """
    dest = dest.resolve()
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)

    (dest / "pyssg.config.py").write_text(CONFIG_SOURCE, encoding="utf-8")
    shutil.copytree(LAYOUT_SRC, dest / "layout")

    content = dest / "content"
    content.mkdir()
    # Section index pages keep the nav sidebar well-formed for every section.
    written_sections: set[int] = set()
    for index in range(n_docs):
        section = index // docs_per_section
        section_dir = content / f"section-{section:03d}"
        if section not in written_sections:
            section_dir.mkdir(parents=True, exist_ok=True)
            written_sections.add(section)
        rel = doc_rel_path(index, docs_per_section)
        (content / rel).write_text(_document(index, n_docs, docs_per_section), encoding="utf-8")

    return dest
