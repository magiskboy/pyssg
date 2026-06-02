"""Provider-agnostic orchestrator for ``pyssg deploy <target>``.

This is the only public entry point a CLI command (or programmatic caller)
needs to invoke a deploy. It strings together the steps that every target
shares so each target stays focused on the one thing it cannot delegate -- the
actual upload to its provider.

Pipeline, in order:

1. Load the site config and pull the ``[deploy.<target>]`` section.
2. Look up the target in the registry; fail clearly if it is unknown.
3. Validate environment variables and required config keys.
4. Build the site (unless ``skip_build`` and ``out_dir`` already exists).
5. Sanity-check the output (unless ``skip_check``): at least one file present.
6. Hash the output tree and compare against the previous deploy record;
   short-circuit with a friendly "no changes" message unless ``force``.
7. If ``dry_run``, report what would be uploaded and stop.
8. Run ``target.deploy(ctx)`` (async); the pipeline blocks on it.
9. Persist the new record and print the friendly summary.

The function is sync; only ``target.deploy`` is async, since real targets will
want concurrent uploads via ``httpx``. The pipeline owns clock access
(``datetime.now``) so the rest of the deploy subsystem stays pure.
"""

from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime
from time import perf_counter
from typing import TYPE_CHECKING

from pyssg.cli.common import build_site, open_cache
from pyssg.config import load_config
from pyssg.deploy import TARGETS, get_target
from pyssg.deploy._hash import file_count_and_size, hash_tree
from pyssg.deploy._output import Console
from pyssg.deploy.base import DeployContext, DeployError, DeployResult
from pyssg.deploy.state import DeployRecord, read_record, write_record

if TYPE_CHECKING:
    from pathlib import Path

    from pyssg.deploy.base import DeployTarget


def run_deploy(
    site_dir: Path,
    target_name: str,
    *,
    dry_run: bool = False,
    force: bool = False,
    skip_build: bool = False,
    skip_check: bool = False,
    targets: dict[str, DeployTarget] | None = None,
    console: Console | None = None,
) -> DeployResult:
    """Run the deploy pipeline for ``target_name`` against ``site_dir``.

    ``targets`` overrides the global registry (used by tests for isolation);
    ``console`` overrides stdout/stderr (also used by tests). Raises
    :class:`DeployError` on any user-actionable failure; the CLI wrapper turns
    that into ``error: ...`` on stderr and a non-zero exit code.
    """
    site_dir = site_dir.resolve()
    out = console if console is not None else Console()
    registry = targets if targets is not None else TARGETS

    out.step("loading config")
    config = load_config(site_dir)
    target_cfg = config.deploy.get(target_name)
    if target_cfg is None:
        raise DeployError(
            f"no deploy.{target_name!r} section in pyssg.config.py; "
            f"add `deploy={{'{target_name}': {{...}}}}` to your config"
        )

    target = get_target(target_name, targets=registry)

    out.step("validating credentials")
    missing_env = [name for name in target.required_env() if name not in os.environ]
    if missing_env:
        raise DeployError(f"missing required environment variable(s): {', '.join(missing_env)}")
    missing_keys = [key for key in target.required_config_keys() if key not in target_cfg]
    if missing_keys:
        raise DeployError(f"deploy.{target_name} is missing key(s): {', '.join(missing_keys)}")
    out.ok("ok")

    out_dir = (site_dir / config.output_dir).resolve()

    if skip_build:
        if not out_dir.is_dir():
            raise DeployError(
                f"--skip-build was set but the output directory {out_dir} does not exist; "
                "run a build first or drop --skip-build"
            )
        out.step("skipping build")
    else:
        out.step("building site")
        started = perf_counter()
        # Full build for deploys: incremental cache exists for `pyssg build`
        # and `serve`, but production uploads must not gamble on cache state.
        stats = build_site(site_dir, open_cache(site_dir, no_cache=True))
        out.ok(f"built {len(stats.changed_outputs)} page(s) in {(perf_counter() - started):.1f}s")

    if not skip_check:
        out.step("checking output")
        file_count, _ = file_count_and_size(out_dir)
        if file_count == 0:
            raise DeployError(f"output directory {out_dir} is empty; nothing to deploy")
        out.ok(f"{file_count} file(s)")

    out.step("computing hash")
    digest = hash_tree(out_dir)
    previous = read_record(site_dir, target_name)
    if previous is not None and previous.hash == digest and not force:
        out.skip(
            f"no changes since {previous.deployment_id} ({previous.url}); pass --force to redeploy"
        )
        return DeployResult(
            url=previous.url,
            deployment_id=previous.deployment_id,
            files_uploaded=0,
            files_skipped=0,
            bytes_uploaded=0,
            elapsed_seconds=0.0,
            skipped=True,
        )

    if dry_run:
        file_count, total_bytes = file_count_and_size(out_dir)
        out.step("dry run")
        out.ok(f"would upload {file_count} file(s) ({total_bytes} bytes) to {target_name}")
        return DeployResult(
            url=previous.url if previous is not None else "",
            deployment_id="dry-run",
            files_uploaded=file_count,
            files_skipped=0,
            bytes_uploaded=total_bytes,
            elapsed_seconds=0.0,
            skipped=False,
        )

    out.step(f"deploying to {target_name}")
    ctx = DeployContext(
        site_dir=site_dir,
        out_dir=out_dir,
        target_name=target_name,
        target_config=target_cfg,
        dry_run=False,
        force=force,
    )
    result = asyncio.run(target.deploy(ctx))

    write_record(
        site_dir,
        DeployRecord(
            target=target_name,
            hash=digest,
            deployment_id=result.deployment_id,
            url=result.url,
            timestamp=datetime.now(UTC).isoformat(timespec="seconds"),
        ),
    )
    out.summary(result)
    return result
