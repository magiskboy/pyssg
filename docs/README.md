# pyssg documentation site

The documentation for pyssg, built by pyssg itself using the `docs()` preset.

## Build

```bash
uv sync --extra plugins
source .venv/bin/activate
cd docs
pyssg build
```

The site is written to `docs/public/`. Open `docs/public/index.html` in a
browser, or serve the folder:

```bash
python -m http.server -d public
```

## Layout

```text
docs/
  content/          # Markdown sources (one folder per section)
  layouts/          # Jinja2 templates (default.html)
  assets/           # static files (style.css) copied via StaticFiles
  pyssg.config.py   # uses the docs() preset + StaticFiles
```
