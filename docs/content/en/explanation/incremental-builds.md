---
title: Incremental builds and determinism
nav_title: Incremental builds
order: 4
---

# Incremental builds and determinism

The single most important property of PySSG is this invariant:

> **An incremental rebuild is byte-identical to a full rebuild.**

Everything about the incremental engine exists to uphold it. This page explains
what that means and how it is achieved.

## Determinism first

Before incremental builds can be *correct*, builds must be **deterministic**:
building the same inputs twice produces byte-identical output. PySSG enforces this
by making every processing unit pure with respect to its declared inputs:

- no global mutable state,
- no direct `datetime.now()`, `time`, or `random`,
- nodes and members are emitted in a stable, sorted order.

Determinism is what makes "incremental == full" even *checkable*: if a full build
were nondeterministic, there would be no fixed target to match.

## How incremental works

A full build marks every node dirty from the `LOAD` phase and processes the whole
graph. An incremental rebuild instead:

1. **Seeds a worklist** from filesystem events (a file was created, modified,
   moved, or deleted).
2. **Hashes aspects** of each node (its raw bytes, its parsed content, its
   metadata) and compares them to the cached hashes.
3. **Propagates only real changes** along the dependency edges, converging to a
   fixpoint with early cutoff - if a node's relevant aspect did not change, work
   stops there and downstream nodes are served from cache.

Because the per-node and per-page processing is the *same code* the full build
runs, a rebuilt node cannot diverge from its full-build version.

## A worked example: navigation

Navigation appears on every page, so it is the classic "how can this possibly stay
incremental?" case. PySSG handles it without any special-casing in the `nav`
plugin:

- A **structural** change (add, move, or delete a document) changes the menu.
  Every page's rendered HTML therefore differs and is re-emitted - correctly.
- A **body-only** edit leaves the menu identical. Other pages hash to the same
  rendered HTML, hit the render cache, and are not re-emitted.

The plugin just declares the menu as a fact; the engine's render sweep decides
what actually changed. This is the general pattern: **plugins declare facts, the
engine owns invalidation.**

## Why plugins must not manage the cache

If a plugin tried to propagate its own dirtiness or poke the cache, two plugins
could disagree about what changed and the invariant would break. Keeping all
invalidation in the core - driven by content hashes and graph edges - is what lets
many independent plugins compose without breaking byte-for-byte reproducibility.

## Testing the invariant

The invariant is not aspirational; it is tested. The project's check suite
includes boundary tests, a determinism test (build twice, compare bytes), and an
`incremental == full` test. A change that breaks any of these does not merge.
