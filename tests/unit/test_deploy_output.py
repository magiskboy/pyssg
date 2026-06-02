"""Unit tests for the friendly deploy console formatter."""

from __future__ import annotations

import io
import unittest

from pyssg.deploy._output import Console
from pyssg.deploy.base import DeployResult


def _make_console() -> tuple[Console, io.StringIO, io.StringIO]:
    out = io.StringIO()
    err = io.StringIO()
    return Console(out=out, err=err), out, err


class ConsoleTest(unittest.TestCase):
    def test_step_prefix_is_homebrew_style(self) -> None:
        console, out, _ = _make_console()
        console.step("loading config")
        self.assertEqual(out.getvalue(), "==> loading config\n")

    def test_detail_lines_are_indented(self) -> None:
        console, out, _ = _make_console()
        console.detail("ok")
        self.assertEqual(out.getvalue(), "    ok\n")

    def test_error_goes_to_stderr_with_hints(self) -> None:
        console, out, err = _make_console()
        console.error("bad token", hints=["check your env", "rotate it"])
        self.assertEqual(out.getvalue(), "")
        self.assertEqual(
            err.getvalue(),
            "error: bad token\n  check your env\n  rotate it\n",
        )

    def test_summary_renders_aligned_key_value(self) -> None:
        console, out, _ = _make_console()
        console.summary(
            DeployResult(
                url="https://example.com",
                deployment_id="abc123",
                files_uploaded=3,
                files_skipped=2,
                bytes_uploaded=2048,
                elapsed_seconds=1.25,
            )
        )
        text = out.getvalue()
        # The keys appear left-aligned in the same column.
        self.assertIn("deployment", text)
        self.assertIn("abc123", text)
        self.assertIn("https://example.com", text)
        self.assertIn("3 file(s)", text)
        self.assertIn("2 file(s) (already present)", text)
        self.assertIn("1.2s", text)

    def test_summary_omits_skipped_when_zero(self) -> None:
        console, out, _ = _make_console()
        console.summary(
            DeployResult(
                url="https://example.com",
                deployment_id="abc",
                files_uploaded=1,
                files_skipped=0,
                bytes_uploaded=10,
                elapsed_seconds=0.1,
            )
        )
        self.assertNotIn("already present", out.getvalue())


if __name__ == "__main__":
    unittest.main()
