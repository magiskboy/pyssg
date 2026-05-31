# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.1.0] - 2026-05-31

### Changed

- **BREAKING (i18n):** the default locale now renders at the site root instead
  of under a `/<locale>/` prefix. With `i18n_blog`/`i18n_docs`, the default
  locale's pages, index, tag pages and RSS feed move to `/`, `/posts/x/`,
  `/tags/:name/` and `/feed.xml`; non-default locales keep their prefix
  (`/en/...`). The redundant root redirect was removed, so the `root_redirect`
  parameter of `i18n_blog`/`i18n_docs` is gone. The I18n plugin sets
  `meta["locale_prefix"]` (`""` for the default locale) for templates that build
  locale-aware links.

### Fixed

- Per-locale index listings (e.g. `/` and `/en/`) now share one
  `translation_key`, so the home page gets a language switcher across locales.

## [1.0.0] - 2026-05-31

First stable release. The public API of the `pyssg` kernel (plugins, lifecycle
hooks, content model) and the `pyssg` CLI is now considered stable and follows
semantic versioning.

### Added

- **Kernel (`pyssg`)** — stdlib-only core with a webpack-style plugin system and
  lifecycle hooks (`Builder`, `Config`, content model, hook bus, schema
  validation, located `BuildError` reporting).
- **Built-in plugins (`pyssg_plugins`)** — Markdown, Jinja2 templates (with
  cascade), YAML frontmatter, syntax highlighting (Pygments), collections,
  listing, navigation, permalinks, redirects, SEO and social head tags, RSS,
  sitemap, robots.txt, asset fingerprinting, HTML/CSS/JS minification, static
  files, file read/write, build statistics, and a live-reload dev server
  (watchdog-based with a dependency-free mtime-polling fallback).
- **CLI (`pyssg_cli`)** — `pyssg new` (site and post scaffolding), `pyssg build`,
  `pyssg serve` (live reload), ready-made preset stacks, and the official `docs`
  and `blog` themes shipped for fully offline scaffolding.
- `pyssg --version`, reporting the installed distribution version.
- Cross-platform support (Linux, macOS, Windows) verified in CI.

### Packaging

- Single wheel ships three layered packages: `pyssg` (kernel) <-
  `pyssg_plugins` <- `pyssg_cli`. The kernel is dependency-free; third-party
  libraries are optional extras (`markdown`, `template`, `frontmatter`,
  `highlight`, `plugins`, `dev`).
- Distributed as a git-installable package with wheel and sdist attached to each
  GitHub Release.

[Unreleased]: https://github.com/magiskboy/pyssg/compare/v1.1.0...HEAD
[1.1.0]: https://github.com/magiskboy/pyssg/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/magiskboy/pyssg/releases/tag/v1.0.0
