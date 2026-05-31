---
title: Getting started
order: 1
---

# Getting started

Every page is a Markdown file with a small YAML frontmatter block:

```markdown
---
title: My page
order: 2
---

# My page

Content goes here.
```

The `order` key controls the position in the sidebar. The first heading becomes
the page title in the body; `title` is used for navigation and the HTML title.

Edit, add or delete files under `content/`, then rebuild with `pyssg build` or
keep `pyssg serve` running for live reload.
