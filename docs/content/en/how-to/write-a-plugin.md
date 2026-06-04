---
title: Write a custom plugin
nav_title: Write a plugin
order: 5
---

# Write a custom plugin

**Goal:** add your own behaviour by tapping a hook, the same way the built-in
plugins do.

For the bigger picture of how plugins fit together, read
[The plugin pipeline](../explanation/plugin-pipeline.md) first. This guide is the
practical recipe.

To start from a working skeleton instead of an empty file, run
`pyssg new plugin <name>`: it scaffolds `plugins/<name>.py` with the class, the
factory, and the hook wiring already in place, ready to customize.

## The plugin shape

A plugin is any object with a `name` attribute and an `apply(builder)` method.
Inside `apply`, you tap one or more hooks. The convention is to ship a small
factory function that returns an instance, so it reads nicely in a config file.

```python
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pyssg.core.builder import Builder


class UppercaseTitles:
    """Force every page title to upper case (a tiny example)."""

    name = "uppercase_titles"

    def apply(self, builder: Builder) -> None:
        @builder.hooks.this_compilation.tap(self.name)
        def _(build: object) -> None:
            # Tap a per-build hook here; see the hook reference for the full set.
            ...


def uppercase_titles() -> UppercaseTitles:
    return UppercaseTitles()
```

## Where to tap

Hooks live in two scopes:

- **Builder hooks** (`builder.hooks.*`) - the long-lived compiler. Tap
  `this_compilation` to reach into each build, or `make` to inject synthetic
  nodes into the graph (this is how `apidoc` adds its reference pages).
- **Build hooks** (`build.hooks.*`) - one compilation. These are the per-document
  and per-page taps: `parse`, `resolve`, `finalize_content`, `route`,
  `render_page`, and more.

The full list with signatures is in the
[plugins & hooks reference](../reference/plugins.md).

## Ordering taps

Taps declare *relative* order with a coarse `stage` integer plus `before` /
`after` name constraints. For example, `external_links` taps `finalize_content`
at `stage=300` so it runs after wikilink resolution (100) and internal link
resolution (200) and therefore sees the final hrefs:

```python
@builder.hooks... .tap(self.name, stage=300)
def _(html: str) -> str:
    ...
```

Before every call the taps are topologically sorted; a constraint cycle raises
`HookOrderError`.

## The rules every plugin must follow

These are not optional - they are what makes PySSG's build guarantees hold:

1. **Be pure with respect to declared inputs.** No global mutable state, and no
   direct `datetime.now()` / `time` / `random`. Building twice must be
   byte-identical.
2. **Declare facts; let the engine own the algorithms.** Plugins do not propagate
   dirtiness or manage the cache themselves.
3. **`route` returning `""` means "no page".** A `route` tap that returns the
   empty string suppresses output for that document (this is how `i18n` drops
   files outside any locale directory).
4. **Core stays stdlib-only.** Third-party imports belong in the periphery
   (`pyssg/plugins/` or `pyssg/contrib/`), never in `pyssg/core/`.

## Use it

Import and add your plugin in `pyssg.config.py`:

```python
from __future__ import annotations

from pyssg.presets import docs
from mypackage.plugins import uppercase_titles

config = docs(
    site={"title": "My Docs"},
    extra_plugins=[uppercase_titles()],
)
```

`extra_plugins` are appended after the preset's defaults, so they run last.
