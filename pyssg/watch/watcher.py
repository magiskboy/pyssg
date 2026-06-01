"""Native, event-driven filesystem watcher.

This is the ONLY module allowed to import ``watchdog``. It wraps
``watchdog.observers.Observer`` (the OS-native backend: inotify/FSEvents/
ReadDirectoryChangesW/kqueue) and normalises raw watchdog events into neutral
:class:`~pyssg.watch.events.FsEvent` instances.

Polling is forbidden: the constructor refuses a
``PollingObserver`` and, if the native backend is unavailable, fails loudly
instead of silently degrading. Debouncing is a timer driven by the event stream
(a :class:`threading.Timer` reset on each event), never a periodic FS scan.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from pyssg.watch.events import FsEvent, coalesce
from pyssg.watch.ignore import is_ignored

if TYPE_CHECKING:
    from watchdog.events import FileSystemEvent

__all__ = ["FsWatcher"]


def _decode(raw: str | bytes) -> str:
    """Normalise a watchdog path (``str`` or ``bytes``) to ``str``."""
    if isinstance(raw, bytes):
        return raw.decode("utf-8", "surrogateescape")
    return raw


class _Sink(FileSystemEventHandler):
    """Maps raw watchdog events to neutral :class:`FsEvent`.

    Directory events are skipped here: the recursive observer already reports
    the contained file events, and the incremental engine works at file
    granularity (dir recursion is handled at the engine layer). Events whose
    path is ignored are dropped before they reach the debounce buffer.
    """

    def __init__(self, push: Callable[[FsEvent], None], ignore: list[str]) -> None:
        self._push = push
        self._ignore = ignore

    def _emit(self, event: FsEvent) -> None:
        if is_ignored(event.path, self._ignore):
            return
        if event.kind == "move" and event.dest is not None and is_ignored(event.dest, self._ignore):
            # A move whose destination is ignored is, from the watched tree's
            # point of view, a deletion of the source.
            self._push(FsEvent("delete", event.path))
            return
        self._push(event)

    def on_created(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        self._emit(FsEvent("add", _decode(event.src_path)))

    def on_modified(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        self._emit(FsEvent("modify", _decode(event.src_path)))

    def on_deleted(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        self._emit(FsEvent("delete", _decode(event.src_path)))

    def on_moved(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        self._emit(FsEvent("move", _decode(event.src_path), _decode(event.dest_path)))


class FsWatcher:
    """Native event-driven watcher with stream-debounced batching.

    Args:
        roots: Directories to watch recursively (content/layout/config dirs).
        ignore: Extra ignore globs from config; combined with the always-on
            editor/VCS/output noise (see :mod:`pyssg.watch.ignore`).
        debounce_ms: Quiet period in milliseconds; a burst is flushed once no
            new event has arrived for this long. Must be positive.

    Raises:
        RuntimeError: If the resolved observer is a ``PollingObserver`` or the
            native backend is otherwise unavailable.
    """

    def __init__(self, roots: list[str], ignore: list[str], debounce_ms: int = 80) -> None:
        if debounce_ms <= 0:
            raise ValueError(f"debounce_ms must be positive, got {debounce_ms!r}")

        # ``Observer`` is a factory that selects the OS-native backend. If the
        # native backend cannot be built, watchdog raises here -- we let that
        # propagate rather than fall back to polling.
        self._obs: Any = Observer()
        observer_name = type(self._obs).__name__
        if observer_name == "PollingObserver":
            raise RuntimeError(
                "watchdog resolved a PollingObserver; polling is forbidden. "
                "The OS-native backend (inotify/FSEvents/ReadDirectoryChangesW/kqueue) "
                "must be available -- no silent polling fallback."
            )

        self._roots = list(roots)
        self._ignore = list(ignore)
        self._debounce_s = debounce_ms / 1000.0

        # Debounce state, guarded by ``_lock`` because the watchdog observer
        # thread feeds events while the timer thread flushes them.
        self._lock = threading.Lock()
        self._buffer: list[FsEvent] = []
        self._timer: threading.Timer | None = None
        self._on_batch: Callable[[list[FsEvent]], None] | None = None
        self._started = False

    @property
    def observer_name(self) -> str:
        """Class name of the resolved observer (for regression assertions)."""
        return type(self._obs).__name__

    def _push(self, event: FsEvent) -> None:
        """Buffer one event and (re)arm the debounce timer.

        Called on the observer thread. Resetting the timer on every event means
        the batch flushes only after the stream goes quiet -- a timer on the
        event stream, never a periodic poll.
        """
        with self._lock:
            self._buffer.append(event)
            if self._timer is not None:
                self._timer.cancel()
            self._timer = threading.Timer(self._debounce_s, self._flush)
            self._timer.daemon = True
            self._timer.start()

    def _flush(self) -> None:
        """Coalesce the buffered burst and hand it to ``on_batch``."""
        with self._lock:
            batch = self._buffer
            self._buffer = []
            self._timer = None
            on_batch = self._on_batch
        if on_batch is not None and batch:
            on_batch(coalesce(batch))

    def run(self, on_batch: Callable[[list[FsEvent]], None]) -> None:
        """Start watching; flush coalesced bursts to ``on_batch``.

        The observer runs on its own thread. This call only schedules and starts
        it; it returns immediately so the caller owns the main thread. Use
        :meth:`stop` to tear down.

        Args:
            on_batch: Invoked once per quiet burst with the coalesced events.

        Raises:
            RuntimeError: If called more than once on the same watcher.
        """
        if self._started:
            raise RuntimeError("FsWatcher.run() already called; create a new watcher")
        self._started = True
        self._on_batch = on_batch

        sink = _Sink(self._push, self._ignore)
        for root in self._roots:
            self._obs.schedule(sink, root, recursive=True)
        self._obs.start()

    def stop(self) -> None:
        """Stop the observer and cancel any pending debounce timer.

        Safe to call even if :meth:`run` was never called or already stopped.
        """
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None
        if self._started:
            self._obs.stop()
            self._obs.join()
            self._started = False
