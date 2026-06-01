"""Unit tests: Registry."""

from __future__ import annotations

import unittest

from pyssg.core.registry import Registry


class RegistryTest(unittest.TestCase):
    def test_for_creates_slot_once(self) -> None:
        created: list[str] = []

        def factory(key: str) -> list[str]:
            created.append(key)
            return [key]

        reg: Registry[str, list[str]] = Registry(factory)
        first = reg.for_("md")
        second = reg.for_("md")
        self.assertIs(first, second)  # same slot reused
        self.assertEqual(created, ["md"])  # factory ran exactly once

    def test_distinct_keys_get_distinct_slots(self) -> None:
        reg: Registry[str, list[str]] = Registry(lambda key: [key])
        a = reg.for_("a")
        b = reg.for_("b")
        self.assertIsNot(a, b)
        self.assertEqual(set(reg.keys()), {"a", "b"})
        self.assertIn(("a", ["a"]), reg.items())
        self.assertIn("a", reg)
        self.assertEqual(len(reg), 2)
