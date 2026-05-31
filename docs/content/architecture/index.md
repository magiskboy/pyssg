---
title: Architecture
order: 4
---

# Architecture

pyssg borrows its core design from webpack. Four ideas carry the whole system:

| webpack | pyssg | Role |
|---------|-------|------|
| Tapable | hook system | The nervous system: typed lifecycle hooks. |
| Compiler | `Builder` | Long-lived orchestrator; owns the hooks. |
| Compilation | `Build` | State of a single build run. |
| Plugin | `Plugin` | An object with `apply(builder)` that taps hooks. |

The key property: **the kernel only emits events at lifecycle milestones.**
Plugins register listeners and do the actual work - even "core" tasks like
reading files or rendering Markdown are plugins.

## In this section

- [The kernel](/architecture/kernel/) - what lives in the core and why it is so
  small.
- [Lifecycle](/architecture/lifecycle/) - the phased passes a build goes
  through.
- [Hooks](/architecture/hooks/) - the three hook types and how `stage` ordering
  works.

## Data model

Two neutral data bags flow through the lifecycle:

- **`Source`** - one input file. Plugins fill in `raw`, `body`, `frontmatter`,
  `content` and `meta` as it moves through the passes.
- **`Output`** - one file to be written. Has a `path` (relative to `out`) and
  `content`.

The kernel never inspects these beyond moving them between hooks; their meaning
is entirely up to plugins.
