"""Unit tests for the provider-agnostic deploy pipeline."""

from __future__ import annotations

import io
import os
import tempfile
import unittest
from dataclasses import dataclass, field
from pathlib import Path
from unittest import mock

from pyssg.deploy._output import Console
from pyssg.deploy.base import (
    DeployContext,
    DeployError,
    DeployResult,
    DeployTarget,
)
from pyssg.deploy.pipeline import run_deploy
from pyssg.deploy.state import read_record


@dataclass(slots=True)
class _MockTarget:
    """A fake target that records the context it was called with."""

    name: str = "mock"
    env: list[str] = field(default_factory=list)
    keys: list[str] = field(default_factory=list)
    result: DeployResult = field(
        default_factory=lambda: DeployResult(
            url="https://mock.example",
            deployment_id="mock-1",
            files_uploaded=2,
            files_skipped=0,
            bytes_uploaded=42,
            elapsed_seconds=0.05,
        )
    )
    seen: list[DeployContext] = field(default_factory=list)

    def required_env(self) -> list[str]:
        return list(self.env)

    def required_config_keys(self) -> list[str]:
        return list(self.keys)

    async def deploy(self, ctx: DeployContext) -> DeployResult:
        self.seen.append(ctx)
        return self.result


_CONFIG_TEMPLATE = """\
from pyssg.config import Config
config = Config(deploy={deploy!r})
"""


class PipelineTest(unittest.TestCase):
    def setUp(self) -> None:
        self.site = Path(self.enterContext(tempfile.TemporaryDirectory())).resolve()
        # Pre-populate the output directory so we can drive most tests with
        # skip_build=True; the build path is exercised separately in the
        # integration test, where we own a full preset scaffold.
        (self.site / "dist").mkdir()
        (self.site / "dist" / "index.html").write_text("<h1>hi</h1>", encoding="utf-8")
        self._capture, self._stdout, self._stderr = self._console()

    def _console(self) -> tuple[Console, io.StringIO, io.StringIO]:
        out = io.StringIO()
        err = io.StringIO()
        return Console(out=out, err=err), out, err

    def _write_config(self, deploy: dict[str, dict[str, object]]) -> None:
        (self.site / "pyssg.config.py").write_text(
            _CONFIG_TEMPLATE.format(deploy=deploy), encoding="utf-8"
        )

    def _registry(self, target: DeployTarget) -> dict[str, DeployTarget]:
        return {target.name: target}

    def test_happy_path_calls_target_and_persists_record(self) -> None:
        self._write_config({"mock": {"key": "value"}})
        target = _MockTarget()
        result = run_deploy(
            self.site,
            "mock",
            skip_build=True,
            targets=self._registry(target),
            console=self._capture,
        )
        self.assertEqual(result.deployment_id, "mock-1")
        self.assertEqual(len(target.seen), 1)
        ctx = target.seen[0]
        self.assertEqual(ctx.target_config, {"key": "value"})
        self.assertEqual(ctx.out_dir, (self.site / "dist").resolve())
        # State persisted under the cache.
        record = read_record(self.site, "mock")
        self.assertIsNotNone(record)
        assert record is not None  # for mypy
        self.assertEqual(record.deployment_id, "mock-1")
        self.assertEqual(record.url, "https://mock.example")

    def test_skip_when_hash_unchanged(self) -> None:
        self._write_config({"mock": {}})
        target = _MockTarget()
        run_deploy(
            self.site,
            "mock",
            skip_build=True,
            targets=self._registry(target),
            console=self._capture,
        )
        # Second run: no file changes -> target.deploy NOT invoked again.
        result = run_deploy(
            self.site,
            "mock",
            skip_build=True,
            targets=self._registry(target),
            console=self._capture,
        )
        self.assertTrue(result.skipped)
        self.assertEqual(len(target.seen), 1)

    def test_force_redeploys_even_when_unchanged(self) -> None:
        self._write_config({"mock": {}})
        target = _MockTarget()
        run_deploy(
            self.site,
            "mock",
            skip_build=True,
            targets=self._registry(target),
            console=self._capture,
        )
        run_deploy(
            self.site,
            "mock",
            skip_build=True,
            force=True,
            targets=self._registry(target),
            console=self._capture,
        )
        self.assertEqual(len(target.seen), 2)

    def test_dry_run_does_not_call_target(self) -> None:
        self._write_config({"mock": {}})
        target = _MockTarget()
        result = run_deploy(
            self.site,
            "mock",
            skip_build=True,
            dry_run=True,
            targets=self._registry(target),
            console=self._capture,
        )
        self.assertEqual(len(target.seen), 0)
        self.assertEqual(result.deployment_id, "dry-run")
        # Nothing was persisted; next non-dry-run will still push.
        self.assertIsNone(read_record(self.site, "mock"))

    def test_missing_env_var_aborts_before_build(self) -> None:
        self._write_config({"mock": {}})
        target = _MockTarget(env=["PYSSG_TEST_TOKEN_DOES_NOT_EXIST"])
        # Make doubly sure the env var really is absent.
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("PYSSG_TEST_TOKEN_DOES_NOT_EXIST", None)
            with self.assertRaisesRegex(DeployError, "missing required environment variable"):
                run_deploy(
                    self.site,
                    "mock",
                    skip_build=True,
                    targets=self._registry(target),
                    console=self._capture,
                )

    def test_missing_config_key_aborts(self) -> None:
        self._write_config({"mock": {}})
        target = _MockTarget(keys=["site_id"])
        with self.assertRaisesRegex(DeployError, "missing key\\(s\\): site_id"):
            run_deploy(
                self.site,
                "mock",
                skip_build=True,
                targets=self._registry(target),
                console=self._capture,
            )

    def test_target_not_configured_in_site(self) -> None:
        self._write_config({"other": {}})
        target = _MockTarget()
        with self.assertRaisesRegex(DeployError, "no deploy.'mock' section"):
            run_deploy(
                self.site,
                "mock",
                skip_build=True,
                targets=self._registry(target),
                console=self._capture,
            )

    def test_unknown_target_in_registry(self) -> None:
        self._write_config({"mock": {}})
        with self.assertRaisesRegex(DeployError, "unknown deploy target: mock"):
            run_deploy(
                self.site,
                "mock",
                skip_build=True,
                targets={},
                console=self._capture,
            )

    def test_skip_build_requires_existing_output_dir(self) -> None:
        self._write_config({"mock": {}})
        # Remove the pre-populated dist to simulate a fresh site.
        import shutil

        shutil.rmtree(self.site / "dist")
        target = _MockTarget()
        with self.assertRaisesRegex(DeployError, "--skip-build was set"):
            run_deploy(
                self.site,
                "mock",
                skip_build=True,
                targets=self._registry(target),
                console=self._capture,
            )

    def test_empty_output_dir_aborts_at_check(self) -> None:
        self._write_config({"mock": {}})
        # Empty out the dist directory before deploy.
        (self.site / "dist" / "index.html").unlink()
        target = _MockTarget()
        with self.assertRaisesRegex(DeployError, "is empty; nothing to deploy"):
            run_deploy(
                self.site,
                "mock",
                skip_build=True,
                targets=self._registry(target),
                console=self._capture,
            )


if __name__ == "__main__":
    unittest.main()
