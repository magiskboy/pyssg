---
title: Giving a preset a face of its own
date: "2024-06-01"
tags: [theming, design]
---
Presets get you a working site in one line, but every site eventually wants its
own look. This blog is the `blog` preset with a **customized theme** bolted on,
and the whole change took two moves.

## 1. Eject the theme

The built-in themes live inside the pyssg package. To edit one, copy it into the
site first:

```bash
pyssg --site examples/custom eject-layout --theme blog --to layout
```

That writes an editable copy under `layout/` -- templates, CSS, and the i18n
strings. Point the config at it with `layout="layout"` and you are now serving
your own copy.

## 2. Edit templates and CSS

From there it is ordinary front-end work: a coloured header band, a tagline, a
restyled post list. See [[Theme options vs. editing templates]] for the lighter
alternative when all you want to change is a colour.
