"""Unit tests for the cloudflare deploy target.

The Direct Upload flow is exercised end to end against an ``httpx``
``MockTransport`` -- no network, no real Cloudflare account. A recording handler
stands in for the API and lets each test assert on exactly which endpoints were
called and what payloads they received.
"""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import httpx

from pyssg.deploy.base import DeployContext, DeployError, DeployResult
from pyssg.deploy.cloudflare import CloudflareTarget, _collect_assets

_TOKEN = {"CLOUDFLARE_API_TOKEN": "cf-token"}


async def _nosleep(_delay: float) -> None:
    """Drop-in for asyncio.sleep so retry tests do not actually wait."""
    return None


class _FakeApi:
    """Records requests and serves canned Direct Upload responses.

    ``missing`` controls what ``check-missing`` reports as not-yet-stored.
    ``fail_paths`` maps a path suffix to a number of leading failures (HTTP 500)
    before it starts succeeding, to drive the retry path.
    """

    def __init__(self, *, missing: list[str] | None = None) -> None:
        self.missing = missing if missing is not None else []
        self.requests: list[httpx.Request] = []
        self.fail_remaining: dict[str, int] = {}
        self.deployment_error: dict[str, object] | None = None

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self._handle)

    def paths(self) -> list[str]:
        return [r.url.path for r in self.requests]

    def request_for(self, suffix: str) -> httpx.Request:
        for r in self.requests:
            if r.url.path.endswith(suffix):
                return r
        raise AssertionError(f"no request to {suffix}; saw {self.paths()}")

    def _handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path = request.url.path
        for suffix, remaining in list(self.fail_remaining.items()):
            if path.endswith(suffix) and remaining > 0:
                self.fail_remaining[suffix] = remaining - 1
                return httpx.Response(500, json={"success": False, "errors": []})
        if path.endswith("/upload-token"):
            return httpx.Response(200, json={"success": True, "result": {"jwt": "jwt-xyz"}})
        if path.endswith("/pages/assets/check-missing"):
            return httpx.Response(200, json={"success": True, "result": self.missing})
        if path.endswith("/pages/assets/upload"):
            return httpx.Response(200, json={"success": True, "result": True})
        if path.endswith("/pages/assets/upsert-hashes"):
            return httpx.Response(200, json={"success": True, "result": True})
        if path.endswith("/deployments"):
            if self.deployment_error is not None:
                return httpx.Response(
                    200, json={"success": False, "errors": [self.deployment_error]}
                )
            return httpx.Response(
                200,
                json={"success": True, "result": {"id": "dep-1", "url": "https://abc.pages.dev"}},
            )
        return httpx.Response(404, json={"success": False, "errors": [{"message": path}]})


class CollectAssetsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.out = Path(self.enterContext(tempfile.TemporaryDirectory())).resolve()

    def test_hash_matches_wrangler_formula(self) -> None:
        import base64

        from blake3 import blake3

        (self.out / "index.html").write_text("<h1>hi</h1>", encoding="utf-8")
        [asset] = _collect_assets(self.out)
        self.assertEqual(asset.key, "/index.html")
        self.assertEqual(asset.content_type, "text/html")
        encoded = base64.b64encode(b"<h1>hi</h1>").decode("ascii")
        expected = blake3((encoded + "html").encode("utf-8")).hexdigest()[:32]
        self.assertEqual(asset.digest, expected)
        self.assertEqual(len(asset.digest), 32)

    def test_assets_are_sorted_and_nested_paths_use_forward_slashes(self) -> None:
        (self.out / "a.txt").write_text("a", encoding="utf-8")
        (self.out / "sub").mkdir()
        (self.out / "sub" / "b.txt").write_text("b", encoding="utf-8")
        keys = [a.key for a in _collect_assets(self.out)]
        self.assertEqual(keys, ["/a.txt", "/sub/b.txt"])


class DeployTest(unittest.TestCase):
    def setUp(self) -> None:
        self.out = Path(self.enterContext(tempfile.TemporaryDirectory())).resolve()
        (self.out / "index.html").write_text("<h1>hi</h1>", encoding="utf-8")
        (self.out / "style.css").write_text("body{}", encoding="utf-8")

    def _ctx(self, **cfg: object) -> DeployContext:
        cfg.setdefault("account_id", "acct-1")
        cfg.setdefault("project", "my-site")
        return DeployContext(
            site_dir=self.out.parent,
            out_dir=self.out,
            target_name="cloudflare",
            target_config=cfg,
            dry_run=False,
            force=False,
        )

    def _target(self, api: _FakeApi) -> CloudflareTarget:
        return CloudflareTarget(transport=api.transport(), sleep=_nosleep, backoff_base=0.0)

    def _run(self, api: _FakeApi, **cfg: object) -> DeployResult:
        target = self._target(api)
        with mock.patch.dict(os.environ, _TOKEN, clear=False):
            return asyncio.run(target.deploy(self._ctx(**cfg)))

    def test_uploads_missing_then_creates_deployment(self) -> None:
        digests = [a.digest for a in _collect_assets(self.out)]
        api = _FakeApi(missing=digests)
        result = self._run(api)
        self.assertEqual(result.deployment_id, "dep-1")
        self.assertEqual(result.url, "https://abc.pages.dev")
        self.assertEqual(result.files_uploaded, 2)
        self.assertEqual(result.files_skipped, 0)
        # Full flow was exercised in order.
        paths = api.paths()
        self.assertTrue(any(p.endswith("/upload-token") for p in paths))
        self.assertTrue(any(p.endswith("/pages/assets/check-missing") for p in paths))
        self.assertTrue(any(p.endswith("/pages/assets/upload") for p in paths))
        self.assertTrue(any(p.endswith("/pages/assets/upsert-hashes") for p in paths))
        self.assertTrue(any(p.endswith("/deployments") for p in paths))

    def test_upload_token_and_deployment_use_account_token(self) -> None:
        api = _FakeApi(missing=[a.digest for a in _collect_assets(self.out)])
        self._run(api)
        self.assertEqual(
            api.request_for("/upload-token").headers["authorization"], "Bearer cf-token"
        )
        self.assertEqual(
            api.request_for("/deployments").headers["authorization"], "Bearer cf-token"
        )
        # Asset endpoints authenticate with the short-lived JWT instead.
        self.assertEqual(
            api.request_for("/pages/assets/check-missing").headers["authorization"],
            "Bearer jwt-xyz",
        )

    def test_manifest_maps_every_path_to_its_hash(self) -> None:
        assets = _collect_assets(self.out)
        api = _FakeApi(missing=[a.digest for a in assets])
        self._run(api)
        body = api.request_for("/deployments").content
        # The manifest is a multipart form field; assert both paths appear.
        self.assertIn(b'name="manifest"', body)
        for asset in assets:
            self.assertIn(asset.key.encode(), body)
            self.assertIn(asset.digest.encode(), body)

    def test_skips_already_present_assets(self) -> None:
        # check-missing returns nothing -> no upload / upsert, deployment still made.
        api = _FakeApi(missing=[])
        result = self._run(api)
        self.assertEqual(result.files_uploaded, 0)
        self.assertEqual(result.files_skipped, 2)
        paths = api.paths()
        self.assertFalse(any(p.endswith("/pages/assets/upload") for p in paths))
        self.assertFalse(any(p.endswith("/pages/assets/upsert-hashes") for p in paths))
        self.assertTrue(any(p.endswith("/deployments") for p in paths))

    def test_check_missing_sends_deduplicated_hashes(self) -> None:
        # Two files with identical bytes and extension share one hash.
        (self.out / "style.css").write_text("body{}", encoding="utf-8")
        (self.out / "copy.css").write_text("body{}", encoding="utf-8")
        assets = _collect_assets(self.out)
        css_digest = next(a.digest for a in assets if a.key == "/style.css")
        api = _FakeApi(missing=[a.digest for a in assets])
        self._run(api)
        sent = json.loads(api.request_for("/check-missing").content)["hashes"]
        # style.css and copy.css collapse to a single hash in the request.
        self.assertEqual(len(sent), len(set(sent)))
        self.assertEqual(sent.count(css_digest), 1)

    def test_includes_branch_when_configured(self) -> None:
        api = _FakeApi(missing=[a.digest for a in _collect_assets(self.out)])
        self._run(api, branch="preview")
        body = api.request_for("/deployments").content
        self.assertIn(b'name="branch"', body)
        self.assertIn(b"preview", body)

    def test_api_error_is_reported(self) -> None:
        api = _FakeApi(missing=[a.digest for a in _collect_assets(self.out)])
        api.deployment_error = {"code": 8000, "message": "project not found"}
        with self.assertRaisesRegex(DeployError, "project not found"):
            self._run(api)

    def test_transient_500_is_retried(self) -> None:
        api = _FakeApi(missing=[a.digest for a in _collect_assets(self.out)])
        # Fail the very first endpoint twice, then let it through.
        api.fail_remaining = {"/upload-token": 2}
        result = self._run(api)
        self.assertEqual(result.deployment_id, "dep-1")
        # Three attempts at upload-token: two 500s and one success.
        self.assertEqual(sum(1 for p in api.paths() if p.endswith("/upload-token")), 3)

    def test_persistent_500_raises_after_retries(self) -> None:
        api = _FakeApi(missing=[a.digest for a in _collect_assets(self.out)])
        api.fail_remaining = {"/upload-token": 99}
        with self.assertRaisesRegex(DeployError, "HTTP 500"):
            self._run(api)

    def test_missing_account_id_raises(self) -> None:
        api = _FakeApi()
        ctx = DeployContext(
            site_dir=self.out.parent,
            out_dir=self.out,
            target_name="cloudflare",
            target_config={"project": "my-site"},
            dry_run=False,
            force=False,
        )
        with (
            mock.patch.dict(os.environ, _TOKEN, clear=False),
            self.assertRaisesRegex(DeployError, "'account_id' must be a non-empty"),
        ):
            asyncio.run(self._target(api).deploy(ctx))

    def test_bad_concurrency_raises(self) -> None:
        api = _FakeApi()
        with self.assertRaisesRegex(DeployError, "'concurrency' must be a positive integer"):
            self._run(api, concurrency=0)


class ContractTest(unittest.TestCase):
    def test_required_surface(self) -> None:
        target = CloudflareTarget()
        self.assertEqual(target.name, "cloudflare")
        self.assertEqual(target.required_env(), ["CLOUDFLARE_API_TOKEN"])
        self.assertEqual(target.required_config_keys(), ["account_id", "project"])


if __name__ == "__main__":
    unittest.main()
