---
title: Customize a theme
nav_title: Customize a theme
order: 3
---

# Customize a theme

**Goal:** change the look of your site by editing templates and CSS, starting
from a built-in theme instead of from scratch.

## 1. Eject a built-in theme

`new theme` copies a built-in theme into your site so you can edit it:

```bash
pyssg --site my-site new theme --name docs --to layouts/theme
```

This copies the `docs` theme into `my-site/layouts/theme/`. (The available themes
are `docs` and `blog`.) The command refuses to overwrite an existing destination,
so you will not clobber a customized layout by accident.

## 2. Point your config at the ejected layout

In `pyssg.config.py`, set `layout` to the copied directory (a path relative to the
site root):

```python
from __future__ import annotations

from pyssg.presets import docs

config = docs(
    site={"title": "My Docs"},
    base_url="https://example.com",
    layout="layouts/theme",
)
```

`layout` accepts either a `str` path relative to the site, or an absolute
`Path` (which is how the built-in themes are referenced internally via
`pyssg.themes.theme_path`).

## 3. Edit templates and styles

Inside `layouts/theme/` you will find the Jinja templates and CSS. Edit them and
re-run `serve` to see changes live:

```bash
pyssg --site my-site serve
```

Templates receive the page's rendered content plus the context variables the
plugins contribute - for example the navigation `menu`, `breadcrumbs`, prev/next
pages, and (if the `i18n` plugin is active) `lang` and `translations`.

## Tip: start from the preset, override only what you need

You do not have to eject the whole theme to tweak one thing. Because a preset is
just a factory returning a `Config`, you can also build a `Config` by hand and
reuse only the plugins you want - see the
[configuration reference](../reference/configuration.md).
