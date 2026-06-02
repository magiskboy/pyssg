"""GitHub Pages deploy target (``pyssg deploy github-pages``).

GitHub Pages is published from a git branch, so this target needs no HTTP
client and no ``pyssg[deploy]`` extra: it shells out to ``git`` and force-pushes
the built site to a content branch (``gh-pages`` by default). Authentication
reuses whatever ``git`` already has -- a stored credential helper, an SSH key,
or a ``GITHUB_TOKEN`` in the environment (used as an HTTPS bearer header when
present) -- so the user does not hand pyssg a secret directly.

The push model is deliberately simple and stateless: every deploy builds a
brand-new single-commit repository in a temporary directory and force-pushes it
over the content branch. The branch therefore holds exactly the current site
with no accumulated history, which is what a generated-output branch wants. The
source branch and the project's real history are never touched.

Because pyssg emits root-absolute links, the published site must be served from
the domain root: a user/org site (``<user>.github.io``) or a custom domain via
``cname``. Project sites served from ``<user>.github.io/<repo>/`` need a base
URL prefix, which pyssg does not yet support.

Configuration (under ``Config.deploy["github-pages"]``):

* ``repo`` (required) -- ``"owner/name"`` slug of the GitHub repository.
* ``branch`` (optional, default ``"gh-pages"``) -- the content branch to push.
* ``cname`` (optional) -- custom domain; written as a ``CNAME`` file and used as
  the result URL.
* ``commit_message`` (optional) -- literal commit message for the push.
* ``remote`` (optional) -- full git remote URL, overriding the URL derived from
  ``repo``. Useful for GitHub Enterprise, a self-hosted mirror, or tests against
  a local bare repository.

This module registers its singleton target at import time; the CLI imports it
lazily via :func:`pyssg.deploy.load_builtin_targets`.
"""

from __future__ import annotations

import asyncio
import base64
import os
import shutil
import tempfile
from pathlib import Path
from time import perf_counter
from typing import TYPE_CHECKING

from pyssg.deploy import register
from pyssg.deploy._hash import file_count_and_size
from pyssg.deploy.base import DeployError, DeployResult

if TYPE_CHECKING:
    from collections.abc import Mapping

    from pyssg.deploy.base import DeployContext

# Default content branch GitHub Pages serves from when configured for branch
# deployment; the most widely used convention for generated output.
_DEFAULT_BRANCH = "gh-pages"

# Deterministic identity for the throwaway deploy commit. The author is not
# meaningful (history is force-pushed away each time), but git refuses to commit
# without one, and relying on the user's global git config would make the
# behavior depend on machine state.
_COMMIT_NAME = "pyssg deploy"
_COMMIT_EMAIL = "deploy@pyssg.local"
_DEFAULT_MESSAGE = "Deploy site with pyssg"


class GitHubPagesTarget:
    """Push the built site to a GitHub Pages content branch via ``git``.

    Stateless: the pipeline owns all persistence, and each :meth:`deploy` call
    operates entirely inside a fresh temporary directory it cleans up. The only
    side effects are subprocess calls to ``git`` and the network push.
    """

    name = "github-pages"

    def required_env(self) -> list[str]:
        """No required env vars; ``git`` supplies its own credentials.

        ``GITHUB_TOKEN`` is consulted when present (HTTPS bearer auth) but is not
        required: an SSH remote or a configured credential helper works too.
        """
        return []

    def required_config_keys(self) -> list[str]:
        """Only ``repo`` is mandatory; everything else has a default."""
        return ["repo"]

    async def deploy(self, ctx: DeployContext) -> DeployResult:
        """Force-push ``ctx.out_dir`` to the configured content branch.

        Builds a single-commit repository in a temporary directory, writes the
        Pages control files (``.nojekyll`` and, if configured, ``CNAME``), and
        force-pushes it. Returns the new commit sha as the deployment id and the
        canonical Pages URL. Raises :class:`DeployError` on any git failure or
        missing ``git`` binary.
        """
        started = perf_counter()
        cfg = ctx.target_config
        repo = _require_repo(cfg)
        branch = _str_option(cfg, "branch", _DEFAULT_BRANCH)
        cname = _optional_str(cfg, "cname")
        message = _str_option(cfg, "commit_message", _DEFAULT_MESSAGE)
        remote = _optional_str(cfg, "remote") or _https_remote(repo)

        file_count, total_bytes = file_count_and_size(ctx.out_dir)

        work = Path(tempfile.mkdtemp(prefix="pyssg-ghpages-"))
        try:
            _populate_worktree(ctx.out_dir, work, cname=cname)
            env = _git_env(remote)
            await _git(work, env, "init", "-q", "-b", branch)
            await _git(work, env, "config", "user.name", _COMMIT_NAME)
            await _git(work, env, "config", "user.email", _COMMIT_EMAIL)
            await _git(work, env, "add", "-A")
            await _git(work, env, "commit", "-q", "-m", message)
            sha = (await _git(work, env, "rev-parse", "HEAD")).strip()
            if not ctx.dry_run:
                await _git(work, env, "push", "--force", remote, f"HEAD:{branch}")
        finally:
            shutil.rmtree(work, ignore_errors=True)

        return DeployResult(
            url=_pages_url(repo, cname),
            deployment_id=sha,
            files_uploaded=file_count,
            files_skipped=0,
            bytes_uploaded=total_bytes,
            elapsed_seconds=perf_counter() - started,
        )


def _require_repo(cfg: Mapping[str, object]) -> str:
    """Read and validate the ``repo`` slug, raising :class:`DeployError`."""
    repo = _optional_str(cfg, "repo")
    if not repo:
        raise DeployError("deploy.github-pages: 'repo' must be a non-empty 'owner/name' string")
    if repo.count("/") != 1 or repo.startswith("/") or repo.endswith("/"):
        raise DeployError(f"deploy.github-pages: 'repo' must look like 'owner/name', got {repo!r}")
    return repo


def _optional_str(cfg: Mapping[str, object], key: str) -> str | None:
    """Return ``cfg[key]`` as a string, or ``None`` if absent.

    Raises :class:`DeployError` if the key is present but not a string, so a
    mistyped config (e.g. a list) fails with a clear message rather than a
    confusing ``TypeError`` deep in the git plumbing.
    """
    if key not in cfg:
        return None
    value = cfg[key]
    if not isinstance(value, str):
        raise DeployError(
            f"deploy.github-pages: '{key}' must be a string, got {type(value).__name__}"
        )
    return value


def _str_option(cfg: Mapping[str, object], key: str, default: str) -> str:
    """Like :func:`_optional_str` but substitutes ``default`` when absent/empty."""
    value = _optional_str(cfg, key)
    return value if value else default


def _https_remote(repo: str) -> str:
    """Canonical HTTPS remote URL for an ``owner/name`` slug."""
    return f"https://github.com/{repo}.git"


def _pages_url(repo: str, cname: str | None) -> str:
    """Canonical served URL for the deployed site.

    A custom domain wins. Otherwise a user/org site (``owner/owner.github.io``)
    serves from the domain root, and any other repo serves from the project
    subpath ``owner.github.io/name/``.
    """
    if cname:
        return f"https://{cname}/"
    owner, name = repo.split("/", 1)
    apex = f"{owner.lower()}.github.io"
    if name.lower() == apex:
        return f"https://{apex}/"
    return f"https://{apex}/{name}/"


def _populate_worktree(out_dir: Path, work: Path, *, cname: str | None) -> None:
    """Copy the built site into ``work`` and write Pages control files.

    ``.nojekyll`` is always written so GitHub Pages serves the files verbatim
    instead of running Jekyll (which would drop paths beginning with ``_``).
    ``CNAME`` is written only when a custom domain is configured.
    """
    shutil.copytree(out_dir, work, dirs_exist_ok=True)
    (work / ".nojekyll").write_text("", encoding="utf-8")
    if cname:
        (work / "CNAME").write_text(cname + "\n", encoding="utf-8")


def _git_env(remote: str) -> dict[str, str]:
    """Environment for git subprocesses, adding HTTPS bearer auth if possible.

    When ``GITHUB_TOKEN`` is set and the remote is an HTTPS GitHub URL, an
    ``http.extraheader`` is injected via ``GIT_CONFIG_*`` env vars so the token
    never appears in the remote URL (and therefore never leaks into git's own
    error messages). For SSH remotes or when no token is set, git falls back to
    its normal credential machinery.
    """
    env = dict(os.environ)
    token = env.get("GITHUB_TOKEN")
    if token and remote.startswith("https://"):
        basic = base64.b64encode(f"x-access-token:{token}".encode()).decode("ascii")
        # GIT_CONFIG_{COUNT,KEY_n,VALUE_n} feeds ad-hoc config to every git
        # invocation without writing a file or mutating the user's config.
        env["GIT_CONFIG_COUNT"] = "1"
        env["GIT_CONFIG_KEY_0"] = "http.extraheader"
        env["GIT_CONFIG_VALUE_0"] = f"AUTHORIZATION: basic {basic}"
    return env


async def _git(cwd: Path, env: Mapping[str, str], *args: str) -> str:
    """Run ``git <args>`` in ``cwd`` and return stdout; raise on failure.

    Raises :class:`DeployError` if ``git`` is not installed or the command exits
    non-zero. The error includes the failing subcommand and git's stderr, but
    never the argument list, which could carry the auth header.
    """
    try:
        proc = await asyncio.create_subprocess_exec(
            "git",
            *args,
            cwd=cwd,
            env=dict(env),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError as exc:
        raise DeployError(
            "git is not installed or not on PATH; the github-pages target requires git"
        ) from exc
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        detail = stderr.decode("utf-8", "replace").strip() or "no stderr"
        raise DeployError(f"git {args[0]} failed (exit {proc.returncode}): {detail}")
    return stdout.decode("utf-8", "replace")


def _build_target() -> GitHubPagesTarget:
    """Construct the singleton target (kept separate so tests can import it)."""
    return GitHubPagesTarget()


register(_build_target())


__all__ = ["GitHubPagesTarget"]
