---
title: Lookup cascade
order: 3
---

# Lookup cascade

Rather than making every page declare which template to use, pyssg resolves a
template automatically from the page's type, section and kind - the same idea as
Hugo's template lookup. Drop a `blog/single.html` into your layouts and every
blog post uses it, no frontmatter required.

## The order

For each page the plugin tries these names in order and uses the first that
exists:

```text
1. <frontmatter layout>        explicit override, always wins
2. <type>/<kind>.html          e.g. blog/single.html
3. <section>/<kind>.html       e.g. <top folder>/list.html
4. _default/<kind>.html        e.g. _default/single.html
5. <kind>.html                 e.g. list.html
6. <default_layout>            final fallback (default.html)
```

## The variables

- **`kind`** is `list` for generated listing pages (tag pages, blog indexes) and
  `single` for everything else. pyssg sets this from the page's `generated`
  flag, so you do not manage it by hand.
- **`type`** comes from frontmatter `type`. Use it to give a group of pages a
  distinct template regardless of where they live: `type: tutorial` ->
  `tutorial/single.html`.
- **`section`** is the top-level folder of the source path. A file at
  `blog/hello.md` has section `blog`.

## Examples

| Page | Resolved template (first that exists) |
|------|---------------------------------------|
| `blog/hello.md` | `blog/single.html` -> `_default/single.html` -> `default.html` |
| `blog/hello.md` with `type: featured` | `featured/single.html` -> `blog/single.html` -> ... |
| a generated tag page in `tags/` | `tags/list.html` -> `_default/list.html` -> ... |
| `about.md` (root) | `_default/single.html` -> `single.html` -> `default.html` |
| any page with `layout: special.html` | `special.html` first |

## Why it matters

The cascade is what turns a folder of layouts into a reusable *theme*. A page
only needs `layout` for genuine one-offs; the common case - "all posts look like
this, all list pages look like that" - is expressed once in
`_default/single.html` and `_default/list.html`. This site declares no `layout`
in any content file; it is entirely cascade-driven.
