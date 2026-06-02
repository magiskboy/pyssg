---
title: Theme options vs. editing templates
date: "2024-06-08"
tags: [theming, config]
---
Not every customization needs a code change. A layout can expose **theme
options** -- named knobs with defaults -- and a site can flip them from its
config without touching a single template.

## Declaring options in the layout

The layout declares defaults in `layout.toml`:

```toml
[options]
accent = "#0b66c3"
tagline = "A custom-themed pyssg blog"
footer_note = "Built with pyssg."
show_reading_time = true
```

Templates read them as `theme.<key>`:

```jinja
<style>:root { --accent: {{ theme.accent }}; }</style>
<p class="site-tagline">{{ theme.tagline }}</p>
```

## Overriding them from the site config

The site overrides any subset in `pyssg.config.py`; it is a shallow per-key
merge over the layout defaults:

```python
config.theme = {
    "accent": "#7a3cff",
    "tagline": "Same engine, a theme of my own",
}
```

The accent and tagline you see on this site come from that override; the footer
note and reading-time flag still come from the layout defaults. Reach for
template edits (see [[Giving a preset a face of its own]]) only when an option
cannot express the change.
