"""Pure ignore-matching helper for the watcher.

The watcher must drop editor temp noise and anything matching the configured
``ignore`` globs *before* emitting an :class:`~pyssg.watch.events.FsEvent`, so
the rebuild loop never sees output-dir churn or ``*.swp`` flicker (which would
otherwise risk a build->event->build loop). Matching is a small pure function so
it can be unit-tested in isolation; it never touches the filesystem.
"""

from __future__ import annotations

import fnmatch
from pathlib import PurePosixPath

__all__ = ["ALWAYS_IGNORE", "is_ignored"]

# Editor/OS temp noise that is always dropped regardless of config.
# Globs ending in ``/`` denote a directory whose subtree is ignored.
ALWAYS_IGNORE: tuple[str, ...] = (
    "*.swp",
    "*~",
    ".DS_Store",
    ".obsidian/",
    ".git/",
    "node_modules/",
)


def _normalize(path: str) -> str:
    """Return ``path`` with OS separators normalised to ``/`` for matching.

    Using POSIX-style parts keeps the glob semantics identical across platforms
    so a single ``ignore`` list behaves the same on macOS, Linux, and Windows.
    """
    return str(PurePosixPath(path.replace("\\", "/")))


def _matches_one(path: str, parts: tuple[str, ...], pattern: str) -> bool:
    """Whether a single glob ``pattern`` matches ``path``/its ``parts``.

    A trailing ``/`` makes the pattern a directory matcher: it matches when any
    path segment equals the directory name (the path lies inside that dir). A
    pattern without a separator is matched against each individual segment as
    well as the whole path, so ``*.tmp`` catches ``a/b/c.tmp``. Patterns that
    contain a separator are matched against the full normalised path.
    """
    if pattern.endswith("/"):
        directory = pattern[:-1]
        return any(fnmatch.fnmatch(part, directory) for part in parts)

    if "/" in pattern:
        return fnmatch.fnmatch(path, pattern)

    if fnmatch.fnmatch(path, pattern):
        return True
    return any(fnmatch.fnmatch(part, pattern) for part in parts)


def is_ignored(path: str, ignore: list[str]) -> bool:
    """Whether ``path`` should be ignored by the watcher.

    Combines the always-on temp/VCS/output noise globs (:data:`ALWAYS_IGNORE`)
    with the user-supplied ``ignore`` list. Matching is case-sensitive and
    separator-agnostic.

    Args:
        path: A filesystem path (absolute or relative; any separator style).
        ignore: Extra globs from config (``WatchOptions.ignore``), e.g.
            ``["*.tmp", "output/"]``.

    Returns:
        ``True`` if any always-ignore or configured glob matches.
    """
    normalized = _normalize(path)
    parts = PurePosixPath(normalized).parts
    return any(_matches_one(normalized, parts, pattern) for pattern in (*ALWAYS_IGNORE, *ignore))
