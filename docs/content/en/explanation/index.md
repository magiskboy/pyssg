---
title: Explanation
nav_title: Overview
order: 1
---

# Explanation

These pages discuss *why* PySSG is built the way it is. They are for understanding,
not for step-by-step tasks - read them when you want the mental model behind the
tool.

- [Architecture](architecture.md) - the small pure core and the peripheral
  plugins around it.
- [The plugin pipeline](plugin-pipeline.md) - hooks, phases, and how content flows
  from a file to a page.
- [Incremental builds and determinism](incremental-builds.md) - the core
  invariant and how it is upheld.
- [The linking model](linking-model.md) - wikilinks, transclusion, backlinks, and
  internal link resolution.
