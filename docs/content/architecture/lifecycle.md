---
title: Lifecycle
order: 2
---

# Lifecycle

A build runs as a series of **phased passes**: each pass sweeps the entire set
of sources before the next begins. This mirrors how webpack builds all modules
before sealing, and it is what lets a plugin see the whole site - essential for
navigation, collections and derived pages.

```text
initialize                       (after every plugin is applied)
before_run
  discover                       (collect Sources)
  load       (each source)       (read raw content)        [bail]
  parse      (each source)       (split frontmatter/body)
  collect    (whole build)       (build site-wide context -> build.meta)
  transform  (each source)       (body -> content)         [waterfall]
  render     (each source)       (emit Output; sees whole site)
  generate   (whole build)       (derived pages: rss, extra files)
  optimize   (whole build)       (minify, optimize)        [stage ordering]
  emit       (whole build)       (write to disk)
  after_emit (whole build)       (sitemap, graph, report)
done | failed
```

## Why phased, not per-source

If each source were processed end-to-end in isolation, a page could not know
about other pages while rendering - so navigation, "related posts" or tag
indexes would be impossible. By finishing `parse` for *all* sources before
`collect` runs, plugins can build a complete picture of the site first.

## The two extension points for whole-site work

- **`collect`** runs *before* `render`. Read-only with respect to output: it
  assembles site-wide context into `build.meta` (collections, navigation) so
  every page can use it. Tier-2 plugins that create synthetic pages (like
  listings) also append their `Source` objects here, so those pages flow
  naturally through `transform` and `render`.
- **`generate`** runs *after* `render`. It synthesizes `Output` files directly -
  things that never pass through a template, like `sitemap.xml` or an RSS feed.

## `build.meta`

`build.meta` is a shared context bag (a `dict`). The `collect` pass writes to
it; `render`, `generate` and templates read from it. Tier-2 plugins agree on a
small set of keys - `site`, `collections`, `menus` - which is what keeps the
ecosystem from fragmenting.

See [Hooks](/architecture/hooks/) for how ordering within a pass works.
