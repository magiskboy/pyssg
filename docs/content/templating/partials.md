---
title: Partials
order: 2
---

# Partials

Partials are reusable template snippets - a header, a card, a pagination bar.
pyssg adds a `partial()` function, modelled on Hugo's, alongside Jinja2's native
`{% include %}` and macros.

## The `partial()` function

```html
{{ partial("partials/card.html", {"item": entry}) }}
```

`partial(name, context=None)`:

- renders the named template with an **explicit** context;
- automatically merges in `site`, `menus` and `collections`, so a partial can
  always reach site-wide data;
- returns safe markup, so the result is not double-escaped;
- accepts a name with or without the `.html` suffix.

This is the recommended way to build components, because the data a partial sees
is exactly what you pass it - no surprises from inherited scope.

## Example: a component with parameters

```html
<!-- layouts/partials/badge.html -->
<span class="badge badge-{{ kind }}">{{ label }}</span>
```

```html
{{ partial("partials/badge.html", {"label": "New", "kind": "info"}) }}
```

## Convention

Keep snippets under `layouts/partials/`. The reference site splits its chrome
into partials so each layout stays small:

```text
layouts/partials/
  topbar.html
  sidebar.html
  prevnext.html
  footer.html
  entry.html       # one item in a listing
```

A layout then reads almost like an outline:

```html
{% extends "base.html" %}
{% block main %}
  <article>{{ content }}</article>
  {{ partial("partials/prevnext.html", {"prev": page.prev, "next": page.next}) }}
{% endblock %}
```

## Native Jinja2 still works

If you prefer Jinja2's built-ins, they are available unchanged:

```html
{% include "partials/topbar.html" %}

{% from "partials/macros.html" import card %}
{{ card(entry) }}
```

Use `{% include %}` for static fragments, macros for parameterised components, or
`partial()` when you want Hugo-style explicit context with site data included.
