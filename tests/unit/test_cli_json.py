"""Tests for the machine-readable ``--json`` output of build/serve."""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from pyssg.cli import main
from pyssg.cli.common import build_stats_payload
from pyssg.cli.scaffold import init_site
from pyssg.core.build import BuildStats
from pyssg.core.types import Phase


class BuildStatsPayloadTest(unittest.TestCase):
    def test_payload_shape(self) -> None:
        stats = BuildStats(
            touched_per_phase={Phase.PARSE: 3},
            cache_hits=5,
            changed_outputs={"/a/", "/b/"},
        )
        payload = build_stats_payload(stats)
        self.assertEqual(payload["pages"], 2)
        self.assertEqual(payload["cache_hits"], 5)
        self.assertEqual(payload["phases"], {"parse": 3})

    def test_empty_phases_omitted(self) -> None:
        payload = build_stats_payload(BuildStats())
        self.assertEqual(payload["phases"], {})


class BuildJsonCommandTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(self.enterContext(tempfile.TemporaryDirectory()))

    def test_build_json_emits_parseable_summary(self) -> None:
        site = self.tmp / "site"
        init_site(site, preset="docs")
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = main(["--site", str(site), "build", "--json"])
        self.assertEqual(rc, 0)
        payload = json.loads(buf.getvalue().strip())
        self.assertEqual(payload["command"], "build")
        self.assertTrue(payload["ok"])
        self.assertGreaterEqual(payload["pages"], 1)
        self.assertIn("phases", payload)

    def test_build_json_reports_failure(self) -> None:
        # No pyssg.config.py -> build_site raises -> JSON error object, rc 1.
        site = self.tmp / "empty"
        site.mkdir()
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = main(["--site", str(site), "build", "--json"])
        self.assertEqual(rc, 1)
        payload = json.loads(buf.getvalue().strip())
        self.assertEqual(payload["command"], "build")
        self.assertFalse(payload["ok"])
        self.assertIn("error", payload)


if __name__ == "__main__":
    unittest.main()
