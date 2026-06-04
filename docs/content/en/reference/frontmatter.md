---
title: Frontmatter reference
nav_title: Frontmatter
order: 4
---

# Frontmatter reference

Each Markdown document may start with a YAML frontmatter block delimited by `---`.
The `frontmatter` plugin parses it into the document's metadata, which later
plugins read. The fields below are the ones PySSG's built-in plugins understand;
any other keys are kept and made available to templates.

```markdown
---
title: Getting Started
order: 2
tags: [intro, setup]
---
# Getting Started
...
```

## Fields read by built-in plugins

| Field | Type | Read by | Effect |
|---|---|---|---|
| `title` | `str` | nav, render, taxonomy | The page title (sidebar entry, `<title>`, breadcrumbs). |
| `nav_title` | `str` | nav | Overrides `title` in the navigation menu only. |
| `order` | `int` | nav | Sort order within a section; pages without `order` sort last, then by URL. |
| `date` | `str` | blog, rss | Publication date (used for ordering and feeds). |
| `tags` | `list[str]` | taxonomy | Generates `/tags/<tag>/` index pages. |
| `category` / `categories` | `str` / `list[str]` | taxonomy | Generates `/categories/<category>/` index pages. |
| `draft` | `bool` | (loader) | Marks a document as a draft. |
| `template` | `str` | render | Choose a specific layout template for this page. |
| `permalink` | `str` | permalink | Set an explicit output URL for this page. |
| `excerpt` | `str` | content_meta | Override the auto-generated excerpt. |
| `toc` | (derived) | content_meta | The table of contents / outline (computed, exposed to templates). |

## Computed metadata

Beyond what you write, the `content_meta` plugin derives and attaches:

- `word_count` and `reading_time`,
- `excerpt` (if not set explicitly),
- `toc` (the heading outline).

These are available to templates alongside the frontmatter fields.

## Notes

- The **locale is not a frontmatter field.** Under the `i18n` plugin the locale is
  the top-level content directory (`content/en/...`), by design - see
  [internationalization](../how-to/internationalization.md).
- Markdown is rendered with [Python-Markdown](https://python-markdown.github.io/)
  (extensions `fenced_code`, `tables`, `sane_lists`, `toc`), so **GFM-style pipe
  tables are supported**. Raw HTML also passes through untouched - which is how the
  `apidoc` plugin emits its parameter tables.
