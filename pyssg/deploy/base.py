"""Public contracts for deploy targets.

A *deploy target* is the integration with a single hosting provider (GitHub
Pages, Cloudflare Pages, Netlify, ...). Targets only declare facts about
themselves and execute the actual upload; everything that is provider-agnostic
(loading config, building, hashing, skip detection, persisting last-deploy
state, friendly output) lives in :mod:`pyssg.deploy.pipeline`.

This module is stdlib-only on purpose: it is the boundary between the engine
and the periphery, so it must not pull in optional dependencies like ``httpx``.

The :class:`DeployTarget` Protocol describes the surface every target must
expose. The orchestrator constructs a :class:`DeployContext` for each run and
calls ``target.deploy(ctx)``; the target returns a :class:`DeployResult` on
success or raises :class:`DeployError` with a user-actionable message on
unrecoverable failure.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from pyssg.core.errors import PyssgError

if TYPE_CHECKING:
    from pathlib import Path


class DeployError(PyssgError):
    """A deploy run failed in a way the user needs to act on.

    Targets raise this for missing credentials, network errors, provider API
    errors, or anything else that aborts the upload. The pipeline catches it,
    prints the message via the friendly console formatter, and exits with a
    non-zero status; the message itself MUST be self-contained (what failed,
    and if possible, what to do about it).
    """


@dataclass(frozen=True, slots=True)
class DeployResult:
    """The outcome of a single ``target.deploy(ctx)`` call.

    ``url`` is the canonical user-facing URL for the freshly deployed site (or
    the existing one if ``skipped``). ``deployment_id`` is whatever the provider
    uses to identify this revision (a git commit sha for GitHub Pages, a UUID
    for Cloudflare Pages, etc.); the pipeline stores it so the next run can show
    "no changes since <id>". ``files_skipped`` counts files the provider already
    had (content-addressed upload) and did not require re-uploading.

    ``skipped`` is True only when the whole deploy was a no-op because the
    output tree hash matched the previous deploy; in that case the file/byte
    counters are zero and ``elapsed_seconds`` is the time spent computing the
    hash, not pushing.
    """

    url: str
    deployment_id: str
    files_uploaded: int
    files_skipped: int
    bytes_uploaded: int
    elapsed_seconds: float
    skipped: bool = False


@dataclass(frozen=True, slots=True)
class DeployContext:
    """Everything a target needs to know to run one deploy.

    ``site_dir`` and ``out_dir`` are absolute resolved paths. ``target_config``
    is the dict the user wrote under ``Config.deploy[target_name]``; the target
    is responsible for reading the keys it declared in
    :meth:`DeployTarget.required_config_keys` and may also read optional ones.

    ``dry_run`` means "do everything except mutate the remote": the target
    should still validate auth, compute what would be uploaded, and return a
    :class:`DeployResult` with sensible counters, but MUST NOT push.

    ``force`` is informational: by the time a target sees the context, the
    pipeline has already decided not to skip. Targets that themselves implement
    fine-grained skipping (e.g. per-file digest match) may consult this flag.
    """

    site_dir: Path
    out_dir: Path
    target_name: str
    target_config: dict[str, object]
    dry_run: bool
    force: bool


class DeployTarget(Protocol):
    """Per-provider integration surface.

    Implementations are typically stateless singletons; the pipeline holds the
    state (cache, last-deploy record) and passes it through ``ctx``.

    ``name`` is the registry key and the CLI subcommand name; it MUST be a
    short, hyphenated identifier (``github-pages``, ``cloudflare``, ``netlify``).
    """

    name: str

    def required_env(self) -> list[str]:
        """Environment variables that must be set before ``deploy`` is called.

        The pipeline checks these up front and fails with a clear message
        listing the missing ones; the target itself can assume they are present
        when ``deploy`` runs. Return an empty list if the target reads no env
        (e.g. GitHub Pages, which uses ``git``'s own credential machinery).
        """

    def required_config_keys(self) -> list[str]:
        """Keys that must appear in ``ctx.target_config``.

        Optional keys are not listed here; the target reads them with
        ``.get(...)`` and supplies its own defaults. The pipeline reports
        missing required keys with a uniform message before invoking the
        target.
        """

    async def deploy(self, ctx: DeployContext) -> DeployResult:
        """Push the built site to the provider.

        Implementations should be idempotent for the same ``out_dir`` content
        (content-addressed upload), MUST honor ``ctx.dry_run``, and MUST raise
        :class:`DeployError` (not a bare ``Exception``) on any user-actionable
        failure.
        """
