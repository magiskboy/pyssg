"""Tests for the CLI's top-level error handling.

The CLI must turn known :class:`BuildError` failures into a concise, located
report on stderr (return code 1) instead of letting them escape as a raw
Python traceback. This applies uniformly to every command, including ``serve``.
"""

from __future__ import annotations

import io
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path

from pyssg_cli import cli


def run_cli_stderr(argv: list[str]) -> tuple[int, str]:
    """Run the CLI with ``argv`` and capture (return code, stderr)."""

    buffer = io.StringIO()
    with redirect_stderr(buffer):
        code = cli.main(argv)
    return code, buffer.getvalue()


def missing_config(tmp: str) -> list[str]:
    return ["-c", str(Path(tmp) / "pyssg.config.py")]


class MissingConfigTest(unittest.TestCase):
    def test_build_reports_friendly_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code, err = run_cli_stderr(["build", *missing_config(tmp)])
            self.assertEqual(code, 1)
            self.assertIn("Build failed", err)
            self.assertIn("Config file not found", err)
            self.assertNotIn("Traceback (most recent call last)", err)

    def test_serve_reports_friendly_error(self) -> None:
        # `serve` used to let the BuildError escape as a traceback because it
        # never wrapped load_config; the centralized handler now catches it.
        with tempfile.TemporaryDirectory() as tmp:
            code, err = run_cli_stderr(["serve", *missing_config(tmp)])
            self.assertEqual(code, 1)
            self.assertIn("Build failed", err)
            self.assertIn("Config file not found", err)
            self.assertNotIn("Traceback (most recent call last)", err)


if __name__ == "__main__":
    unittest.main()
