"""Integration tests for the ``pyssg deploy`` CLI surface.

Exercises the argparse wiring and the meta actions (``list`` / ``status``). All
three built-in targets (``github-pages``, ``cloudflare``, ``netlify``) register
themselves; the ``list`` action additionally distinguishes a configured target
that has no registered implementation (an arbitrary key in ``Config.deploy``).
"""

from __future__ import annotations

import io
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from pyssg.cli import main
from pyssg.config import CONFIG_FILENAME


def _write_config(site: Path, body: str) -> None:
    site.mkdir(parents=True, exist_ok=True)
    (site / CONFIG_FILENAME).write_text(body, encoding="utf-8")


class DeployCliParserTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(self.enterContext(tempfile.TemporaryDirectory()))

    def test_deploy_without_action_fails(self) -> None:
        """``pyssg deploy`` without a sub-action is a usage error."""
        with self.assertRaises(SystemExit), redirect_stderr(io.StringIO()):
            main(["--site", str(self.tmp), "deploy"])

    def test_each_builtin_target_parser_exists(self) -> None:
        """Per-target subparsers accept the standard flags and dispatch.

        Drives ``netlify`` with its auth token unset so the pipeline reaches the
        credential check and reports the missing variable -- a deterministic
        failure that proves the flags parsed and the target was dispatched,
        without needing a real provider account.
        """
        _write_config(
            self.tmp,
            "from pyssg.config import Config\n"
            "config = Config(deploy={'netlify': {'site_id': 'x'}})\n",
        )
        err = io.StringIO()
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("NETLIFY_AUTH_TOKEN", None)
            with redirect_stderr(err):
                rc = main(
                    [
                        "--site",
                        str(self.tmp),
                        "deploy",
                        "netlify",
                        "--dry-run",
                        "--force",
                        "--skip-build",
                        "--skip-check",
                    ]
                )
        self.assertEqual(rc, 1)
        self.assertIn("NETLIFY_AUTH_TOKEN", err.getvalue())


class DeployListTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(self.enterContext(tempfile.TemporaryDirectory()))

    def test_list_with_no_targets(self) -> None:
        _write_config(self.tmp, "from pyssg.config import Config\nconfig = Config()\n")
        out = io.StringIO()
        with redirect_stdout(out):
            rc = main(["--site", str(self.tmp), "deploy", "list"])
        self.assertEqual(rc, 0)
        self.assertIn("no deploy targets configured", out.getvalue())

    def test_list_shows_configured_targets(self) -> None:
        # A built-in target (implemented) alongside an arbitrary key with no
        # registered implementation, to cover both columns of the table.
        _write_config(
            self.tmp,
            "from pyssg.config import Config\n"
            "config = Config(deploy={'github-pages': {}, 'custom-host': {}})\n",
        )
        out = io.StringIO()
        with redirect_stdout(out):
            rc = main(["--site", str(self.tmp), "deploy", "list"])
        self.assertEqual(rc, 0)
        text = out.getvalue()
        self.assertIn("github-pages", text)
        self.assertIn("custom-host", text)
        # github-pages is implemented ("yes"); custom-host has no target ("no").
        self.assertIn("yes", text)
        self.assertIn("no", text)


class DeployStatusTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(self.enterContext(tempfile.TemporaryDirectory()))

    def test_status_with_no_record(self) -> None:
        _write_config(
            self.tmp,
            "from pyssg.config import Config\nconfig = Config(deploy={'github-pages': {}})\n",
        )
        out = io.StringIO()
        with redirect_stdout(out):
            rc = main(["--site", str(self.tmp), "deploy", "status"])
        self.assertEqual(rc, 0)
        # Records absent -> placeholder dashes.
        self.assertIn("github-pages", out.getvalue())
        self.assertIn("-", out.getvalue())

    def test_status_with_no_targets(self) -> None:
        _write_config(self.tmp, "from pyssg.config import Config\nconfig = Config()\n")
        out = io.StringIO()
        with redirect_stdout(out):
            rc = main(["--site", str(self.tmp), "deploy", "status"])
        self.assertEqual(rc, 0)
        self.assertIn("no deploy targets configured", out.getvalue())


if __name__ == "__main__":
    unittest.main()
