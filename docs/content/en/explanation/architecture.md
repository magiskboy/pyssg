---
title: Architecture
nav_title: Architecture
order: 2
---

# Architecture

PySSG is organized as a **small pure kernel** surrounded by **peripheral
plugins**, in the spirit of Webpack's compiler/plugin split. Understanding this
boundary explains most of the design decisions.

## The core is pure standard library

Everything under `pyssg/core/` uses only the Python standard library - no
third-party imports. The core owns the *algorithms*: the dependency graph, the
build phases, the incremental engine, the hook system, and the scheduler. It
knows how to turn a graph of nodes into output, but it knows nothing about
Markdown, Pygments, Jinja, or watchdog.

Anything that needs a third-party library lives at the **periphery**:

- `pyssg/plugins/` - the built-in plugins (Markdown parsing, highlighting,
  navigation, RSS, and so on).
- `pyssg/contrib/` - community plugins (`apidoc`, `external_links`). These ship
  tests and pass `mypy --strict`, but are not auto re-exported into
  `pyssg.plugins`.
- `pyssg/presets/` - pure factories that return a `Config` (a plugin list plus a
  theme); they declare facts, they do not own algorithms.
- `pyssg/themes/` - the built-in Jinja themes.

## Plugins declare facts; the engine owns the algorithms

A plugin's job is to contribute *facts* by tapping hooks: "this is how you parse a
`.md` file", "this document links to that one", "this page's URL is X". The plugin
does **not** decide what is dirty, manage the cache, or schedule work. That keeps
the hard, correctness-critical machinery (incremental invalidation,
deterministic ordering) in one place - the core - rather than spread across every
plugin.

## The data plane: a graph of nodes

A build is a `DependencyGraph` of typed **nodes**. The main node kinds are
`MARKDOWN`, `DATA`, `DIRECTORY`, `ASSET`, and `PAGE`; relations between them are
typed **connections** (`CONTAINMENT`, `LINK`, `EMBED`, `ASSET_REF`, `TEMPLATE`,
`COLLECTION`, `GENERATED_FROM`, ...). A `Document` (a parsed `.md` file) typically
*generates* one `Page`; the `GENERATED_FROM` edge ties them together.

Representing links and embeds as real edges is what makes **backlinks** and
**incremental invalidation** fall out naturally: if you know what links to what,
you know both who to credit with a backlink and what to re-render when a target
moves.

## The control plane: hooks

Plugins attach to **hooks** at well-defined points. There are two scopes:

- **Builder hooks** - on the long-lived compiler (`initialize`, `before_run`,
  `this_compilation`, `make`, `after_emit`, `done`, ...).
- **Build hooks** - on a single compilation (`load_node`, `parse`, `resolve`,
  `finalize_content`, `expand_content`, `generate`, `route`, `render_page`,
  `emit`, ...).

The next page, [The plugin pipeline](plugin-pipeline.md), walks through how a file
travels these hooks to become a page.

## Why code-as-config

Configuration is a Python file (`pyssg.config.py`) that exports a `config`
variable, not YAML or TOML. Code lets you compose plugin *instances* and arbitrary
template variables with full type checking - which is the whole point: the basic
user writes one line, and the advanced user has the entire language available
without a new plugin-configuration DSL.
