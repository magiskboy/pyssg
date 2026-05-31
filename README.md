# pyssg

[![CI](https://github.com/magiskboy/pyssg/actions/workflows/ci.yml/badge.svg)](https://github.com/magiskboy/pyssg/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.13+](https://img.shields.io/badge/python-3.13%2B-blue.svg)](https://www.python.org/downloads/)

A fast, batteries-included static site generator for Python. Turn a folder of
Markdown into a production-ready website — documentation, a blog, or a landing
page — with no Node toolchain and no build step of your own.

## Features

- **Scaffolding** — `pyssg new` gives you a working site from a built-in theme
  (`docs` or `blog`) that runs fully offline.
- **Live dev server** — `pyssg serve` rebuilds and reloads the browser on change.
- **Markdown + Jinja2 templates** with frontmatter, theme inheritance, and
  reusable partials.
- **Content structure out of the box** — collections, tags, pagination, menus,
  and prev/next navigation.
- **Production output** — sitemaps, RSS feeds, SEO/Open Graph tags, asset
  fingerprinting, syntax highlighting, HTML minification, `robots.txt`, and
  redirects.
- **AI-friendly** — optionally serve a raw Markdown version of each page next to
  the HTML.
- **Helpful errors** — friendly build errors with `file:line`, shown as an
  in-browser overlay while you develop.

## Installation

pyssg installs directly from GitHub. Most sites want the `plugins` extra
(Markdown, Jinja2, YAML frontmatter, syntax highlighting):

```bash
# uv (recommended)
uv add "pyssg[plugins] @ git+https://github.com/magiskboy/pyssg.git"

# pin to a released version
uv add "pyssg[plugins] @ git+https://github.com/magiskboy/pyssg.git@v0.1.0"

# pip
pip install "pyssg[plugins] @ git+https://github.com/magiskboy/pyssg.git"
```

## Quickstart

```bash
# Scaffold a new site from a built-in theme (works offline)
pyssg new mysite --theme docs        # or: --theme blog
cd mysite

# Live preview with rebuild-on-change at http://127.0.0.1:8000
pyssg serve

# Build the production site into ./public
pyssg build
```

Add a new blog post:

```bash
pyssg new post "My first post"
```

## Configuration

A site is configured by a `pyssg.config.py` file that exposes a `config()`
function. The simplest setup picks a preset:

```python
from pyssg.config import Config
from pyssg_cli.presets import docs, blog, site


def config() -> Config:
    return Config(src="content", out="public", plugins=blog(page_size=10))
```

- `docs()` — technical documentation: folder-based sidebar plus prev/next.
- `blog()` — personal blog: paginated index, tag pages, RSS feed.
- `site()` — simple website: flat menu and standalone pages.

Common options are passed as keyword arguments, for example
`blog(page_size=10, rss=True, sitemap=True, minify=True)`.

```bash
pyssg build                  # uses pyssg.config.py in the current directory
pyssg build -c path/to/config.py
pyssg serve --port 3000 --no-livereload
```

Need finer control — custom plugins, manual lifecycle composition, or building
your own theme? See the documentation.

## Documentation

Full guides (getting started, configuration, templating, plugins, deployment,
and the plugin/lifecycle architecture) live in [`docs/`](docs/) — and the docs
site is itself built with pyssg:

```bash
cd docs && pyssg build         # -> docs/public/
python -m http.server -d public
```

Deployment recipes for GitHub Pages, Netlify, and Cloudflare Pages are in
[`recipes/deploy/`](recipes/deploy/).

## Contributing

Contributions are welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for development
setup and conventions, and [SECURITY.md](SECURITY.md) for reporting
vulnerabilities.

## License

[MIT](LICENSE) © magiskboy and pyssg contributors.
