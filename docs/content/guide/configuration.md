---
title: Configuration
order: 2
---

# Configuration

pyssg is configured with a Python file - `pyssg.config.py` by default - that
exposes a `config()` function returning a `Config` object. Using Python (rather
than YAML or TOML) means you can pass plugin instances directly and use any
logic you like, exactly like `webpack.config.js`.

## The `config()` function

```python
from pyssg.config import Config
from pyssg_cli.presets import blog


def config() -> Config:
    return Config(
        src="content",
        out="public",
        options={"title": "My Blog", "base_url": "https://example.com"},
        plugins=blog(page_size=10),
    )
```

## The `Config` object

| Field | Type | Description |
|-------|------|-------------|
| `src` | path | Directory containing Markdown sources. |
| `out` | path | Directory the built site is written to. |
| `plugins` | list | Plugin instances, applied in order. |
| `options` | dict | Site-wide values exposed to templates as `site`. |

`src` and `out` accept strings or `Path` objects.

## Site options

Anything you put in `options` is available in templates as the `site` object:

```python
Config(..., options={"title": "Docs", "author": "Jane"})
```

```html
<title>{{ site.title }}</title>
<meta name="author" content="{{ site.author }}">
```

## Choosing plugins

You can use a [preset](/plugins/presets/) or assemble plugins by hand. The order
matters: plugins run in the order listed, and within a lifecycle hook the order
is refined by each plugin's *stage*. See [Lifecycle](/architecture/lifecycle/)
for the full picture.

```python
from pyssg_plugins import (
    ReadFile, Frontmatter, Markdown, Template, WriteFile,
)

def config() -> Config:
    return Config(
        src="content",
        out="public",
        plugins=[
            ReadFile(),
            Frontmatter(),
            Markdown(),
            Template(directory="layouts"),
            WriteFile(clean=True),
        ],
    )
```
