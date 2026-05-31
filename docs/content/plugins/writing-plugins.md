---
title: Writing plugins
order: 3
---

# Writing plugins

A plugin is any object with an `apply(builder)` method. Inside it, tap the hooks
you care about.

## A minimal plugin

This plugin adds a reading-time estimate to every page's metadata:

```python
from pyssg.builder import Builder
from pyssg.build import Build
from pyssg.models import Source


class ReadingTime:
    def __init__(self, wpm: int = 200) -> None:
        self._wpm = wpm

    def apply(self, builder: Builder) -> None:
        builder.hooks.parse.tap("ReadingTime", self._estimate)

    def _estimate(self, source: Source, build: Build) -> None:
        words = len(source.body.split())
        source.meta["reading_time"] = max(1, round(words / self._wpm))
```

Use it like any built-in plugin:

```python
plugins = [..., ReadingTime(wpm=180), ...]
```

And read it in a template:

```html
<span>{{ page.reading_time }} min read</span>
```

## Choosing a hook

| You want to... | Tap |
|----------------|-----|
| Discover or read source files | `discover`, `load` |
| Parse or annotate a single page | `parse` |
| Build site-wide data (nav, groups) | `collect` |
| Transform the body content | `transform` (waterfall) |
| Produce output from a page | `render` |
| Create derived files (rss, sitemap) | `generate` |
| Post-process all outputs | `optimize` |
| Write to disk | `emit` |
| Report after writing | `after_emit` |

## Conventions

- **Order with `stage`.** If your plugin must run before or after another on the
  same hook, set its `stage`. Lower runs first.
- **Lazy-import heavy dependencies.** Import third party libraries inside the
  method that uses them, not at module top level, so the plugin can be installed
  and inspected without the dependency present.
- **Reuse the content model.** Read and write `build.meta["collections"]`,
  `["menus"]` and `["site"]` (see `pyssg.content`) instead of inventing your
  own keys, so your plugin composes with the built-ins.
- **Mark synthetic pages.** If you append a generated `Source` during `collect`,
  set `source.meta["generated"] = True` so other plugins can tell it apart from
  real files.

## Waterfall plugins

For `transform`, return the (possibly modified) value so the next tap can
continue the pipeline:

```python
def apply(self, builder: Builder) -> None:
    builder.hooks.transform.tap("Anchors", self._add_anchors, stage=10)

def _add_anchors(self, source: Source, build: Build) -> Source:
    source.content = inject_heading_anchors(source.content)
    return source
```
