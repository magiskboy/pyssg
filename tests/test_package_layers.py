"""Enforce the layered package boundary.

The source is split into three import packages with a strict one-way
dependency, webpack-cli style:

    pyssg (kernel) <- pyssg_plugins (built-ins) <- pyssg_cli (CLI/presets)

This test parses every module with ``ast`` and fails if any module imports a
package from a higher layer. It is the contract that keeps the kernel free of
plugin dependencies and prevents the layers from re-fragmenting over time.
"""

from __future__ import annotations

import ast
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"

# Each package may import only itself and the packages below it.
FORBIDDEN: dict[str, frozenset[str]] = {
    "pyssg": frozenset({"pyssg_plugins", "pyssg_cli"}),
    "pyssg_plugins": frozenset({"pyssg_cli"}),
    "pyssg_cli": frozenset(),
}


def _imported_roots(tree: ast.Module) -> set[str]:
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(alias.name.split(".", 1)[0])
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".", 1)[0])
    return roots


class PackageLayerTest(unittest.TestCase):
    def test_no_upward_imports(self) -> None:
        violations: list[str] = []
        for package, forbidden in FORBIDDEN.items():
            for path in (SRC / package).rglob("*.py"):
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
                for root in _imported_roots(tree) & forbidden:
                    rel = path.relative_to(SRC)
                    violations.append(f"{rel} imports forbidden package '{root}'")
        self.assertEqual(violations, [], "\n".join(violations))


if __name__ == "__main__":
    unittest.main()
