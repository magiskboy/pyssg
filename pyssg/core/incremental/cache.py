"""Caches and cache keys.

Two tiers: ``MemoryCache`` (one watch session) and ``FsCache`` (cross-run,
write-through, to survive cold starts on large wikis). Only expensive *pure*
results are cached (rendered HTML, parsed AST, optimized bytes).

The cache key MUST cover every non-pure input that affects the output -- source
content, the pipeline code version, the plugin set + their config, and the
config keys relevant to the phase. Forgetting one would silently serve stale
output, so the rule is: prefer a cache miss over a wrong hit.
Stdlib only.
"""

from __future__ import annotations

import pickle
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, cast

from pyssg.core.incremental.hashing import digest
from pyssg.core.node import Node
from pyssg.core.types import Aspect, Digest, Phase

if TYPE_CHECKING:
    from collections.abc import Callable

    from pyssg.core.build import Build

# Which node aspects feed each phase's computation. Only the phases
# wrapped by cached_or_compute in M4 are listed; more arrive with later phases.
_INPUT_ASPECTS: dict[Phase, tuple[Aspect, ...]] = {
    # A page render reads the source content_html, the source's public meta
    # (title, etc. used by the template), the chosen template, and the URL.
    Phase.RENDER: ("content", "meta", "template", "url"),
}


def input_aspects_of(phase: Phase) -> tuple[Aspect, ...]:
    return _INPUT_ASPECTS.get(phase, ())


class Cache(Protocol):
    """A pure key/value store of computed phase results."""

    def get(self, key: Digest) -> object | None: ...

    def set(self, key: Digest, value: object) -> None: ...


class MemoryCache:
    """In-process cache for a single watch session."""

    __slots__ = ("_store",)

    def __init__(self) -> None:
        self._store: dict[Digest, object] = {}

    def get(self, key: Digest) -> object | None:
        return self._store.get(key)

    def set(self, key: Digest, value: object) -> None:
        self._store[key] = value


class FsCache:
    """Persistent write-through cache backed by a directory.

    A small in-memory layer fronts the disk so repeated hits in one session do
    not re-read files. ``set`` writes both (write-through), so values survive
    across runs to cure cold-start cost on large sites.
    """

    __slots__ = ("_dir", "_memory")

    def __init__(self, cache_dir: Path) -> None:
        self._dir = cache_dir
        self._dir.mkdir(parents=True, exist_ok=True)
        self._memory: dict[Digest, object] = {}

    def _path(self, key: Digest) -> Path:
        return self._dir / f"{key}.pickle"

    def get(self, key: Digest) -> object | None:
        if key in self._memory:
            return self._memory[key]
        path = self._path(key)
        if not path.is_file():
            return None
        value: object = pickle.loads(path.read_bytes())
        self._memory[key] = value
        return value

    def set(self, key: Digest, value: object) -> None:
        self._memory[key] = value
        self._path(key).write_bytes(pickle.dumps(value, protocol=pickle.HIGHEST_PROTOCOL))


def cache_key(node: Node, phase: Phase, build: Build) -> Digest:
    """Cover every non-pure input affecting ``node``'s ``phase`` output."""
    aspect_digests = [node.hashes.get(aspect, "") for aspect in input_aspects_of(phase)]
    return digest(
        node.id,
        phase.name,
        *aspect_digests,
        build.pipeline_version(phase),
        build.plugin_set_version,
        build.relevant_config(phase),
    )


def cached[T](build: Build, key: Digest, compute: Callable[[], T]) -> T:
    """Return a cached result for ``key`` or compute, cache and return it.

    ``compute`` MUST be pure in everything folded into ``key`` -- reading an
    undeclared input here is the classic way to corrupt incremental builds.
    """
    hit = build.cache.get(key)
    if hit is not None:
        build.stats.cache_hits += 1
        return cast("T", hit)
    value = compute()
    build.cache.set(key, value)
    return value


def cached_or_compute[T](build: Build, node: Node, phase: Phase, compute: Callable[[], T]) -> T:
    """Like :func:`cached`, deriving the key from a node's phase inputs."""
    return cached(build, cache_key(node, phase, build), compute)
