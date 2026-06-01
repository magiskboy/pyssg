"""M0 acceptance: the package imports and exposes a version."""

from __future__ import annotations

import unittest

import pyssg


class ImportSmokeTest(unittest.TestCase):
    def test_import_pyssg(self) -> None:
        self.assertIsInstance(pyssg.__version__, str)
        self.assertTrue(pyssg.__version__)
