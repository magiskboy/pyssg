---
title: Integrations
nav_title: Overview
order: 1
---

# Integrations

Integrations connect PySSG to the tools you already write in. Each one is an
official **adapter** - a thin layer that drives a PySSG build from another
application - and lives in the project's `adapters/<name>/` directory with its
own toolchain.

Adapters never fork the engine: they shell out to the `pyssg` command line (or
the Python API) and reuse the same plugins, presets and incremental build that
the CLI uses. Whatever you can build from the terminal, an adapter builds the
same way.

## Available integrations

- **[Obsidian](obsidian.md)** - publish an Obsidian vault as a static site:
  wikilinks, embeds, attachments and selective publishing, with live preview
  inside the editor.

More integrations (other note-taking and authoring apps) will appear here as
they land. They all follow the same pattern, so the concepts you learn for one
adapter carry over to the next.
