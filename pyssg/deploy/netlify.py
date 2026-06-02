"""Netlify deploy target (``pyssg deploy netlify``).

Publishes the built site with Netlify's file-digest Deploy API: the whole site
is described as a ``{path: sha1}`` manifest, Netlify replies with the subset of
hashes it does not already have, and only those files are uploaded. This is the
same content-addressed flow the Netlify CLI uses, so re-deploying a mostly
unchanged site uploads almost nothing.

Unlike Cloudflare's Direct Upload, the digest here is a plain SHA1 of the file
contents (stdlib ``hashlib``), so this target needs no extra hashing
dependency -- only ``httpx`` from the optional ``pyssg[deploy]`` extra, imported
lazily so that merely importing this module never requires the extra.

Configuration (under ``Config.deploy["netlify"]``):

* ``site_id`` (required) -- the Netlify site's API id (its ``api_id``, or the
  ``*.netlify.app`` subdomain).
* ``production`` (optional, default ``True``) -- ``True`` publishes to the live
  site; ``False`` creates a draft (preview) deploy that does not change what is
  currently published.

Authentication: the ``NETLIFY_AUTH_TOKEN`` environment variable (a personal
access token). Read from the environment, never from config.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
from dataclasses import dataclass
from time import perf_counter
from typing import TYPE_CHECKING
from urllib.parse import quote

from pyssg.deploy import register
from pyssg.deploy._http import HttpSession
from pyssg.deploy.base import DeployError, DeployResult

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Mapping
    from pathlib import Path

    import httpx

    from pyssg.deploy.base import DeployContext

_API_BASE = "https://api.netlify.com/api/v1"
_TOKEN_ENV = "NETLIFY_AUTH_TOKEN"


@dataclass(frozen=True, slots=True)
class _File:
    """One built file as Netlify's digest API sees it.

    ``key`` is the manifest path (leading ``/``); ``rel`` is the same path
    without the leading slash, used in the upload URL. ``sha1`` is the content
    digest Netlify deduplicates on. ``path`` is re-read at upload time so file
    bodies are not all held in memory at once.
    """

    key: str
    rel: str
    sha1: str
    path: Path
    size: int


class NetlifyTarget:
    """Deploy to Netlify via the file-digest Deploy API.

    Stateless with respect to the pipeline. The test seams (``transport``,
    ``sleep``, retry/backoff knobs) let the flow run against an ``httpx``
    ``MockTransport`` with no real network or wall-clock delay.
    """

    name = "netlify"

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
        """The personal access token used as a bearer credential."""
        return [_TOKEN_ENV]

    def required_config_keys(self) -> list[str]:
        """The site id identifies which Netlify site to deploy to."""
        return ["site_id"]

    async def deploy(self, ctx: DeployContext) -> DeployResult:
        """Create a deploy from the digest manifest and upload required files.

        Returns the deploy id and its URL. Raises :class:`DeployError` on a
        missing extra, an API error, or a malformed response.
        """
        started = perf_counter()
        cfg = ctx.target_config
        site_id = _require_str(cfg, "site_id")
        production = _optional_bool(cfg, "production", default=True)
        token = os.environ[_TOKEN_ENV]

        files = _collect_files(ctx.out_dir)
        if not files:
            raise DeployError(f"output directory {ctx.out_dir} has no files to deploy")
        manifest = {f.key: f.sha1 for f in files}
        # Identical bodies share a sha1; upload each unique digest once.
        by_sha = {f.sha1: f for f in files}

        if ctx.dry_run:
            return _dry_run_result(files, started)

        headers = {"Authorization": f"Bearer {token}"}
        async with HttpSession.open(
            self.name,
            transport=self._transport,
            max_retries=self._max_retries,
            backoff_base=self._backoff_base,
            sleep=self._sleep,
        ) as session:
            deploy = await _create_deploy(session, site_id, headers, manifest, production)
            deploy_id = _str_field(deploy, "id", "creating deploy")
            required = _required_hashes(deploy)
            # Upload one file per unique required hash; dict.fromkeys dedups
            # while preserving order in case the API ever repeats a hash.
            to_upload = [by_sha[h] for h in dict.fromkeys(required) if h in by_sha]
            await _upload_files(session, deploy_id, headers, to_upload)

        required_set = set(required)
        uploaded = [f for f in files if f.sha1 in required_set]
        return DeployResult(
            url=_deploy_url(deploy),
            deployment_id=deploy_id,
            files_uploaded=len(uploaded),
            files_skipped=len(files) - len(uploaded),
            bytes_uploaded=sum(f.size for f in uploaded),
            elapsed_seconds=perf_counter() - started,
        )


# --- config helpers ---------------------------------------------------------


def _require_str(cfg: Mapping[str, object], key: str) -> str:
    value = cfg.get(key)
    if not isinstance(value, str) or not value:
        raise DeployError(f"deploy.netlify: '{key}' must be a non-empty string")
    return value


def _optional_bool(cfg: Mapping[str, object], key: str, *, default: bool) -> bool:
    if key not in cfg:
        return default
    value = cfg[key]
    if not isinstance(value, bool):
        raise DeployError(f"deploy.netlify: '{key}' must be a boolean")
    return value


# --- asset preparation ------------------------------------------------------


def _collect_files(out_dir: Path) -> list[_File]:
    """Hash every regular file under ``out_dir`` with SHA1, sorted by path.

    Deterministic (sorted, no clock/env reads), so the same tree yields the same
    manifest on every build.
    """
    files: list[_File] = []
    for path in sorted(out_dir.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        content = path.read_bytes()
        rel = path.relative_to(out_dir).as_posix()
        # SHA1 is Netlify's content-addressing key, not a security primitive.
        digest = hashlib.sha1(content).hexdigest()
        files.append(
            _File(
                key="/" + rel,
                rel=rel,
                sha1=digest,
                path=path,
                size=len(content),
            )
        )
    return files


def _dry_run_result(files: list[_File], started: float) -> DeployResult:
    """Counters for a dry run: every file is reported as a candidate upload."""
    return DeployResult(
        url="",
        deployment_id="dry-run",
        files_uploaded=len(files),
        files_skipped=0,
        bytes_uploaded=sum(f.size for f in files),
        elapsed_seconds=perf_counter() - started,
    )


# --- API steps --------------------------------------------------------------


async def _create_deploy(
    session: HttpSession,
    site_id: str,
    headers: Mapping[str, str],
    manifest: Mapping[str, str],
    production: bool,
) -> Mapping[str, object]:
    """Create a deploy from the digest manifest; return the deploy object."""
    body = await session.send_json(
        "POST",
        f"{_API_BASE}/sites/{quote(site_id, safe='')}/deploys",
        headers=headers,
        json={"files": dict(manifest), "draft": not production},
    )
    if not isinstance(body, dict):
        raise DeployError("creating deploy: response was not a JSON object")
    return body


def _required_hashes(deploy: Mapping[str, object]) -> list[str]:
    """The ``required`` hash list from a deploy response, defaulting to empty."""
    required = deploy.get("required")
    if required is None:
        return []
    if not isinstance(required, list):
        raise DeployError("creating deploy: 'required' was not a list of hashes")
    return [str(h) for h in required]


async def _upload_files(
    session: HttpSession,
    deploy_id: str,
    headers: Mapping[str, str],
    files: list[_File],
) -> None:
    """Upload the given files concurrently to the open deploy."""
    if not files:
        return
    await asyncio.gather(*(_upload_one(session, deploy_id, headers, f) for f in files))


async def _upload_one(
    session: HttpSession,
    deploy_id: str,
    headers: Mapping[str, str],
    file: _File,
) -> None:
    """PUT a single file's raw bytes to the deploy."""
    put_headers = {**dict(headers), "Content-Type": "application/octet-stream"}
    await session.send_json(
        "PUT",
        f"{_API_BASE}/deploys/{deploy_id}/files/{quote(file.rel, safe='/')}",
        headers=put_headers,
        content=file.path.read_bytes(),
    )


def _str_field(obj: Mapping[str, object], key: str, context: str) -> str:
    value = obj.get(key)
    if not isinstance(value, str) or not value:
        raise DeployError(f"{context}: response did not contain a '{key}'")
    return value


def _deploy_url(deploy: Mapping[str, object]) -> str:
    """Prefer the HTTPS deploy URL, falling back to the plain one or empty."""
    for key in ("ssl_url", "url", "deploy_ssl_url", "deploy_url"):
        value = deploy.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


register(NetlifyTarget())


__all__ = ["NetlifyTarget"]
