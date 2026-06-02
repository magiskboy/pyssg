---
title: Plugins and hooks
nav_title: Plugins and hooks
order: 5
---

# Plugins and hooks

This page lists the built-in and contrib plugins, and the hook points a plugin can
tap. For the auto-generated, per-symbol API of every module, see the
[References](/references/pyssg/) section.

## Built-in plugins (`pyssg.plugins`)

These are the plugins bundled with pyssg and used by the presets.

| Plugin | Purpose |
|---|---|
| `directory_loader` | Discovers source files under `content/`. |
| `frontmatter` | Splits YAML frontmatter from the body. |
| `markdown` | Loads and parses Markdown to HTML (Python-Markdown). |
| `mermaid` | Renders Mermaid diagrams client-side. |
| `highlight` | Colourises fenced code blocks via Pygments. |
| `content_meta` | TOC / outline, word count, reading time, excerpt. |
| `permalink` | Assigns each page its output URL. |
| `wikilink` | Obsidian-style `[[...]]` links. |
| `link_resolver` | Rewrites internal `.md` links; records backlinks. |
| `transclude` | Obsidian-style `![[...]]` embeds. |
| `nav` | Sidebar menu, breadcrumbs, and prev/next. |
| `taxonomy` | Zero-config `tags` and `categories` index pages. |
| `collections` | Declarative, paginated lists of documents. |
| `i18n` | Directory-based locales and UI-string tables (see the [i18n reference](/reference/i18n/)). |
| `rss` | RSS feed. |
| `sitemap` | `sitemap.xml`. |
| `asset_copy` | Copies static assets to the output. |
| `render` | Renders pages through the Jinja layout. |

## Contrib plugins (`pyssg.contrib`)

Community plugins. They ship tests and pass `mypy --strict`, but are **not** auto
re-exported into `pyssg.plugins` - import them from their module.

| Plugin | Import | Purpose |
|---|---|---|
| `apidoc` | `from pyssg.contrib.apidoc import apidoc` | A `References` section from Python docstrings (see [the how-to](../how-to/api-reference.md)). |
| `external_links` | `from pyssg.contrib.external_links import external_links` | Opens off-site links in a new tab with `rel="noopener noreferrer"`. |

## The hook system

A plugin is an object with a `name` and an `apply(builder)` method; inside `apply`
it taps hooks. Hooks come in four flavors, each with a different value-flow
semantic:

| Flavor | Semantic |
|---|---|
| `SyncHook` | Call every tap for side effects. |
| `AsyncSeriesHook` | Await each tap in order (I/O, e.g. emitting files). |
| `WaterfallHook` | Thread a value through the taps; each returns the next input. |
| `BailHook` | Stop at the first tap that returns a non-`None` value. |

Taps order themselves with a coarse `stage` integer plus `before` / `after` name
constraints; the taps are topologically sorted before each call (a cycle raises
`HookOrderError`).

### Builder hooks (`builder.hooks`)

Scoped to the long-lived compiler.

| Hook | Flavor | When |
|---|---|---|
| `initialize` | Sync | Builder created. |
| `before_run` | AsyncSeries | Before a build run. |
| `this_compilation` | Sync | A fresh `Build` was created. |
| `make` | AsyncSeries | Inject synthetic nodes into the graph (used by `apidoc`). |
| `after_emit` | AsyncSeries | After all output is emitted. |
| `done` | Sync | Build finished (receives `BuildStats`). |
| `failed` | Sync | Build raised. |
| `watch_run` | AsyncSeries | A watch-triggered rebuild starts. |
| `invalidate` | Sync | Nodes were invalidated. |

### Build hooks (`build.hooks`)

Scoped to a single compilation.

| Hook | Flavor | Role |
|---|---|---|
| `load_node` | Bail | Load a source path into a `Node`. |
| `parse` | Sync | Parse a loaded node. |
| `resolve` | Bail | Resolve a dependency into a `Connection`. |
| `evaluate_collections` | Sync | Build whole-graph lists (nav, taxonomy, link resolution). |
| `finalize_content` | Waterfall | Per-document content rewrite (wikilink @100, link_resolver @200, external_links @300). |
| `expand_content` | Sync | Whole-build content expansion (transclusion). |
| `generate` | Sync | Generate pages from documents. |
| `route` | Waterfall | Compute a page URL; returning `""` means "no page". |
| `transform` | Waterfall | Transform node payloads. |
| `render_page` | Waterfall | Produce the final HTML. |
| `process_assets` | Sync | Process / optimize assets. |
| `emit` | AsyncSeries | Write output files. |
| `after_emit` | AsyncSeries | Per-build post-emit work. |

To write one, see [Write a custom plugin](../how-to/write-a-plugin.md).
