"""Light, non-flaky checks for ``FsWatcher`` construction.

We deliberately avoid real-filesystem event-timing assertions (inherently
flaky). We only assert the structural no-polling guarantee and constructor
validation; the debounce/coalesce behaviour itself is covered purely in
``test_watch_coalesce.py``.
"""

from __future__ import annotations

import unittest

from pyssg.watch import FsWatcher


class FsWatcherTest(unittest.TestCase):
    def test_constructed_observer_is_not_polling(self) -> None:
        watcher = FsWatcher(roots=[], ignore=[])
        try:
            self.assertNotEqual(watcher.observer_name, "PollingObserver")
        finally:
            watcher.stop()

    def test_rejects_non_positive_debounce(self) -> None:
        with self.assertRaisesRegex(ValueError, "debounce_ms must be positive"):
            FsWatcher(roots=[], ignore=[], debounce_ms=0)

    def test_stop_is_idempotent_before_run(self) -> None:
        watcher = FsWatcher(roots=[], ignore=[])
        watcher.stop()
        watcher.stop()
