---
title: Hello, world
date: 2026-01-01
tags: [meta, pyssg]
summary: The first post of this blog, and how the blog theme is wired together.
---

This is the first post. It lives at `content/blog/hello-world.md` and is listed
automatically on the [Blog](/blog/) index, sorted by `date` (newest first).

## Frontmatter

Every post starts with a small YAML block:

```yaml
---
title: Hello, world
date: 2026-01-01
tags: [meta, pyssg]
summary: A one-line teaser shown on the index.
---
```

- `date` controls ordering and shows next to the title.
- `tags` generate per-tag pages under `/tags/<name>/`.
- `summary` is the teaser shown on the listing.

Write the rest of the post in Markdown below the frontmatter.
