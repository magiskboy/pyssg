# benchmarks

Performance benchmarks for pyssg's incremental build engine. They measure
wall-clock cost and work-done counters for a cold full build versus a sequence
of incremental rebuilds, across three synthetic site sizes, then render charts
and a Markdown report.

This package is peripheral tooling. It imports the public pyssg surface but is
never imported back by `pyssg`, and it is free to use third-party libraries
(matplotlib) that the core forbids.

## Running

```bash
uv run python -m benchmarks            # all three sizes + charts
uv run python -m benchmarks --quick    # small + medium only
uv run python -m benchmarks --sizes small,large
uv run python -m benchmarks --no-charts   # JSON only, skip matplotlib
```

Other flags:

- `--results DIR` — output directory (default `benchmarks/results/`).
- `--verify-all` — run the byte-identical check on every size (slow at 10k docs).
- `--no-verify` — skip the byte-identical check entirely.

## Sizes

| Size   | Documents | Iterations / scenario | Byte-identical check |
|--------|----------:|----------------------:|:--------------------:|
| small  |       100 |                    20 | on                   |
| medium |     1 000 |                    10 | on                   |
| large  |    10 000 |                     5 | off by default       |

The largest size runs a from-scratch reference build per scenario only when
verification is enabled, since that dominates wall time at 10k documents. Use
`--verify-all` to force it on.

## Naive vs. incremental

Every scenario iteration measures the *same* content change two ways:

- **naive** — a full rebuild from scratch with the cache disabled
  (`MemoryCache`), i.e. what a non-incremental generator does on every save;
- **incremental** — `IncrementalSession.apply` reusing the persistent
  `FsCache`, recomputing only the dirty frontier.

The reported speedup is `naive_median_ms / incremental_median_ms`. The naive
rebuild also serves as the from-scratch reference: its output is compared
byte-for-byte against the incremental output (`inc == full` must be YES), so
speed is only ever reported for runs that are also correct.

## Scenarios

For each size the runner generates a fresh site, runs one cold full build
through an `IncrementalSession`, then drives four realistic docs/blog scenarios.
Each iteration mutates a *batch* of files (multiple files at once, or the same
file repeatedly) and times one rebuild:

- **rewrite_one** — the same single document edited every iteration (iterative
  authoring). The early-cutoff hot path: one reparse, one re-emitted output.
- **edit_batch** — a batch of documents edited together in one save
  (find/replace burst). Several reparses, one rebuild.
- **publish_batch** — a batch of new posts published at once (a release).
  Structural fan-out: navigation and taxonomy change site-wide.
- **move_batch** — a batch of documents moved at once (restructure), also
  fan-out.

## How the site is generated

`generator.py` writes a complete, buildable site: a `pyssg.config.py` with a
realistic basic blog/docs plugin stack (Markdown, code highlighting,
reading-time/TOC metadata, permalinks, internal links + backlinks, navigation,
a tag taxonomy, sitemap, RSS, asset copying), a copy of the example `docs`
layout, and `content/` populated with Markdown documents grouped into sections.

Generation is fully deterministic — no `random`, no `datetime.now()`; every
varying value is derived from the document index — so runs are reproducible and
the incremental-equals-full check stays meaningful. Each document carries a
publication date, frontmatter tags from a fixed pool, a fenced code block, and
internal links to its neighbours, so highlighting, the taxonomy, RSS ordering,
the link resolver, and backlinks all have real work to do.

## Output

Written to `benchmarks/results/` (gitignored):

- `bench-<size>.json` — raw per-iteration metrics (naive ms, incremental ms,
  docs parsed, cache hits, outputs) plus min/median/mean/max summaries and the
  speedup.
- `scaling.png`, `speedup.png`, `times-<size>.png` — charts.
- `REPORT.md` — the rendered report embedding the charts and summary tables.

## Layout

| Module          | Role                                                            |
|-----------------|-----------------------------------------------------------------|
| `sizes.py`      | declarative small / medium / large definitions                  |
| `generator.py`  | deterministic synthetic-site generator                          |
| `scenarios.py`  | batch Markdown mutation primitives that emit `FsEvent`s          |
| `runner.py`     | runs one size: generate, cold build, naive vs. incremental loops|
| `metrics.py`    | measurement records and JSON serialization                      |
| `visualize.py`  | matplotlib charts + Markdown report                             |
| `__main__.py`   | CLI orchestration                                               |
