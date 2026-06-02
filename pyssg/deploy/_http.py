"""Shared async HTTP plumbing for API-based deploy targets.

Targets that talk to a provider over HTTP (Cloudflare Pages, Netlify) need the
same handful of things: a lazily imported ``httpx`` client (it lives behind the
optional ``pyssg[deploy]`` extra, so importing it must fail with an actionable
message rather than a bare ``ImportError``), automatic retry on transient
failures (HTTP 429/5xx and transport errors), and a concurrency cap so a large
site does not open hundreds of sockets at once.

:class:`HttpSession` wraps all of that. A target opens one session, issues
requests through :meth:`HttpSession.send_json`, and closes it. The session owns
the retry/backoff policy and an :class:`asyncio.Semaphore`; the target just
describes the requests.

``httpx`` is imported lazily inside :meth:`HttpSession.open` so that merely
importing a target module (which the CLI does to populate the registry) never
requires the extra -- only an actual deploy does. Tests inject an
``httpx`` ``MockTransport`` and a no-op ``sleep`` to exercise the retry logic
without real sockets or wall-clock delays.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from pyssg.deploy.base import DeployError

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Mapping

    import httpx

# Status codes worth retrying: rate limiting and the transient 5xx family. A
# 4xx other than 429 is a client error the caller must fix, so it is surfaced
# immediately.
_RETRY_STATUS = frozenset({429, 500, 502, 503, 504})

# Defaults chosen to be polite without making a failing deploy hang for minutes:
# four attempts with exponential backoff from half a second (0.5s, 1s, 2s).
_DEFAULT_RETRIES = 4
_DEFAULT_BACKOFF = 0.5
_DEFAULT_CONCURRENCY = 10
_DEFAULT_TIMEOUT = 60.0


def _missing_extra_error(target: str) -> DeployError:
    """Build the actionable error shown when ``httpx`` is not installed."""
    return DeployError(
        f"the {target!r} deploy target needs the optional 'deploy' extra. "
        "Install it with: pip install 'pyssg[deploy]' (or, with uv: uv add 'pyssg[deploy]')"
    )


class HttpSession:
    """An async HTTP client with retry, backoff, and a concurrency cap.

    Construct one with :meth:`open` (which performs the lazy ``httpx`` import),
    use it as an async context manager so the underlying client is always
    closed, and route every request through :meth:`send_json`.
    """

    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        concurrency: int,
        max_retries: int,
        backoff_base: float,
        sleep: Callable[[float], Awaitable[None]],
    ) -> None:
        self._client = client
        self._sem = asyncio.Semaphore(max(1, concurrency))
        self._max_retries = max(1, max_retries)
        self._backoff_base = backoff_base
        self._sleep = sleep

    @classmethod
    def open(
        cls,
        target: str,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        concurrency: int = _DEFAULT_CONCURRENCY,
        max_retries: int = _DEFAULT_RETRIES,
        backoff_base: float = _DEFAULT_BACKOFF,
        sleep: Callable[[float], Awaitable[None]] | None = None,
        timeout: float = _DEFAULT_TIMEOUT,
    ) -> HttpSession:
        """Open a session, importing ``httpx`` on demand.

        Raises :class:`DeployError` with an install hint if ``httpx`` (the
        ``pyssg[deploy]`` extra) is not available. ``transport`` and ``sleep``
        exist for tests; production callers leave them at their defaults.
        """
        try:
            import httpx
        except ModuleNotFoundError as exc:
            raise _missing_extra_error(target) from exc
        client = httpx.AsyncClient(transport=transport, timeout=timeout)
        return cls(
            client,
            concurrency=concurrency,
            max_retries=max_retries,
            backoff_base=backoff_base,
            sleep=sleep if sleep is not None else asyncio.sleep,
        )

    async def __aenter__(self) -> HttpSession:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self._client.aclose()

    def _backoff(self, attempt: int) -> float:
        """Delay before retry ``attempt`` (0-based): geometric, deterministic."""
        return self._backoff_base * (2.0**attempt)

    async def send_json(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        json: object | None = None,
        content: bytes | None = None,
        files: Mapping[str, tuple[str | None, bytes, str]] | None = None,
    ) -> object:
        """Send one request with retry and return the decoded JSON body.

        Exactly one body kind should be supplied: ``json`` (an
        application/json payload), ``content`` (a raw byte body -- set the
        ``Content-Type`` via ``headers``), or ``files`` (multipart form data).
        ``files`` entries are ``(filename, content, content_type)`` triples;
        passing ``None`` as the filename emits a plain multipart form field
        (no ``filename`` attribute), which some provider APIs require.

        Retries transport errors and HTTP 429/5xx up to the session limit with
        exponential backoff. On a non-2xx final response or exhausted retries,
        raises :class:`DeployError` including the provider's response text so the
        user sees what the API actually said.
        """
        import httpx

        request = self._client.build_request(
            method,
            url,
            headers=dict(headers) if headers else None,
            json=json,
            content=content,
            files=files,
        )
        last_detail = "no response"
        for attempt in range(self._max_retries):
            try:
                async with self._sem:
                    response = await self._client.send(request)
            except httpx.HTTPError as exc:
                last_detail = f"{type(exc).__name__}: {exc}"
            else:
                if response.status_code in _RETRY_STATUS and attempt < self._max_retries - 1:
                    last_detail = f"HTTP {response.status_code}"
                else:
                    return _decode(response, method, url)
            if attempt < self._max_retries - 1:
                await self._sleep(self._backoff(attempt))
        raise DeployError(
            f"{method} {url} failed after {self._max_retries} attempts: {last_detail}"
        )


def _decode(response: httpx.Response, method: str, url: str) -> object:
    """Validate the status and decode the JSON body, or raise :class:`DeployError`.

    Returns ``None`` for a successful response with an empty body, so endpoints
    that reply ``200``/``204`` with no payload (e.g. a raw file upload) do not
    look like a malformed JSON error to the caller.
    """
    if response.status_code >= 400:
        body = response.text.strip()
        snippet = body[:500] if body else "(empty body)"
        raise DeployError(f"{method} {url} returned HTTP {response.status_code}: {snippet}")
    if not response.content:
        return None
    try:
        return response.json()
    except ValueError as exc:
        raise DeployError(f"{method} {url} returned a non-JSON body: {exc}") from exc
