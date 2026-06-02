---
title: About
---
**Off the Shelf** is the pyssg example for *theme customization*. It runs on the
`blog` preset but renders through a local layout under `layout/` -- an ejected
copy of the built-in `blog` theme with edited templates and a rebranded
stylesheet, plus a few options overridden from `pyssg.config.py`.

Look at three files to see how it fits together:

- `pyssg.config.py` -- selects `layout="layout"` and overrides `config.theme`.
- `layout/layout.toml` -- declares the theme `[options]` and their defaults.
- `layout/templates/base.html.j2` -- reads those options as `theme.<key>`.

To build it yourself:

```bash
pyssg --site examples/custom build
pyssg --site examples/custom serve
```
