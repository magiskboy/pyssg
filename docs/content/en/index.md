---
title: Home
nav_title: Overview
order: 1
---

# PySSG

**PySSG** is a fast, incremental static site generator for Markdown, with a
Webpack-inspired plugin architecture. It is built for **documentation sites**,
**blogs**, and large **wikis / knowledge bases**.

The core (`pyssg.core`) is pure standard library; every third-party dependency
lives in a peripheral plugin. Builds are deterministic - building twice produces
byte-identical output, and an incremental rebuild is guaranteed byte-identical to
a full rebuild.

> This documentation site is itself built with PySSG. The **References** section
> in the sidebar is generated automatically from the project's own docstrings by
> the [`apidoc`](how-to/api-reference.md) contrib plugin.

## Where to start

This documentation follows the [Diátaxis](https://diataxis.fr/) framework, which
splits docs into four kinds, each serving a different need:

- **[Tutorial](tutorial/build-your-first-site.md)** - learning-oriented. Start
  here if you are new: build and serve your first site step by step.
- **[How-to guides](how-to/index.md)** - task-oriented recipes for specific
  problems (add i18n, customize a theme, write a plugin, generate an API
  reference, deploy).
- **[Integrations](integrations/index.md)** - publish from the tools you already
  write in (e.g. an [Obsidian](integrations/obsidian.md) vault).
- **[Reference](reference/index.md)** - information-oriented, precise
  descriptions of the CLI, configuration, frontmatter, and the built-in plugins.
- **[Explanation](explanation/index.md)** - understanding-oriented discussion of
  *why* PySSG works the way it does (architecture, the plugin pipeline,
  incremental builds, the linking model).
- **[References](/references/pyssg/)** - the auto-generated API reference for the
  `pyssg` package.

## Feature highlights

- **Incremental builds** - on each save, only the pages that actually changed are
  re-rendered; everything else is served from cache, and the result is
  byte-identical to a full rebuild.
- **Plugin pipeline** - content flows through a chain of hooks (load -> parse ->
  link -> render), each owned by a small, composable plugin.
- **Obsidian-style linking** - `[[wikilinks]]`, `![[transclusion]]`, automatic
  **backlinks**, and broken-link detection out of the box.
- **Zero-config taxonomy** - add `tags:` or `category:` in frontmatter and the
  `/tags/` and `/categories/` index pages appear automatically.
- **Internationalization** - directory-based locales with a language switcher and
  `hreflang` tags.
- **Rich Markdown** - code highlighting (Pygments), Mermaid diagrams, table of
  contents, reading time, and excerpts.
- **Batteries included** - sidebar navigation, breadcrumbs, prev/next, RSS feed,
  and sitemap generated for you.
- **Live-reload dev server** - `serve` watches your files, rebuilds
  incrementally, and refreshes the browser.

## Requirements

- Python 3.13+
- [uv](https://github.com/astral-sh/uv) (package and environment manager)
