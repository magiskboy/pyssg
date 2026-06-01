"""Dependency boundary invariant.

``pyssg.core`` MUST import stdlib only. This test parses the AST of every module
under ``pyssg/core`` and fails if any module imports a non-stdlib, non-pyssg
top-level package. It also implicitly enforces the rule that
``watchdog`` (and any other third-party watcher) never leaks into core.
"""

from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path

CORE_DIR = Path(__file__).resolve().parents[2] / "pyssg" / "core"

# Always-allowed top-level names: the stdlib, __future__, and pyssg itself.
_ALLOWED: frozenset[str] = frozenset(sys.stdlib_module_names) | {"__future__", "pyssg"}


def _imported_top_level_modules(tree: ast.AST) -> set[str]:
    """Top-level package names imported by absolute imports in ``tree``.

    Relative imports (``from . import x``) have ``level > 0`` and stay internal,
    so they are ignored.
    """
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".", 1)[0])
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module is not None:
            names.add(node.module.split(".", 1)[0])
    return names


def _core_modules() -> list[Path]:
    assert CORE_DIR.is_dir(), f"core package not found at {CORE_DIR}"
    return sorted(CORE_DIR.rglob("*.py"))


class CoreBoundaryTest(unittest.TestCase):
    def test_core_imports_stdlib_only(self) -> None:
        offenders: dict[str, set[str]] = {}
        for path in _core_modules():
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            bad = _imported_top_level_modules(tree) - _ALLOWED
            if bad:
                offenders[str(path.relative_to(CORE_DIR.parent.parent))] = bad
        self.assertFalse(
            offenders,
            "pyssg.core must import stdlib only; third-party imports: "
            + ", ".join(f"{mod} -> {sorted(mods)}" for mod, mods in sorted(offenders.items())),
        )

    def test_core_never_imports_watchdog(self) -> None:
        """watchdog stays in pyssg/watch only.

        Checks actual import statements (not prose), so a docstring may still mention
        the watcher. This is subsumed by the stdlib-only test above but kept explicit.
        """
        for path in _core_modules():
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            self.assertNotIn(
                "watchdog",
                _imported_top_level_modules(tree),
                f"{path} imports watchdog; the watcher lib must stay in pyssg/watch",
            )
