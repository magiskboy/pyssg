"""Execute the benchmark for one site size.

The flow per size mirrors a real editing session: generate the site, run one
cold full build through an :class:`~pyssg.core.phases.IncrementalSession`, then
drive a series of realistic docs/blog scenarios. Each scenario iteration mutates
a *batch* of Markdown files and then measures that exact change two ways:

* **naive** -- a full rebuild from scratch with the cache disabled
  (``MemoryCache``), i.e. what a non-incremental generator does on every save;
* **incremental** -- ``IncrementalSession.apply`` reusing the persistent cache.

The naive rebuild also serves as the from-scratch reference: its output is
compared byte-for-byte against the incremental output, so the speed numbers are
only ever reported for runs that are also correct.
"""

from __future__ import annotations

import asyncio
import shutil
import time
from pathlib import Path

from benchmarks import generator, scenarios
from benchmarks.metrics import IterationMetric, ScenarioMetric, SizeReport, make_iteration
from benchmarks.sizes import SiteSize
from pyssg.cli.common import build_site, make_builder
from pyssg.core.incremental.cache import MemoryCache
from pyssg.core.phases import IncrementalSession
from pyssg.watch import FsEvent, coalesce

_IGNORE = shutil.ignore_patterns("dist", ".pyssg-cache", "__pycache__", "*.pyc")


def _files_map(root: Path) -> dict[str, str]:
    """Map every file under ``root`` to its text, for byte-identical comparison."""
    return {
        p.relative_to(root).as_posix(): p.read_text(encoding="utf-8", errors="replace")
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


def _naive_build(site: Path, ref_dir: Path) -> tuple[float, dict[str, str]]:
    """Full-rebuild the current content of ``site`` from scratch, cache disabled.

    Returns the wall time in ms and the resulting output map. A fresh copy with
    no ``.pyssg-cache`` plus a ``MemoryCache`` guarantees nothing is reused --
    the non-incremental baseline.
    """
    if ref_dir.exists():
        shutil.rmtree(ref_dir)
    shutil.copytree(site, ref_dir, ignore=_IGNORE)
    t0 = time.perf_counter()
    build_site(ref_dir, MemoryCache())
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    return elapsed_ms, _files_map(ref_dir / "dist")


def _batch_sizes(n_docs: int) -> dict[str, int]:
    """Per-scenario batch sizes, scaled to the site but floored for small sites."""
    return {
        "edit_batch": min(n_docs, max(3, n_docs // 20)),
        "publish_batch": min(n_docs, max(2, n_docs // 50)),
        "move_batch": min(n_docs, max(2, n_docs // 50)),
    }


def _spread(i: int, count: int, n_docs: int, span: int = 1) -> list[int]:
    """``span`` document indices for iteration ``i``, spread deterministically."""
    step = max(1, n_docs // max(1, count))
    start = (i * step) % n_docs
    return [(start + j) % n_docs for j in range(span)]


def run_size(size: SiteSize, workdir: Path, *, verify: bool) -> SizeReport:
    """Generate, cold-build, and run every scenario for one size; return its report."""
    site = workdir / f"site-{size.name}"
    ref_dir = workdir / f"ref-{size.name}"
    generator.generate_site(site, size.n_docs, size.docs_per_section)
    content_root = (site / "content").resolve()

    session = IncrementalSession(make_builder(site))
    t0 = time.perf_counter()
    cold_stats = asyncio.run(session.initial_build())
    cold_ms = (time.perf_counter() - t0) * 1000.0

    batch = _batch_sizes(size.n_docs)
    scenario_metrics: list[ScenarioMetric] = [
        _rewrite_one(session, site, ref_dir, content_root, size, verify),
        _edit_batch(session, site, ref_dir, content_root, size, batch["edit_batch"], verify),
        _publish_batch(session, site, ref_dir, content_root, size, batch["publish_batch"], verify),
        _move_batch(session, site, ref_dir, content_root, size, batch["move_batch"], verify),
    ]

    return SizeReport(
        size=size.name,
        n_docs=size.n_docs,
        cold_incremental_ms=cold_ms,
        cold_outputs=len(cold_stats.changed_outputs),
        scenarios=scenario_metrics,
    )


def _record(
    session: IncrementalSession,
    site: Path,
    ref_dir: Path,
    events: list[FsEvent],
    iteration: int,
    files_changed: int,
    verify: bool,
) -> IterationMetric:
    """Run naive + incremental for one batch and return the iteration metric."""
    naive_ms, naive_dist = _naive_build(site, ref_dir)

    batch = coalesce(events)
    t0 = time.perf_counter()
    stats = session.apply(batch)
    incremental_ms = (time.perf_counter() - t0) * 1000.0

    identical = (_files_map(site / "dist") == naive_dist) if verify else True
    return make_iteration(iteration, files_changed, naive_ms, incremental_ms, stats, identical)


def _rewrite_one(
    session: IncrementalSession,
    site: Path,
    ref_dir: Path,
    content_root: Path,
    size: SiteSize,
    verify: bool,
) -> ScenarioMetric:
    """Iterative authoring: the same single document edited every iteration."""
    rel = generator.doc_rel_path(size.n_docs // 3, size.docs_per_section)
    iters: list[IterationMetric] = []
    for i in range(size.iterations):
        events = scenarios.edit_docs(site, content_root, [rel], i)
        iters.append(_record(session, site, ref_dir, events, i, 1, verify))
    return ScenarioMetric(
        name="rewrite_one",
        description="Same single document edited repeatedly (iterative authoring).",
        batch_size=1,
        iterations=iters,
    )


def _edit_batch(
    session: IncrementalSession,
    site: Path,
    ref_dir: Path,
    content_root: Path,
    size: SiteSize,
    batch_size: int,
    verify: bool,
) -> ScenarioMetric:
    """Multi-file content revision: a batch of documents edited in one save."""
    iters: list[IterationMetric] = []
    for i in range(size.iterations):
        idxs = _spread(i, size.iterations, size.n_docs, span=batch_size)
        rels = [generator.doc_rel_path(idx, size.docs_per_section) for idx in idxs]
        events = scenarios.edit_docs(site, content_root, rels, i)
        iters.append(_record(session, site, ref_dir, events, i, len(rels), verify))
    return ScenarioMetric(
        name="edit_batch",
        description=f"{batch_size} documents edited together per rebuild (find/replace burst).",
        batch_size=batch_size,
        iterations=iters,
    )


def _publish_batch(
    session: IncrementalSession,
    site: Path,
    ref_dir: Path,
    content_root: Path,
    size: SiteSize,
    batch_size: int,
    verify: bool,
) -> ScenarioMetric:
    """Release: a batch of new posts published in one rebuild (structural fan-out)."""
    iters: list[IterationMetric] = []
    for i in range(size.iterations):
        rels = [f"releases/post-{i:03d}-{j:02d}.md" for j in range(batch_size)]
        events = scenarios.add_posts(site, content_root, rels, i)
        iters.append(_record(session, site, ref_dir, events, i, len(rels), verify))
    return ScenarioMetric(
        name="publish_batch",
        description=f"{batch_size} new posts published per rebuild (release).",
        batch_size=batch_size,
        iterations=iters,
    )


def _move_batch(
    session: IncrementalSession,
    site: Path,
    ref_dir: Path,
    content_root: Path,
    size: SiteSize,
    batch_size: int,
    verify: bool,
) -> ScenarioMetric:
    """Restructure: a batch of documents moved per rebuild (structural fan-out)."""
    iters: list[IterationMetric] = []
    for i in range(size.iterations):
        idxs = _spread(i, size.iterations, size.n_docs, span=batch_size)
        pairs: list[tuple[str, str]] = []
        for j, idx in enumerate(idxs):
            src = generator.doc_rel_path(idx, size.docs_per_section)
            head = src.rsplit("/", 1)
            dst = (head[0] + "/" if len(head) == 2 else "") + f"moved-{i:03d}-{j:02d}.md"
            pairs.append((src, dst))
        events = scenarios.move_docs(site, content_root, pairs)
        iters.append(_record(session, site, ref_dir, events, i, len(pairs), verify))
    return ScenarioMetric(
        name="move_batch",
        description=f"{batch_size} documents moved per rebuild (restructure).",
        batch_size=batch_size,
        iterations=iters,
    )
