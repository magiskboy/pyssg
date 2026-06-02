"""Deterministic hash of a built output tree.

Used by the pipeline to decide whether the freshly built ``out_dir`` is byte-
identical to the previous deploy; if so the upload is skipped (unless
``--force``). The hash MUST be:

* Path-stable: the same content under a renamed root must produce the same
  digest (we hash relative paths).
* Order-stable: directory iteration order varies across filesystems, so we
  sort entries explicitly.
* Content-aware: the same set of paths with different file bodies must
  produce a different digest.

The format mixes the relative path and its body digest before re-hashing so
that renaming a file (same content, different path) is correctly seen as a
change. The output is a 64-char hex sha256 string suitable for use as an opaque
identifier.

Stdlib only -- this is core to the periphery and must not pull extra deps.
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


# Read files in 1 MiB chunks: large enough to amortize the syscall cost on big
# binary assets, small enough to keep memory usage bounded for big sites.
_READ_CHUNK = 1 << 20


def _file_sha256(path: Path) -> str:
    """Hex sha256 of a file's bytes, streamed in fixed-size chunks."""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while chunk := fh.read(_READ_CHUNK):
            h.update(chunk)
    return h.hexdigest()


def hash_tree(root: Path) -> str:
    """Hex sha256 of the file tree under ``root``.

    Symlinks and special files are skipped; only regular files contribute. The
    function is pure: it does not read clocks or environment, so calling it
    twice on the same tree returns the same value.
    """
    if not root.exists():
        return hashlib.sha256(b"").hexdigest()

    entries: list[tuple[str, str]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        rel = path.relative_to(root).as_posix()
        entries.append((rel, _file_sha256(path)))

    tree = hashlib.sha256()
    for rel, digest in entries:
        # The NUL separators make this injection-safe: filenames can contain
        # spaces, colons, slashes, but not NUL on any supported filesystem.
        tree.update(rel.encode("utf-8"))
        tree.update(b"\x00")
        tree.update(digest.encode("ascii"))
        tree.update(b"\x00")
    return tree.hexdigest()


def file_count_and_size(root: Path) -> tuple[int, int]:
    """Number of regular files under ``root`` and their total size in bytes.

    Used by ``--dry-run`` and the friendly summary; cheap because we already
    walked the tree once when hashing but kept this independent for callers
    that do not need the full hash.
    """
    if not root.exists():
        return (0, 0)
    count = 0
    total = 0
    for path in root.rglob("*"):
        if not path.is_file() or path.is_symlink():
            continue
        count += 1
        total += path.stat().st_size
    return (count, total)
