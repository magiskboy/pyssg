---
title: Add internationalization (i18n)
nav_title: Internationalization
order: 2
---

# Add internationalization (i18n)

**Goal:** serve the same site in several languages, with a language switcher and
correct `hreflang` tags, without ever linking to a missing translation.

## 1. Add the plugin

The `i18n` plugin is built in. Append it to a preset with `extra_plugins`:

```python
from __future__ import annotations

from pyssg.presets import docs
from pyssg.plugins import i18n

config = docs(
    site={"title": "My Docs"},
    base_url="https://example.com",
    extra_plugins=[i18n(default_locale="en", locales=["en", "vi"])],
)
```

## 2. Lay content out one directory per locale

The locale is the **top-level directory** under `content/` - there is no
frontmatter override:

```
content/
  en/index.md          ->  /            (default locale, served at the root)
  en/guide/intro.md    ->  /guide/intro/
  vi/index.md          ->  /vi/
  vi/guide/intro.md    ->  /vi/guide/intro/
```

The rules are deliberately simple:

- The **default locale** is served at the site root (its prefix is stripped);
  every other locale keeps its `/<locale>/` prefix.
- Content **outside** any locale directory produces no page.
- A page is emitted only for locales that **actually have the file** - there is no
  content fallback, so a language switcher never links to a missing translation.

## 3. Use the template variables

The plugin gives every page three extra template variables:

- `lang` - the current page's locale.
- `translations` - the same page in other locales, each `{lang, url, title}`.
- `languages` - all configured locales.

The built-in `docs` and `blog` themes already use them to render `<html lang>`,
`hreflang` alternates, and a header switcher, so with the layout above you get a
working bilingual site out of the box.

## 4. Translate the UI strings

Steps 1-3 localise your *content*. The labels baked into the theme - "Tags",
"Previous", "On this page" - are translated separately, through **string tables**.

### Where the tables live

Two optional files per locale are merged, the site's overriding the theme's per
key:

```text
<layout>/i18n/en.toml    # theme defaults (the built-in themes ship these)
<layout>/i18n/vi.toml
i18n/en.toml             # site overrides, relative to the site root
i18n/vi.toml
```

The tables are loaded independently of the routing plugin, so even a
single-language site can use them.

### Write a table

Group keys with TOML tables and address them with dots (`nav.home`). Values may
contain `{placeholders}`:

```toml
# i18n/vi.toml
[nav]
home = "Trang chủ"
tags = "Thẻ"

[post]
reading_time = "{minutes} phút đọc"
```

### Call `t()` in a template

The render step injects a `t(key, **vars)` function into every template:

```jinja
<a href="/">{{ t("nav.home") }}</a>
<span>{{ t("post.reading_time", minutes=reading_time) }}</span>
```

`t()` resolves the key in the current page's locale, falls back to the default
locale, and finally returns the key itself - so an untranslated label shows its
key (easy to spot) instead of breaking the page. The built-in `blog` and `docs`
themes already route every label through `t()` and ship `en`/`vi` tables, so
translating them is just a matter of adding or overriding a `.toml` file.

See the [i18n reference](/reference/i18n/) for the exact lookup and merge rules.

## 5. Build and check

```bash
pyssg --site my-site build
```

English pages appear at the root and Vietnamese pages under `/vi/`. See
`examples/docs/` in the repository for a complete bilingual sample.
