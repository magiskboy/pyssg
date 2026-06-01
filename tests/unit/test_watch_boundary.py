"""Boundary lint for the watcher.

Two structural guarantees, enforced by parsing the AST of every module under
``pyssg/`` (so commented-out code or guard strings cannot trip the check):

1. ``watchdog`` is imported only inside ``pyssg/watch/``.
2. Nowhere in ``pyssg/`` is ``watchdog.observers.polling`` imported nor
   ``PollingObserver`` imported as a name (polling is banned).

A bare textual reference to ``PollingObserver`` (e.g. the watcher's guard error
message) is allowed; only actual ``import`` statements fail the test.
"""

from __future__ import annotations

import ast
import unittest
from pathlib import Path

PYSSG_DIR = Path(__file__).resolve().parents[2] / "pyssg"
WATCH_DIR = PYSSG_DIR / "watch"


def _all_modules() -> list[Path]:
    assert PYSSG_DIR.is_dir(), f"pyssg package not found at {PYSSG_DIR}"
    return sorted(PYSSG_DIR.rglob("*.py"))


def _imports_top_level(tree: ast.AST, name: str) -> bool:
    """Whether any absolute import in ``tree`` pulls in top-level ``name``."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(alias.name.split(".", 1)[0] == name for alias in node.names):
                return True
        elif (
            isinstance(node, ast.ImportFrom)
            and node.level == 0
            and node.module is not None
            and node.module.split(".", 1)[0] == name
        ):
            return True
    return False


def _imports_polling(tree: ast.AST) -> bool:
    """Whether ``tree`` imports the polling backend or ``PollingObserver``.

    A bare ``import watchdog.observers`` is fine; only the ``polling`` submodule
    and importing the ``PollingObserver`` name are banned.
    """
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(alias.name == "watchdog.observers.polling" for alias in node.names):
                return True
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            if node.module == "watchdog.observers.polling":
                return True
            if node.module in ("watchdog.observers", "watchdog") and any(
                alias.name == "PollingObserver" for alias in node.names
            ):
                return True
    return False


class WatchBoundaryTest(unittest.TestCase):
    def test_watchdog_only_imported_in_watch_package(self) -> None:
        offenders: list[str] = []
        for path in _all_modules():
            if WATCH_DIR in path.parents or path == WATCH_DIR:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            if _imports_top_level(tree, "watchdog"):
                offenders.append(str(path.relative_to(PYSSG_DIR.parent)))
        self.assertFalse(
            offenders,
            f"watchdog must be imported only inside pyssg/watch; offending modules: {offenders}",
        )

    def test_no_polling_observer_anywhere(self) -> None:
        offenders: list[str] = []
        for path in _all_modules():
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            if _imports_polling(tree):
                offenders.append(str(path.relative_to(PYSSG_DIR.parent)))
        self.assertFalse(
            offenders,
            "PollingObserver / watchdog.observers.polling is forbidden; "
            f"offending modules: {offenders}",
        )
