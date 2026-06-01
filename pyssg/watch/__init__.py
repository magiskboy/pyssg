"""Filesystem watch mode for pyssg.

Public surface:

- :class:`FsEvent` and :func:`coalesce` -- the neutral event type and its pure
  debounce merge;
- :class:`FsWatcher` -- the native, event-driven watcher;
- :func:`is_ignored` -- the pure ignore-glob helper.

This package is the only place allowed to import ``watchdog``;
everything it exposes upward is backend-neutral.
"""

from __future__ import annotations

from pyssg.watch.events import FsEvent, coalesce
from pyssg.watch.ignore import ALWAYS_IGNORE, is_ignored
from pyssg.watch.watcher import FsWatcher

__all__ = ["ALWAYS_IGNORE", "FsEvent", "FsWatcher", "coalesce", "is_ignored"]
