# Changelog

All notable changes to pyssg are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and pyssg adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

pyssg is **pre-1.0 and in active development**: the public API, configuration,
and built-in themes may still change between minor versions. Pin a specific
version or commit if you depend on it.

## [Unreleased]

## [0.2.0] - 2026-06-03

Plugin-design and i18n release. The summarizer plugins gained per-locale output
and were refactored into subclass-friendly classes, and two new built-ins close
gaps surfaced while migrating a real multilingual blog. Builds remain
deterministic and incremental rebuilds byte-identical to a full build.

### Added

- **Redirects plugin** — `redirects({old_url: new_url, ...})` emits a
  `meta refresh` HTML page per rule (with a canonical link and `noindex`), so
  links to retired paths keep resolving after a migration. Rules are literal and
  a rule whose source collides with a real page is skipped.
- **Static-file mounts** — `asset_copy(mounts=[(source, dest), ...])` publishes
  arbitrary static trees (e.g. a site-local `static/` at the output root for
  `/style.css`, `/images/...`, `/robots.txt`), in addition to the layout's
  `assets/`. Sources may be relative (to the site) or absolute; a collision with
  a generated page or another mount aborts the build with a clear error before
  anything is written.
- **Configurable Markdown** — `markdown(extensions=..., extension_configs=...)`
  forwards Python-Markdown options through, and `highlight(linenums=...)`
  toggles code line numbers. Both fold their configuration into the render cache.

### Changed

- **Locale-aware feeds, taxonomy, and pagination** — on an i18n site the RSS
  feed, `/tags/` & `/categories/` term pages, and collection pagination are now
  partitioned per locale (the default locale at the root, others URL-prefixed),
  so generated pages never mix languages. RSS items also carry `<guid>` and
  `<pubDate>`.
- **Subclass-friendly plugins** — `markdown`, `rss`, `taxonomy`, and
  `collections` were refactored into classes with small overridable methods, so
  a site customizes behavior by subclassing rather than forking the plugin.

## [0.1.0] - 2026-06-02

First release of the rewritten pyssg. The core (`pyssg.core`) is pure standard
library; every third-party dependency lives in a peripheral plugin. Builds are
deterministic — building twice produces byte-identical output, and an
incremental rebuild is byte-identical to a full rebuild.

### Added

- **Incremental build engine** — a dependency graph re-renders only the pages
  affected by a change; everything else is served from cache.
- **Webpack-inspired plugin pipeline** — content flows through `load → parse →
  link → render` hooks, each owned by a small, composable plugin. Plugins
  declare facts; the engine owns the algorithms (dirtiness propagation, caching).
- **Presets** — `docs` and `blog`, each a pure factory bundling a plugin list
  and a theme.
- **Built-in themes** — three starter themes (`blog-minimal`, `blog-technical`,
  `docs-technical`) plus a `Config.theme` configuration API, with
  `eject-layout` to copy a theme into a site for customization.
- **Obsidian-style linking** — `[[wikilinks]]` (with aliases and heading
  anchors), `![[transclusion]]`, automatic backlinks, and build-time
  broken-link detection.
- **Obsidian vault publishing** — publish a vault as a static site, gated by a
  `publish: true` frontmatter flag.
- **Internationalization (i18n)** — directory-based locales, with the default
  locale served at the root and others URL-prefixed; templates receive `lang`,
  `translations`, `languages`, `hreflang` alternates, and locale-aware
  navigation. UI strings are translatable via tables and a template `t()`
  helper. Untranslated pages are skipped, so a switcher never links to a
  missing translation.
- **Rich Markdown** (Python-Markdown engine) — Pygments code highlighting with
  configurable line numbers, Mermaid diagrams, tables, table of contents with
  heading ids, internal link rewriting, reading time, and excerpts.
- **Zero-config taxonomy** — `/tags/` and `/categories/` index pages generated
  from frontmatter.
- **Batteries included** — sidebar navigation, breadcrumbs, prev/next, RSS feed,
  and sitemap.
- **Unicode-aware slugify** with a configurable slug function.
- **Live-reload dev server** — `serve` watches files, rebuilds incrementally,
  and refreshes the browser.
- **Deploy subsystem** — `pyssg deploy` with `github-pages`, `cloudflare`, and
  `netlify` targets.
- **AI-friendly output** (`contrib`) — an `llms.txt` / `llms-full.txt` plugin
  with raw content emit and resolved links.
- **Document graph** (`contrib`) — emits `graph.json` plus an interactive 2D/3D
  view.
- **API reference generation** (`contrib`) — an `apidoc` plugin that builds the
  References section of the docs site from Python docstrings.
- **CLI** — `init`, `build`, `serve`, `clean`, and `eject-layout`.

[Unreleased]: https://github.com/magiskboy/pyssg/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/magiskboy/pyssg/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/magiskboy/pyssg/releases/tag/v0.1.0
