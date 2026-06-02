"""Unit tests for the netlify deploy target.

The file-digest Deploy API is exercised end to end against an ``httpx``
``MockTransport``. A recording handler stands in for the API so each test can
assert exactly which files were uploaded and what the create-deploy request
looked like.
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
from pyssg.deploy.netlify import NetlifyTarget, _collect_files

_TOKEN = {"NETLIFY_AUTH_TOKEN": "nf-token"}


async def _nosleep(_delay: float) -> None:
    return None


class _FakeApi:
    """Records requests and serves canned Netlify Deploy API responses.

    ``required`` is the set of SHA1 hashes the create-deploy call reports as
    not-yet-present (i.e. needing upload).
    """

    def __init__(self, *, required: list[str] | None = None) -> None:
        self.required = required if required is not None else []
        self.requests: list[httpx.Request] = []
        self.create_error: int | None = None

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self._handle)

    def paths(self) -> list[str]:
        return [r.url.path for r in self.requests]

    def puts(self) -> list[httpx.Request]:
        return [r for r in self.requests if r.method == "PUT"]

    def request_for(self, suffix: str) -> httpx.Request:
        for r in self.requests:
            if r.url.path.endswith(suffix):
                return r
        raise AssertionError(f"no request to {suffix}; saw {self.paths()}")

    def _handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path = request.url.path
        if path.endswith("/deploys") and request.method == "POST":
            if self.create_error is not None:
                return httpx.Response(self.create_error, text="boom")
            return httpx.Response(
                200,
                json={
                    "id": "dep-1",
                    "required": self.required,
                    "ssl_url": "https://my-site.netlify.app",
                },
            )
        if "/files/" in path and request.method == "PUT":
            return httpx.Response(200, json={"id": "file-1"})
        return httpx.Response(404, text=path)


class CollectFilesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.out = Path(self.enterContext(tempfile.TemporaryDirectory())).resolve()

    def test_sha1_and_paths(self) -> None:
        import hashlib

        (self.out / "index.html").write_text("<h1>hi</h1>", encoding="utf-8")
        (self.out / "sub").mkdir()
        (self.out / "sub" / "a.css").write_text("body{}", encoding="utf-8")
        files = _collect_files(self.out)
        self.assertEqual([f.key for f in files], ["/index.html", "/sub/a.css"])
        self.assertEqual([f.rel for f in files], ["index.html", "sub/a.css"])
        self.assertEqual(files[0].sha1, hashlib.sha1(b"<h1>hi</h1>").hexdigest())


class DeployTest(unittest.TestCase):
    def setUp(self) -> None:
        self.out = Path(self.enterContext(tempfile.TemporaryDirectory())).resolve()
        (self.out / "index.html").write_text("<h1>hi</h1>", encoding="utf-8")
        (self.out / "style.css").write_text("body{}", encoding="utf-8")

    def _ctx(self, **cfg: object) -> DeployContext:
        cfg.setdefault("site_id", "site-123")
        return DeployContext(
            site_dir=self.out.parent,
            out_dir=self.out,
            target_name="netlify",
            target_config=cfg,
            dry_run=False,
            force=False,
        )

    def _target(self, api: _FakeApi) -> NetlifyTarget:
        return NetlifyTarget(transport=api.transport(), sleep=_nosleep, backoff_base=0.0)

    def _run(self, api: _FakeApi, **cfg: object) -> DeployResult:
        with mock.patch.dict(os.environ, _TOKEN, clear=False):
            return asyncio.run(self._target(api).deploy(self._ctx(**cfg)))

    def test_creates_deploy_and_uploads_required(self) -> None:
        files = _collect_files(self.out)
        api = _FakeApi(required=[f.sha1 for f in files])
        result = self._run(api)
        self.assertEqual(result.deployment_id, "dep-1")
        self.assertEqual(result.url, "https://my-site.netlify.app")
        self.assertEqual(result.files_uploaded, 2)
        self.assertEqual(result.files_skipped, 0)
        self.assertEqual(len(api.puts()), 2)

    def test_skips_files_already_present(self) -> None:
        api = _FakeApi(required=[])
        result = self._run(api)
        self.assertEqual(result.files_uploaded, 0)
        self.assertEqual(result.files_skipped, 2)
        self.assertEqual(len(api.puts()), 0)

    def test_uploads_one_request_per_unique_content(self) -> None:
        # Two files, identical bytes -> one sha1 -> a single upload covers both.
        (self.out / "style.css").write_text("body{}", encoding="utf-8")
        (self.out / "copy.css").write_text("body{}", encoding="utf-8")
        files = _collect_files(self.out)
        api = _FakeApi(required=[f.sha1 for f in files])
        result = self._run(api)
        self.assertEqual(len(api.puts()), len({f.sha1 for f in files}))
        # All three files (index + the two identical css) count as "uploaded".
        self.assertEqual(result.files_uploaded, 3)

    def test_production_omits_draft(self) -> None:
        api = _FakeApi(required=[])
        self._run(api)
        body = json.loads(api.request_for("/deploys").content)
        self.assertEqual(body["draft"], False)
        self.assertIn("/index.html", body["files"])

    def test_preview_sets_draft(self) -> None:
        api = _FakeApi(required=[])
        self._run(api, production=False)
        body = json.loads(api.request_for("/deploys").content)
        self.assertEqual(body["draft"], True)

    def test_put_uses_octet_stream_and_raw_body(self) -> None:
        files = _collect_files(self.out)
        api = _FakeApi(required=[f.sha1 for f in files])
        self._run(api)
        put = api.request_for("/files/index.html")
        self.assertEqual(put.headers["content-type"], "application/octet-stream")
        self.assertEqual(put.headers["authorization"], "Bearer nf-token")
        self.assertEqual(put.content, b"<h1>hi</h1>")

    def test_api_error_is_reported(self) -> None:
        api = _FakeApi(required=[])
        api.create_error = 422
        with self.assertRaisesRegex(DeployError, "HTTP 422"):
            self._run(api)

    def test_missing_site_id_raises(self) -> None:
        api = _FakeApi()
        ctx = DeployContext(
            site_dir=self.out.parent,
            out_dir=self.out,
            target_name="netlify",
            target_config={},
            dry_run=False,
            force=False,
        )
        with (
            mock.patch.dict(os.environ, _TOKEN, clear=False),
            self.assertRaisesRegex(DeployError, "'site_id' must be a non-empty"),
        ):
            asyncio.run(self._target(api).deploy(ctx))

    def test_bad_production_type_raises(self) -> None:
        api = _FakeApi()
        with self.assertRaisesRegex(DeployError, "'production' must be a boolean"):
            self._run(api, production="yes")

    def test_empty_output_raises(self) -> None:
        (self.out / "index.html").unlink()
        (self.out / "style.css").unlink()
        api = _FakeApi()
        with self.assertRaisesRegex(DeployError, "no files to deploy"):
            self._run(api)


class ContractTest(unittest.TestCase):
    def test_required_surface(self) -> None:
        target = NetlifyTarget()
        self.assertEqual(target.name, "netlify")
        self.assertEqual(target.required_env(), ["NETLIFY_AUTH_TOKEN"])
        self.assertEqual(target.required_config_keys(), ["site_id"])


if __name__ == "__main__":
    unittest.main()
