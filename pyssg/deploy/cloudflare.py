"""Cloudflare Pages deploy target (``pyssg deploy cloudflare``).

Publishes the built site with Cloudflare Pages' *Direct Upload* protocol -- the
same content-addressed flow Wrangler uses. Each file is hashed, the API is asked
which hashes it does not already have, only the missing files are uploaded
(deduplicated across the site and across previous deploys), and finally a
deployment is created from a manifest mapping every served path to its hash.

The asset endpoints (``/pages/assets/*``) are not part of Cloudflare's public,
documented REST surface; they are the routes the official tooling uses and may
change without notice. The hash is BLAKE3 of ``base64(content) + extension``
truncated to 32 hex characters, matching Wrangler exactly so uploads dedupe
against deployments made by other tools.

This target uses HTTP, so it needs the optional ``pyssg[deploy]`` extra
(``httpx`` for the client, ``blake3`` for the hash). Both are imported lazily so
that merely importing this module -- which the CLI does to populate the deploy
registry -- never requires the extra; only an actual deploy does.

Configuration (under ``Config.deploy["cloudflare"]``):

* ``account_id`` (required) -- Cloudflare account id that owns the project.
* ``project`` (required) -- Pages project name.
* ``branch`` (optional) -- deployment branch; when it equals the project's
  production branch Cloudflare publishes to production, otherwise a preview.
  Omitted by default (Cloudflare uses the project's production branch).
* ``concurrency`` (optional, default 10) -- parallel upload batches.

Authentication: the ``CLOUDFLARE_API_TOKEN`` environment variable, scoped
``Account > Cloudflare Pages > Edit``. The token is read from the environment,
never from config.
"""

from __future__ import annotations

import asyncio
import base64
import json
import mimetypes
import os
from dataclasses import dataclass
from time import perf_counter
from typing import TYPE_CHECKING

from pyssg.deploy import register
from pyssg.deploy._http import HttpSession
from pyssg.deploy.base import DeployError, DeployResult

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Mapping
    from pathlib import Path

    import httpx

    from pyssg.deploy.base import DeployContext

_API_BASE = "https://api.cloudflare.com/client/v4"
_TOKEN_ENV = "CLOUDFLARE_API_TOKEN"

# Direct Upload caps each upload batch. These are conservative relative to
# Cloudflare's limits so a batch never trips the request-size ceiling: at most
# this many files, or this many bytes of base64 payload, per POST.
_MAX_BATCH_FILES = 1000
_MAX_BATCH_BYTES = 40 * 1024 * 1024

# Length of the truncated BLAKE3 hex digest used as the asset key (16 bytes).
_HASH_HEX_LEN = 32


@dataclass(frozen=True, slots=True)
class _Asset:
    """One built file prepared for upload.

    ``key`` is the served path (manifest key, leading ``/``). ``digest`` is the
    Direct Upload content hash. ``base64`` is the file body, base64-encoded as
    the upload endpoint requires. ``content_type`` and ``size`` feed the upload
    metadata and the friendly summary.
    """

    key: str
    digest: str
    base64: str
    content_type: str
    size: int


class CloudflareTarget:
    """Deploy to Cloudflare Pages via the Direct Upload protocol.

    Stateless with respect to the pipeline. The test seams (``transport``,
    ``sleep``, retry/backoff knobs) let the upload flow run against an ``httpx``
    ``MockTransport`` with no real network or wall-clock delay; production uses
    the defaults.
    """

    name = "cloudflare"

    def __init__(
        self,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        sleep: Callable[[float], Awaitable[None]] | None = None,
        max_retries: int = 4,
        backoff_base: float = 0.5,
    ) -> None:
        self._transport = transport
        self._sleep = sleep
        self._max_retries = max_retries
        self._backoff_base = backoff_base

    def required_env(self) -> list[str]:
        """The Pages API token; everything else comes from config."""
        return [_TOKEN_ENV]

    def required_config_keys(self) -> list[str]:
        """Account and project identify which Pages project to deploy to."""
        return ["account_id", "project"]

    async def deploy(self, ctx: DeployContext) -> DeployResult:
        """Upload missing assets and create a Cloudflare Pages deployment.

        Returns the deployment id and its URL. Raises :class:`DeployError` on a
        missing extra, an API error, or a malformed response.
        """
        started = perf_counter()
        cfg = ctx.target_config
        account_id = _require_str(cfg, "account_id")
        project = _require_str(cfg, "project")
        branch = _optional_str(cfg, "branch")
        concurrency = _optional_int(cfg, "concurrency", default=10)
        token = os.environ[_TOKEN_ENV]

        assets = _collect_assets(ctx.out_dir)
        if not assets:
            raise DeployError(f"output directory {ctx.out_dir} has no files to deploy")
        manifest = {asset.key: asset.digest for asset in assets}
        # Deduplicate by hash: identical bodies upload once.
        by_digest = {asset.digest: asset for asset in assets}

        if ctx.dry_run:
            return _dry_run_result(assets, started)

        project_base = f"{_API_BASE}/accounts/{account_id}/pages/projects/{project}"
        async with HttpSession.open(
            self.name,
            transport=self._transport,
            concurrency=concurrency,
            max_retries=self._max_retries,
            backoff_base=self._backoff_base,
            sleep=self._sleep,
        ) as session:
            jwt = await _fetch_upload_token(session, project_base, token)
            missing = await _check_missing(session, jwt, sorted(by_digest))
            await _upload_assets(session, jwt, [by_digest[h] for h in missing])
            if missing:
                await _upsert_hashes(session, jwt, sorted(by_digest))
            deployment = await _create_deployment(session, project_base, token, manifest, branch)

        missing_set = set(missing)
        uploaded = [a for a in assets if a.digest in missing_set]
        return DeployResult(
            url=str(deployment.get("url") or ""),
            deployment_id=str(deployment.get("id") or ""),
            files_uploaded=len(uploaded),
            files_skipped=len(assets) - len(uploaded),
            bytes_uploaded=sum(a.size for a in uploaded),
            elapsed_seconds=perf_counter() - started,
        )


# --- config helpers ---------------------------------------------------------


def _require_str(cfg: Mapping[str, object], key: str) -> str:
    value = _optional_str(cfg, key)
    if not value:
        raise DeployError(f"deploy.cloudflare: '{key}' must be a non-empty string")
    return value


def _optional_str(cfg: Mapping[str, object], key: str) -> str | None:
    if key not in cfg:
        return None
    value = cfg[key]
    if not isinstance(value, str):
        raise DeployError(
            f"deploy.cloudflare: '{key}' must be a string, got {type(value).__name__}"
        )
    return value


def _optional_int(cfg: Mapping[str, object], key: str, *, default: int) -> int:
    if key not in cfg:
        return default
    value = cfg[key]
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise DeployError(f"deploy.cloudflare: '{key}' must be a positive integer")
    return value


# --- asset preparation ------------------------------------------------------


def _collect_assets(out_dir: Path) -> list[_Asset]:
    """Hash and encode every regular file under ``out_dir``, sorted by path.

    The result is deterministic (sorted, no clock/env reads) so two builds of
    the same tree produce the same manifest.
    """
    from blake3 import blake3

    assets: list[_Asset] = []
    for path in sorted(out_dir.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        content = path.read_bytes()
        encoded = base64.b64encode(content).decode("ascii")
        extension = path.suffix[1:]  # without the leading dot, matching Wrangler
        digest = blake3((encoded + extension).encode("utf-8")).hexdigest()[:_HASH_HEX_LEN]
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        key = "/" + path.relative_to(out_dir).as_posix()
        assets.append(
            _Asset(
                key=key,
                digest=digest,
                base64=encoded,
                content_type=content_type,
                size=len(content),
            )
        )
    return assets


def _dry_run_result(assets: list[_Asset], started: float) -> DeployResult:
    """Counters for a dry run: every asset is reported as a candidate upload."""
    return DeployResult(
        url="",
        deployment_id="dry-run",
        files_uploaded=len(assets),
        files_skipped=0,
        bytes_uploaded=sum(a.size for a in assets),
        elapsed_seconds=perf_counter() - started,
    )


# --- API steps --------------------------------------------------------------


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _result(envelope: object, context: str) -> object:
    """Validate a Cloudflare API envelope and return its ``result`` field.

    Cloudflare wraps responses as ``{success, errors, messages, result}``; a
    ``success: false`` (or a non-object body) becomes a :class:`DeployError`
    quoting the provider's error messages.
    """
    if not isinstance(envelope, dict):
        raise DeployError(f"{context}: unexpected response (not a JSON object)")
    if envelope.get("success") is False:
        raise DeployError(f"{context}: {_format_errors(envelope.get('errors'))}")
    return envelope.get("result")


def _format_errors(errors: object) -> str:
    """Render Cloudflare's ``errors`` array into a single readable string."""
    if isinstance(errors, list) and errors:
        parts: list[str] = []
        for item in errors:
            if isinstance(item, dict):
                code = item.get("code")
                message = item.get("message")
                parts.append(f"[{code}] {message}" if code is not None else str(message))
            else:
                parts.append(str(item))
        return "; ".join(parts)
    return "Cloudflare reported an error with no details"


async def _fetch_upload_token(session: HttpSession, project_base: str, token: str) -> str:
    """Exchange the account API token for a short-lived asset-upload JWT."""
    envelope = await session.send_json(
        "POST", f"{project_base}/upload-token", headers=_bearer(token)
    )
    result = _result(envelope, "fetching upload token")
    jwt = result.get("jwt") if isinstance(result, dict) else None
    if not isinstance(jwt, str):
        raise DeployError("fetching upload token: response did not contain a 'jwt'")
    return jwt


async def _check_missing(session: HttpSession, jwt: str, hashes: list[str]) -> list[str]:
    """Return the subset of ``hashes`` Cloudflare does not already store."""
    if not hashes:
        return []
    envelope = await session.send_json(
        "POST",
        f"{_API_BASE}/pages/assets/check-missing",
        headers=_bearer(jwt),
        json={"hashes": hashes},
    )
    result = _result(envelope, "checking for missing assets")
    if result is None:
        return []
    if not isinstance(result, list):
        raise DeployError("checking for missing assets: expected a list of hashes")
    return [str(h) for h in result]


async def _upload_assets(session: HttpSession, jwt: str, assets: list[_Asset]) -> None:
    """Upload the given assets in size-bounded batches, in parallel."""
    batches = list(_batch_assets(assets))
    if not batches:
        return
    await asyncio.gather(*(_upload_batch(session, jwt, batch) for batch in batches))


def _batch_assets(assets: list[_Asset]) -> list[list[_Asset]]:
    """Split assets into batches bounded by file count and base64 byte size."""
    batches: list[list[_Asset]] = []
    current: list[_Asset] = []
    current_bytes = 0
    for asset in assets:
        payload = len(asset.base64)
        if current and (
            len(current) >= _MAX_BATCH_FILES or current_bytes + payload > _MAX_BATCH_BYTES
        ):
            batches.append(current)
            current = []
            current_bytes = 0
        current.append(asset)
        current_bytes += payload
    if current:
        batches.append(current)
    return batches


async def _upload_batch(session: HttpSession, jwt: str, batch: list[_Asset]) -> None:
    """Upload one batch of assets to the content-addressed store."""
    payload = [
        {
            "key": asset.digest,
            "value": asset.base64,
            "metadata": {"contentType": asset.content_type},
            "base64": True,
        }
        for asset in batch
    ]
    envelope = await session.send_json(
        "POST",
        f"{_API_BASE}/pages/assets/upload",
        headers=_bearer(jwt),
        json=payload,
    )
    _result(envelope, "uploading assets")


async def _upsert_hashes(session: HttpSession, jwt: str, hashes: list[str]) -> None:
    """Register the full hash set so Cloudflare retains the deployment's assets."""
    envelope = await session.send_json(
        "POST",
        f"{_API_BASE}/pages/assets/upsert-hashes",
        headers=_bearer(jwt),
        json={"hashes": hashes},
    )
    _result(envelope, "registering asset hashes")


async def _create_deployment(
    session: HttpSession,
    project_base: str,
    token: str,
    manifest: Mapping[str, str],
    branch: str | None,
) -> Mapping[str, object]:
    """Create the deployment from the manifest and return its result object."""
    files: dict[str, tuple[str | None, bytes, str]] = {
        # filename=None makes this a plain multipart form field, matching the
        # FormData the official tooling sends.
        "manifest": (None, json.dumps(manifest).encode("utf-8"), "application/json"),
    }
    if branch:
        files["branch"] = (None, branch.encode("utf-8"), "text/plain")
    envelope = await session.send_json(
        "POST", f"{project_base}/deployments", headers=_bearer(token), files=files
    )
    result = _result(envelope, "creating deployment")
    if not isinstance(result, dict):
        raise DeployError("creating deployment: response did not contain a deployment object")
    return result


register(CloudflareTarget())


__all__ = ["CloudflareTarget"]
