"""Unit tests for the persistent last-deploy state."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pyssg.deploy.state import DeployRecord, read_record, write_record


class StateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.site = Path(self.enterContext(tempfile.TemporaryDirectory()))

    def _record(self, target: str = "github-pages", hash_value: str = "abc") -> DeployRecord:
        return DeployRecord(
            target=target,
            hash=hash_value,
            deployment_id="dep-1",
            url="https://example.com",
            timestamp="2026-06-02T09:14:00+00:00",
        )

    def test_round_trip(self) -> None:
        original = self._record()
        write_record(self.site, original)
        loaded = read_record(self.site, original.target)
        self.assertEqual(loaded, original)

    def test_read_missing_returns_none(self) -> None:
        self.assertIsNone(read_record(self.site, "unknown"))

    def test_read_corrupt_returns_none(self) -> None:
        path = self.site / ".pyssg-cache" / "deploy" / "github-pages.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("not json", encoding="utf-8")
        self.assertIsNone(read_record(self.site, "github-pages"))

    def test_write_overwrites_existing(self) -> None:
        write_record(self.site, self._record(hash_value="first"))
        write_record(self.site, self._record(hash_value="second"))
        loaded = read_record(self.site, "github-pages")
        self.assertIsNotNone(loaded)
        assert loaded is not None  # for mypy
        self.assertEqual(loaded.hash, "second")

    def test_per_target_files(self) -> None:
        write_record(self.site, self._record(target="github-pages"))
        write_record(self.site, self._record(target="cloudflare", hash_value="xyz"))
        gh = read_record(self.site, "github-pages")
        cf = read_record(self.site, "cloudflare")
        self.assertIsNotNone(gh)
        self.assertIsNotNone(cf)
        assert gh is not None and cf is not None  # for mypy
        self.assertEqual(gh.hash, "abc")
        self.assertEqual(cf.hash, "xyz")


if __name__ == "__main__":
    unittest.main()
