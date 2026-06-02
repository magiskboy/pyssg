"""Unit tests for the shared async HTTP session used by API deploy targets."""

from __future__ import annotations

import asyncio
import unittest
from collections.abc import Callable

import httpx

from pyssg.deploy._http import HttpSession, _missing_extra_error
from pyssg.deploy.base import DeployError


async def _nosleep(_delay: float) -> None:
    return None


class MissingExtraTest(unittest.TestCase):
    def test_message_points_at_the_deploy_extra(self) -> None:
        err = _missing_extra_error("cloudflare")
        self.assertIsInstance(err, DeployError)
        self.assertIn("'cloudflare'", str(err))
        self.assertIn("pyssg[deploy]", str(err))


class RetryTest(unittest.TestCase):
    def _session(self, handler: Callable[[httpx.Request], httpx.Response]) -> HttpSession:
        return HttpSession.open(
            "test",
            transport=httpx.MockTransport(handler),
            max_retries=4,
            backoff_base=0.0,
            sleep=_nosleep,
        )

    def test_retries_transport_error_then_succeeds(self) -> None:
        calls = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            if calls["n"] == 1:
                raise httpx.ConnectError("boom", request=request)
            return httpx.Response(200, json={"ok": True})

        async def run() -> object:
            async with self._session(handler) as session:
                return await session.send_json("GET", "https://example.test/x")

        self.assertEqual(asyncio.run(run()), {"ok": True})
        self.assertEqual(calls["n"], 2)

    def test_transport_error_exhausts_and_raises(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("down", request=request)

        async def run() -> object:
            async with self._session(handler) as session:
                return await session.send_json("GET", "https://example.test/x")

        with self.assertRaisesRegex(DeployError, "failed after 4 attempts"):
            asyncio.run(run())

    def test_client_error_is_not_retried(self) -> None:
        calls = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            return httpx.Response(403, text="forbidden")

        async def run() -> object:
            async with self._session(handler) as session:
                return await session.send_json("GET", "https://example.test/x")

        with self.assertRaisesRegex(DeployError, "HTTP 403"):
            asyncio.run(run())
        # A 4xx is the caller's fault: surfaced on the first response, no retry.
        self.assertEqual(calls["n"], 1)


if __name__ == "__main__":
    unittest.main()
