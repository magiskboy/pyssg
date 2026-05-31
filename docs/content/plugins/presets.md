---
title: Presets
order: 2
---

# Presets

A preset is just a function returning a configured list of plugins. They give
beginners a working setup in one line, while leaving power users free to
assemble plugins by hand.

```python
from pyssg_cli.presets import docs, blog, site
```

## `docs()`

Technical documentation: a folder-based sidebar with prev/next links.

```python
docs(markdown_extensions=("fenced_code", "tables"))
```

Stack: `ReadFile`, `Frontmatter`, `Markdown`, `Permalink`, `Collections`
(by folder), `Navigation` (folder mode, sequential), `Template`, `WriteFile`.

This is the preset that builds the site you are reading.

## `blog()`

A personal blog: a paginated index, one page per tag, and a top menu.

```python
blog(page_size=10)
```

Stack adds two `Listing` plugins (the blog index and the tag pages) and a
frontmatter-driven `Navigation`.

## `site()`

A company or organisation site: a flat top menu and standalone pages.

```python
site()
```

The leanest preset - permalinks, a frontmatter menu, and the tier-1 pipeline.

## Customising a preset

Every preset accepts keyword arguments for the common knobs:

| Argument | Presets | Default |
|----------|---------|---------|
| `markdown_extensions` | all | `()` |
| `template_dir` | all | `"layouts"` |
| `clean` | all | `True` |
| `page_size` | `blog` | `10` |
| `sitemap` | all | `False` |
| `minify` | all | `False` |
| `robots` | all | `False` |
| `markdown_pages` | all | `False` |
| `seo` | all | `True` |
| `rss` | `blog` | `True` |

For example, a production docs build with a sitemap and minified HTML:

```python
docs(sitemap=True, minify=True)
```

If you need more control, copy the preset's body into your config and adjust the
plugin list directly - it is just a list.
