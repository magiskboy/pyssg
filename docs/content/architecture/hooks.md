---
title: Hooks
order: 3
---

# Hooks

The hook system is pyssg's version of webpack's Tapable. It provides three
synchronous hook types - enough to express every SSG need.

## The three hook types

### SyncHook

Fires an event and calls every tap in order. Return values are ignored. Used for
side effects like writing files.

```python
builder.hooks.emit.tap("WriteFile", self._emit)
```

### SyncBailHook

Calls taps in order and stops at the first one returning a non-`None` value,
returning that value. Perfect for "which plugin handles this?" questions.

```python
# "Who can read this kind of file?" - first reader wins.
```

### SyncWaterfallHook

Threads a value through every tap: each tap's result becomes the next tap's
input. A tap returning `None` means "no change". This is the heart of content
transformation.

```python
builder.hooks.transform.tap("Markdown", self._render)
# Markdown -> HTML -> add anchors -> highlight code -> ...
```

## Ordering with `stage`

Every tap carries a `stage` (default `0`). Taps run in ascending stage order;
within the same stage, registration order is preserved. This is how plugins that
share a hook coordinate without knowing about each other.

```python
builder.hooks.transform.tap("base", fn, stage=0)
builder.hooks.transform.tap("wrap", fn, stage=10)   # runs after "base"
```

The tier-2 plugins use stage to order their work inside the single `collect`
pass: Permalink (`-200`) assigns URLs first, then Collections (`-100`) groups
pages, then Listing (`0`) builds list pages, then Navigation (`100`) builds
menus once every page (including synthetic ones) exists.

## Typing

Hooks are generic over their positional arguments using `TypeVarTuple`, giving
natural signatures:

```python
self.transform: SyncWaterfallHook[Source, Build]
self.render: SyncHook[Source, Build]
```
