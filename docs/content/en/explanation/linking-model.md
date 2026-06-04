---
title: The linking model
nav_title: The linking model
order: 5
---

# The linking model

PySSG treats links as first-class data, not just text in the output. That is what
makes wikilinks, transclusion, backlinks, and safe internal links work together.

## Internal Markdown links

A normal Markdown link to a local `.md` file is rewritten to the target page's
resolved URL, and a reverse `LINK` connection is recorded so backlinks work:

```markdown
See [getting started](getting-started.md).
```

Resolution happens during `evaluate_collections`, after every document is parsed
and every page URL is known. The rewrite always starts from the document's
pre-resolution HTML, so if a target is moved or renamed, the link updates on the
next finalize - even though the *linking* document was not itself re-edited. The
rewritten content is re-hashed, which is precisely what makes the render sweep
re-render a page whose link targets changed (keeping incremental == full).

## Wikilinks

The `wikilink` plugin adds Obsidian-style `[[...]]` links, resolved by target
title or filename:

```markdown
Read about [[Core concepts]] next.
```

Wikilink runs early in the `finalize_content` waterfall (stage 100), before plain
internal link resolution (stage 200), so by the time other plugins see the HTML,
wikilinks are already ordinary hrefs.

## Transclusion

`![[...]]` *embeds* another document's finalized content into the current page,
rather than just linking to it:

```markdown
![[shared/disclaimer]]
```

Transclusion runs in `expand_content`, after `finalize_content`, because it needs
the embedded document's *finalized* HTML (links already resolved) to splice in.

## Backlinks

Because every resolved link is stored as a reverse edge in the graph, PySSG can
show, on any page, which other pages link to it - with no extra configuration. The
backlink list is derived from the same `LINK` connections the resolver records, so
it is always consistent with the actual links in your content.

## Broken-link detection

Since links are resolved against the real graph of documents, a link whose target
does not exist is detectable rather than silently producing a dead href. This is
the other half of treating links as data: you find out at build time, not when a
reader clicks.

## External links

Links with a URL scheme (`http:`, `mailto:`, ...) are left alone by the internal
resolver. The optional `external_links` contrib plugin can rewrite off-site
anchors to open in a new tab with `rel="noopener noreferrer"`; it taps
`finalize_content` at stage 300, after wikilink and internal resolution, so it
only ever sees final hrefs.
