"""Unit tests for the deploy target registry."""

from __future__ import annotations

import unittest

from pyssg.deploy import (
    DeployContext,
    DeployError,
    DeployResult,
    DeployTarget,
    get_target,
    list_targets,
    register,
)


class _StubTarget:
    """Minimal DeployTarget used to populate an isolated registry in tests."""

    def __init__(self, name: str) -> None:
        self.name = name

    def required_env(self) -> list[str]:
        return []

    def required_config_keys(self) -> list[str]:
        return []

    async def deploy(self, ctx: DeployContext) -> DeployResult:
        raise NotImplementedError


class RegistryTest(unittest.TestCase):
    def test_get_unknown_raises_with_available_list(self) -> None:
        targets: dict[str, DeployTarget] = {"a": _StubTarget("a"), "b": _StubTarget("b")}
        with self.assertRaises(DeployError) as ctx:
            get_target("c", targets=targets)
        self.assertIn("unknown deploy target: c", str(ctx.exception))
        self.assertIn("a, b", str(ctx.exception))

    def test_get_unknown_with_empty_registry(self) -> None:
        with self.assertRaisesRegex(DeployError, "available: \\(none\\)"):
            get_target("anything", targets={})

    def test_list_returns_sorted_names(self) -> None:
        targets: dict[str, DeployTarget] = {
            "zeta": _StubTarget("zeta"),
            "alpha": _StubTarget("alpha"),
        }
        self.assertEqual(list_targets(targets=targets), ["alpha", "zeta"])

    def test_register_then_lookup(self) -> None:
        """Mutates the module-level registry; clean up afterwards."""
        from pyssg.deploy import TARGETS

        target = _StubTarget("test-only-target")
        self.assertNotIn("test-only-target", TARGETS)
        register(target)
        try:
            self.assertIs(get_target("test-only-target"), target)
            self.assertIn("test-only-target", list_targets())
            # Double-register is a clear error.
            with self.assertRaisesRegex(DeployError, "already registered"):
                register(target)
        finally:
            del TARGETS["test-only-target"]


if __name__ == "__main__":
    unittest.main()
