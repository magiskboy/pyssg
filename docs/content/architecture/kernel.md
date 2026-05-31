---
title: The kernel
order: 1
---

# The kernel

The kernel is deliberately small and has **zero third party dependencies** - it
is pure standard library. Everything it contains falls into one of a handful of
modules.

| Module | Responsibility |
|--------|----------------|
| `hooks.py` | `SyncHook`, `SyncBailHook`, `SyncWaterfallHook`. |
| `builder.py` | `Builder` (lifecycle orchestrator) and `BuilderHooks`. |
| `build.py` | `Build`, the state of one run. |
| `models.py` | `Source` and `Output`, neutral data bags. |
| `plugin.py` | The `Plugin` protocol. |
| `config.py` | `Config` and loading of `pyssg.config.py`. |
| `cli.py` | The `pyssg build` entry point. |

## Dependency-free by design

The rule is simple: **the kernel uses only the standard library; plugins may use
whatever they need.** This resolves the tension between "keep dependencies
minimal" and "we need a real Markdown parser". The kernel stays clean, while a
plugin like `Markdown` is free to depend on `python-markdown`, imported lazily
so the cost is only paid when the plugin is actually used.

## The plugin protocol

A plugin is any object with an `apply` method:

```python
class Plugin(Protocol):
    def apply(self, builder: Builder) -> None: ...
```

Inside `apply`, the plugin taps the hooks it cares about. That is the entire
contract between the kernel and its extensions.

## The Builder

The `Builder` is created from a `Config`. On construction it applies every
plugin (calling `apply`), then fires the `initialize` hook. Calling `run()`
executes one full [lifecycle](/architecture/lifecycle/) and returns the
resulting `Build`.

Because the builder is a long-lived object, it is the natural home for a future
watch mode that rebuilds on file changes - without changing any plugin.
