"""Batch Markdown mutation primitives that drive the rebuilds.

Real docs/blog editing rarely touches exactly one file in isolation: a writer
saves a post and its index together, a find/replace sweeps a whole section, a
release publishes several pages at once. So every primitive here operates on a
*batch* of files and returns the combined :class:`~pyssg.watch.FsEvent` list,
exactly as a debounced watcher burst would. The runner coalesces that batch into
a single rebuild.

All edits are content-relative and deterministic; the marker passed in is the
iteration index, so repeated runs produce identical sequences.
"""

from __future__ import annotations

from pathlib import Path

from benchmarks import generator
from pyssg.watch import FsEvent


def _abs(content_root: Path, rel: str) -> str:
    return str(content_root / rel)


def edit_docs(work: Path, content_root: Path, rels: list[str], marker: int) -> list[FsEvent]:
    """Append a line to each document in ``rels`` (content revision burst)."""
    events: list[FsEvent] = []
    for rel in rels:
        path = work / "content" / rel
        path.write_text(
            path.read_text(encoding="utf-8") + f"\n\nRevision {marker} of this section.\n",
            encoding="utf-8",
        )
        events.append(FsEvent("modify", _abs(content_root, rel)))
    return events


def add_posts(work: Path, content_root: Path, rels: list[str], marker: int) -> list[FsEvent]:
    """Publish a batch of new blog-style posts (a release)."""
    events: list[FsEvent] = []
    for offset, rel in enumerate(rels):
        path = work / "content" / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_post_source(marker, offset), encoding="utf-8")
        events.append(FsEvent("add", _abs(content_root, rel)))
    return events


def delete_docs(work: Path, content_root: Path, rels: list[str]) -> list[FsEvent]:
    """Unpublish a batch of documents."""
    events: list[FsEvent] = []
    for rel in rels:
        (work / "content" / rel).unlink()
        events.append(FsEvent("delete", _abs(content_root, rel)))
    return events


def move_docs(work: Path, content_root: Path, pairs: list[tuple[str, str]]) -> list[FsEvent]:
    """Move a batch of documents (restructure / reorganise)."""
    events: list[FsEvent] = []
    for src_rel, dst_rel in pairs:
        src = work / "content" / src_rel
        dst = work / "content" / dst_rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        src.rename(dst)
        events.append(FsEvent("move", _abs(content_root, src_rel), _abs(content_root, dst_rel)))
    return events


def _post_source(marker: int, offset: int) -> str:
    """A deterministic blog-style post body, consistent with generated docs."""
    idx = 900000 + marker * 100 + offset
    return (
        f"---\n"
        f"title: Release Post {marker:03d}-{offset:02d}\n"
        f"date: {generator._date(idx)}\n"
        f"order: {idx}\n"
        f"tags: [release, news]\n"
        f"---\n\n"
        f"# Release Post {marker:03d}-{offset:02d}\n\n"
        f"{generator._body(idx)}"
    )
