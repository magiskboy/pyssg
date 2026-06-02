"""Persistent last-deploy state under ``.pyssg-cache/deploy/<target>.json``.

The pipeline writes one small JSON file per target after every successful
deploy; the next run reads it back to answer "is the current output identical
to what we last pushed?". The file is intentionally human-readable and stable:
the user can inspect it, ``cat`` it, or delete it to force a redeploy.

This module is stdlib-only. The on-disk format is a tiny dict so we can add
fields later without breaking older entries; unknown keys are tolerated on
read.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

# Cache layout mirrors the rest of the cache (lives next to the build cache, so
# ``pyssg clean`` already removes it). Kept separate from the build cache files
# to avoid any cross-contamination if either side changes its format.
_CACHE_DIRNAME = ".pyssg-cache"
_DEPLOY_SUBDIR = "deploy"


@dataclass(frozen=True, slots=True)
class DeployRecord:
    """A snapshot of the most recent successful deploy for one target.

    ``hash`` is the output-tree hash at the moment of upload; ``deployment_id``
    and ``url`` are whatever the target returned. ``timestamp`` is an ISO-8601
    UTC string captured by the pipeline (the pipeline owns clock access, so
    this module stays pure: callers pass the value in).
    """

    target: str
    hash: str
    deployment_id: str
    url: str
    timestamp: str


def _record_path(site_dir: Path, target_name: str) -> Path:
    return site_dir / _CACHE_DIRNAME / _DEPLOY_SUBDIR / f"{target_name}.json"


def read_record(site_dir: Path, target_name: str) -> DeployRecord | None:
    """Return the last-deploy record for ``target_name`` or ``None`` if absent.

    Returns ``None`` (rather than raising) on a missing or unreadable file: the
    caller treats a missing record as "never deployed", which is the same
    user-visible behavior, and a corrupted file would otherwise block any
    further deploy with no useful recovery path beyond deleting the cache.
    """
    path = _record_path(site_dir, target_name)
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(raw, dict):
        return None
    try:
        return DeployRecord(
            target=str(raw["target"]),
            hash=str(raw["hash"]),
            deployment_id=str(raw["deployment_id"]),
            url=str(raw["url"]),
            timestamp=str(raw["timestamp"]),
        )
    except KeyError:
        return None


def write_record(site_dir: Path, record: DeployRecord) -> None:
    """Persist ``record`` for ``record.target`` under the cache directory.

    The parent directories are created on demand. The JSON is sorted and
    pretty-printed so diffs (e.g. when the cache is committed by accident) stay
    minimal and reviewable.
    """
    path = _record_path(site_dir, record.target)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(asdict(record), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
