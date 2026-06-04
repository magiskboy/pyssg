# pyssg

![Status: in development](https://img.shields.io/badge/status-in%20development-orange)

A fast, incremental static site generator for Markdown, with a Webpack-inspired
plugin architecture. Built for **documentation sites**, **blogs**, and large
**wikis / knowledge bases**.

The core (`pyssg.core`) is pure standard library; every third-party dependency
lives in a peripheral plugin. Builds are deterministic — building twice produces
byte-identical output.

> **Pre-1.0 and in active development.** The public API, configuration, and
> built-in themes may still change without notice. If you depend on pyssg, pin a
> specific commit.

## Features

- **Incremental builds** — on each save, only the pages that actually changed are
  re-rendered; everything else is served from cache. Incremental output is
  guaranteed byte-identical to a full rebuild.
- **Plugin pipeline** — content flows through a chain of hooks (load → parse →
  link → render), each owned by a small, composable plugin. Add your own by
  tapping into a hook.
- **Obsidian-style linking** — `[[wikilinks]]`, `![[transclusion]]`, automatic
  **backlinks**, and broken-link detection out of the box.
- **Zero-config taxonomy** — just add `tags:` or `category:` in frontmatter and
  the `/tags/` and `/categories/` index pages appear automatically.
- **Internationalization (i18n)** — directory-based locales (`content/en/…`,
  `content/vi/…`): the default locale is served at the root, others get a URL
  prefix, and templates receive `lang`, a `translations` switcher, and
  `hreflang` tags. Untranslated pages are skipped, so there are no broken links.
- **Rich Markdown** — code highlighting (Pygments), Mermaid diagrams, internal
  link rewriting, table of contents, reading time, and excerpts.
- **Batteries included** — sidebar navigation, breadcrumbs, prev/next, RSS feed,
  and sitemap generated for you.
- **Live-reload dev server** — `serve` watches your files, rebuilds incrementally,
  and refreshes the browser.

## Requirements

- Python 3.13+
- [uv](https://github.com/astral-sh/uv) (package and environment manager)

## Installation

pyssg is installed directly from GitHub (it is not published to PyPI).

To add it as a dependency in your own project:

```bash
uv add git+https://github.com/magiskboy/pyssg
```

Or clone the repository to develop against it:

```bash
git clone https://github.com/magiskboy/pyssg && cd pyssg
uv sync
```

## Quick start

The fastest way to begin is with a **preset** — a ready-made configuration that
bundles the right plugins and a default theme.

```bash
# Scaffold a new site (use --preset blog for a blog)
pyssg --site my-site new site --preset docs

# Build to my-site/dist
pyssg --site my-site build

# Watch + incremental rebuild + live-reload at http://127.0.0.1:8000
pyssg --site my-site serve
```

`new site` writes a one-line config plus some sample content. The whole config
file is just:

```python
from __future__ import annotations
from pyssg.presets import docs        # or: from pyssg.presets import blog

config = docs(site={"title": "My Docs"}, base_url="https://example.com")
```

Two presets ship today:

- **`docs`** — documentation site: directory-based navigation, taxonomy,
  wikilinks/transclusion, RSS, and sitemap.
- **`blog`** — blog: posts under `content/posts/`, newest-first listing with
  pagination and RSS.

Edit any file under `content/` and the page rebuilds and reloads automatically.

## CLI

| Command | Description |
|---|---|
| `new site --preset docs\|blog\|obsidian` | Scaffold a new site for a preset. |
| `new post --title "..."` | Scaffold a blog post under `content/posts/`. |
| `new theme --name docs\|blog --to DIR` | Copy a built-in theme into your site to customize templates/CSS. |
| `new plugin NAME` | Scaffold a starter plugin module under `plugins/`. |
| `build` | Full build to `output_dir`. |
| `serve` | Watch + incremental rebuild + dev server with live-reload. |
| `clean` | Remove `output_dir` and cache. |
| `deploy list\|status\|<target>` | Push the built site to a hosting provider. |

Pass `--site PATH` to select the site directory (defaults to the current one).
Run any command with `--help` for its options. The earlier `init` and
`eject-layout` commands still work as aliases for `new site` / `new theme`.

## Internationalization (i18n)

Add the `i18n` plugin and lay content out one directory per locale:

```
content/
  en/guide/intro.md   ->  /guide/intro/      (default locale, served at the root)
  vi/guide/intro.md   ->  /vi/guide/intro/
```

```python
from pyssg.presets import docs
from pyssg.plugins import i18n

config = docs(
    site={"title": "My Docs"},
    base_url="https://example.com",
    extra_plugins=[i18n(default_locale="en", locales=["en", "vi"])],
)
```

The rules are deliberately simple, to avoid edge cases:

- The **locale is the top-level directory** — there is no frontmatter override.
- The **default locale** is served at the site root (its prefix is stripped);
  every other locale keeps its `/<locale>/` prefix.
- Content **outside** any locale directory produces no page.
- A page is emitted only for locales that **actually have the file** — there is
  no content fallback, so a language switcher never links to a missing
  translation.

Templates receive three extra variables: `lang` (the current page's locale),
`translations` (the same page in other locales, each `{lang, url, title}`), and
`languages` (all configured locales). The built-in `docs` and `blog` themes use
them to render `<html lang>`, `hreflang` alternates, and a header switcher.

## Examples

```bash
# A small bilingual docs site (English at the root, Vietnamese under /vi/)
# built with the docs preset plus the i18n plugin.
pyssg --site examples/docs serve
```

## Documentation

- Design history: [`docs/content/technical-spec-v0.1.0.md`](docs/content/technical-spec-v0.1.0.md)
- Contributing conventions: [`CLAUDE.md`](CLAUDE.md)

## License

[MIT](LICENSE)
