---
title: Inheritance
order: 1
---

# Inheritance

Template inheritance lets you define a page skeleton once and have every layout
fill in the parts that change. pyssg uses Jinja2's native `{% extends %}` and
`{% block %}` - there is nothing extra to learn or enable.

## A base skeleton

Put the shared HTML in a base template with named blocks for the variable parts:

```html
<!-- layouts/base.html -->
<!doctype html>
<html lang="en">
<head>
  <title>{% block title %}{{ site.title }}{% endblock %}</title>
  <link rel="stylesheet" href="/assets/style.css">
</head>
<body>
  <main>{% block main %}{% endblock %}</main>
</body>
</html>
```

## Extending it

A concrete layout extends the base and overrides the blocks:

```html
<!-- layouts/_default/single.html -->
{% extends "base.html" %}

{% block main %}
  <article>{{ content }}</article>
{% endblock %}
```

Anything not overridden falls through to the base's default. You can nest
inheritance as deep as you like - a section layout can extend a base, which
extends a root skeleton.

## Convention

The reference layout used by the `docs()` preset is organised like this:

```text
layouts/
  base.html              # the skeleton every page shares
  _default/
    single.html          # extends base.html - normal pages
    list.html            # extends base.html - listing pages
  partials/              # reusable snippets (see Partials)
```

See the [lookup cascade](/templating/lookup-cascade/) for how `single.html` and
`list.html` get selected automatically.
