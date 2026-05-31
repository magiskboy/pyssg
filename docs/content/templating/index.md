---
title: Templating
order: 2
---

# Templating

The `Template` plugin renders pages with [Jinja2](https://jinja.palletsprojects.com/),
and adds two Hugo-inspired conveniences on top of it.

- [Inheritance](/templating/inheritance/) - share a base skeleton with
  `{% extends %}` and `{% block %}`.
- [Partials](/templating/partials/) - reuse snippets and components with the
  `partial()` function.
- [Lookup cascade](/templating/lookup-cascade/) - let pages resolve their
  template automatically by type, section and kind, instead of declaring
  `layout` everywhere.

Everything here lives in the `Template` plugin and standard Jinja2 - the kernel
is untouched. This very site uses all three features; its `layouts/` folder is a
working reference.

## The template context

Every template receives:

| Variable | What it is |
|----------|-----------|
| `content` | The rendered HTML body (safe markup). |
| `page` | The page's frontmatter merged with its `meta` (`url`, `prev`, ...). |
| `site` | Site-wide options from `Config.options`. |
| `collections` | Named groups of pages (when `Collections` is used). |
| `menus` | Named navigation trees (when `Navigation` is used). |
| `partial` | The partial render function. |
