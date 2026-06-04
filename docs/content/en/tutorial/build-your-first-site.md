---
title: Build your first site
nav_title: Build your first site
order: 1
---

# Build your first site

This tutorial walks you from an empty directory to a live, auto-reloading
documentation site. By the end you will have scaffolded a site, built it, served
it locally, and made a change that reloads in the browser.

It is a *lesson*, not a reference: follow the steps in order and you will reach a
working result. You do not need to understand every detail yet - the
[Explanation](../explanation/index.md) section covers the *why* later.

## Prerequisites

- **Python 3.13+** and **[uv](https://github.com/astral-sh/uv)** installed.
- PySSG available. The simplest way while you learn is to clone the repository
  and run everything through `uv run`:

  ```bash
  git clone https://github.com/magiskboy/pyssg && cd pyssg
  uv sync
  ```

  In your own project you would instead add it as a dependency:

  ```bash
  uv add git+https://github.com/magiskboy/pyssg
  ```

All commands below are written as `pyssg ...`. The `--site`
option selects the site directory; it defaults to the current directory.

## Step 1 - Scaffold a new site

A **preset** is a ready-made configuration that bundles the right plugins and a
default theme. Scaffold a documentation site with the `docs` preset:

```bash
pyssg --site my-site new site --preset docs
```

This creates three files:

```
my-site/
  pyssg.config.py                     # one-line configuration
  content/index.md                    # the home page
  content/guide/getting-started.md    # a sample page
```

Open `my-site/pyssg.config.py`. The entire configuration is one call:

```python
from __future__ import annotations

from pyssg.presets import docs

config = docs(
    site={"title": "My Docs"},
    base_url="https://example.com",
)
```

## Step 2 - Build the site

Render the content into the output directory (`dist/` by default):

```bash
pyssg --site my-site build
```

You should see something like `build: 3 pages written`. The HTML now lives under
`my-site/dist/`. Each page is written as a *pretty URL* - `content/guide/getting-started.md`
becomes `dist/guide/getting-started/index.html`, served at `/guide/getting-started/`.

## Step 3 - Serve with live reload

Instead of rebuilding by hand, run the dev server. It watches your files,
rebuilds only what changed, and refreshes the browser automatically:

```bash
pyssg --site my-site serve
```

Open the printed URL (by default <http://127.0.0.1:8000>). You will see your home
page with a sidebar listing the sample pages.

## Step 4 - Make a change and watch it reload

Leave `serve` running. In another terminal (or your editor), open
`my-site/content/index.md` and change the heading:

```markdown
---
title: Home
---
# Welcome to my docs

This is my first pyssg site.
```

Save the file. The terminal shows a quick incremental rebuild and the browser
reloads on its own - only the page you edited was re-rendered.

## Step 5 - Add a new page and link to it

Create `my-site/content/guide/concepts.md`:

```markdown
---
title: Core concepts
order: 2
---
# Core concepts

Back to [getting started](getting-started.md).
```

Save it. A new entry appears in the sidebar under **guide**, ordered by the
`order` frontmatter field. The link to `getting-started.md` is automatically
rewritten to the target page's URL - internal links are resolved by path, so they
keep working even if you move pages around later.

## What you built

You now have a working site with:

- a home page and a `guide/` section that became a sidebar group,
- incremental rebuilds with live reload,
- internal links that resolve themselves.

## Next steps

- Solve specific problems with the **[How-to guides](../how-to/index.md)** -
  for example [customize the theme](../how-to/customize-theme.md) or
  [add a second language](../how-to/internationalization.md).
- Look up exact options in the **[Reference](../reference/index.md)**.
- Understand how the build works in **[Explanation](../explanation/index.md)**.
