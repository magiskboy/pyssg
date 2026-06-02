"""Unit tests for the github-pages deploy target.

The target shells out to ``git`` and force-pushes the built site to a content
branch. These tests stand up a local bare repository as the "remote" (via the
``remote`` config override) so the whole push path runs end to end without any
network access or GitHub credentials.
"""

from __future__ import annotations

import asyncio
import subprocess
import tempfile
import unittest
from pathlib import Path

from pyssg.deploy.base import DeployContext, DeployError
from pyssg.deploy.github_pages import GitHubPagesTarget, _pages_url


def _git(*args: str, cwd: Path) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


class PagesUrlTest(unittest.TestCase):
    def test_user_site_serves_from_root(self) -> None:
        self.assertEqual(_pages_url("alice/alice.github.io", None), "https://alice.github.io/")

    def test_project_site_serves_from_subpath(self) -> None:
        self.assertEqual(_pages_url("alice/docs", None), "https://alice.github.io/docs/")

    def test_cname_overrides(self) -> None:
        self.assertEqual(_pages_url("alice/docs", "docs.example.com"), "https://docs.example.com/")

    def test_owner_case_is_normalized(self) -> None:
        self.assertEqual(_pages_url("Alice/Docs", None), "https://alice.github.io/Docs/")


class DeployTest(unittest.TestCase):
    def setUp(self) -> None:
        root = Path(self.enterContext(tempfile.TemporaryDirectory())).resolve()
        self.out = root / "out"
        self.out.mkdir()
        (self.out / "index.html").write_text("<h1>hi</h1>", encoding="utf-8")
        (self.out / "_assets").mkdir()
        (self.out / "_assets" / "app.css").write_text("body{}", encoding="utf-8")
        # A bare repo acts as the push target ("remote").
        self.remote = root / "remote.git"
        self.remote.mkdir()
        _git("init", "--bare", "-q", cwd=self.remote)
        self.target = GitHubPagesTarget()

    def _ctx(self, **cfg: object) -> DeployContext:
        cfg.setdefault("repo", "alice/docs")
        cfg.setdefault("remote", str(self.remote))
        return DeployContext(
            site_dir=self.out.parent,
            out_dir=self.out,
            target_name="github-pages",
            target_config=cfg,
            dry_run=False,
            force=False,
        )

    def _checkout(self, branch: str) -> Path:
        """Clone the remote branch into a fresh dir to inspect what was pushed."""
        dest = Path(self.enterContext(tempfile.TemporaryDirectory()))
        _git("clone", "-q", "-b", branch, str(self.remote), str(dest / "co"), cwd=dest.parent)
        return dest / "co"

    def test_pushes_site_to_default_branch(self) -> None:
        result = asyncio.run(self.target.deploy(self._ctx()))
        self.assertEqual(result.url, "https://alice.github.io/docs/")
        self.assertEqual(result.files_uploaded, 2)
        co = self._checkout("gh-pages")
        self.assertEqual((co / "index.html").read_text(encoding="utf-8"), "<h1>hi</h1>")
        self.assertEqual((co / "_assets" / "app.css").read_text(encoding="utf-8"), "body{}")
        # .nojekyll is always written so Pages serves _assets/ verbatim.
        self.assertTrue((co / ".nojekyll").is_file())
        # No CNAME unless configured.
        self.assertFalse((co / "CNAME").exists())

    def test_deployment_id_is_the_commit_sha(self) -> None:
        result = asyncio.run(self.target.deploy(self._ctx()))
        head = _git("rev-parse", "gh-pages", cwd=self.remote).strip()
        self.assertEqual(result.deployment_id, head)

    def test_custom_branch_and_cname(self) -> None:
        result = asyncio.run(
            self.target.deploy(self._ctx(branch="pages", cname="docs.example.com"))
        )
        self.assertEqual(result.url, "https://docs.example.com/")
        co = self._checkout("pages")
        self.assertEqual((co / "CNAME").read_text(encoding="utf-8"), "docs.example.com\n")

    def test_redeploy_force_pushes_over_branch(self) -> None:
        asyncio.run(self.target.deploy(self._ctx()))
        (self.out / "index.html").write_text("<h1>v2</h1>", encoding="utf-8")
        asyncio.run(self.target.deploy(self._ctx()))
        co = self._checkout("gh-pages")
        self.assertEqual((co / "index.html").read_text(encoding="utf-8"), "<h1>v2</h1>")
        # Force push leaves a single throwaway commit, not accumulated history.
        log = _git("rev-list", "--count", "gh-pages", cwd=self.remote).strip()
        self.assertEqual(log, "1")

    def test_dry_run_builds_commit_but_does_not_push(self) -> None:
        ctx = DeployContext(
            site_dir=self.out.parent,
            out_dir=self.out,
            target_name="github-pages",
            target_config={"repo": "alice/docs", "remote": str(self.remote)},
            dry_run=True,
            force=False,
        )
        result = asyncio.run(self.target.deploy(ctx))
        self.assertTrue(result.deployment_id)
        # Nothing reached the remote.
        with self.assertRaises(subprocess.CalledProcessError):
            _git("rev-parse", "gh-pages", cwd=self.remote)

    def test_missing_repo_key_raises(self) -> None:
        ctx = DeployContext(
            site_dir=self.out.parent,
            out_dir=self.out,
            target_name="github-pages",
            target_config={"remote": str(self.remote)},
            dry_run=False,
            force=False,
        )
        with self.assertRaisesRegex(DeployError, "'repo' must be a non-empty"):
            asyncio.run(self.target.deploy(ctx))

    def test_malformed_repo_raises(self) -> None:
        with self.assertRaisesRegex(DeployError, "must look like 'owner/name'"):
            asyncio.run(self.target.deploy(self._ctx(repo="not-a-slug")))

    def test_non_string_option_raises(self) -> None:
        with self.assertRaisesRegex(DeployError, "'branch' must be a string"):
            asyncio.run(self.target.deploy(self._ctx(branch=123)))

    def test_push_failure_raises_deploy_error(self) -> None:
        with self.assertRaises(DeployError):
            asyncio.run(self.target.deploy(self._ctx(remote=str(self.out / "does-not-exist.git"))))


class ContractTest(unittest.TestCase):
    def test_required_surface(self) -> None:
        target = GitHubPagesTarget()
        self.assertEqual(target.name, "github-pages")
        self.assertEqual(target.required_env(), [])
        self.assertEqual(target.required_config_keys(), ["repo"])


if __name__ == "__main__":
    unittest.main()
