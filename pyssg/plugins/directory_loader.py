"""Directory loader plugin.

Walks ``content_dir`` and turns it into graph nodes: a ``DIRECTORY`` document for
each folder and a content node for each file (delegated to the ``load_node``
hook, so the markdown plugin owns ``.md`` handling). It wires CONTAINMENT edges
(parent -> child) which later milestones use for navigation/membership.

Optional ``include`` / ``exclude`` glob filters restrict which paths enter the
graph. Both match the path *relative to* ``content_dir`` with
:meth:`pathlib.PurePosixPath.full_match` semantics (``**`` spans any number of
segments), so ``.obsidian`` drops that whole subtree and ``**/*.tmp`` drops temp
files at any depth. ``exclude`` wins over ``include``; excluding a directory
prunes everything beneath it; ``include`` (when given) restricts *files* only --
directories are still traversed so their included children are reached. With
neither filter the behavior is unchanged (every file a loader claims is loaded).

Pure: the tree walk is sorted for deterministic output (two builds of the same
tree are byte-identical) and the filters are static config. The filter config is
folded into ``cache_version`` so changing ``include`` / ``exclude`` busts the
cache.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING

from pyssg.core.dependency import Dependency
from pyssg.core.node import Document
from pyssg.core.types import ConnectionKind, NodeId, NodeKind, Phase

if TYPE_CHECKING:
    from collections.abc import Sequence

    from pyssg.core.build import Build
    from pyssg.core.builder import Builder

_ROOT_ID: NodeId = "dir:."


def _dir_id(rel: Path) -> NodeId:
    posix = rel.as_posix()
    return _ROOT_ID if posix == "." else f"dir:{posix}"


def _matches_any(rel: Path, patterns: tuple[str, ...]) -> bool:
    """Whether ``rel`` (a content-relative path) matches any glob in ``patterns``."""
    pure = PurePosixPath(rel.as_posix())
    return any(pure.full_match(pattern) for pattern in patterns)


class DirectoryLoaderPlugin:
    """Discovers the content tree into directory + file nodes.

    ``include`` / ``exclude`` are glob patterns (relative to ``content_dir``)
    that filter the walk; see the module docstring for their precise semantics.
    """

    name = "directory_loader"

    def __init__(
        self,
        *,
        include: Sequence[str] | None = None,
        exclude: Sequence[str] | None = None,
    ) -> None:
        # Sorted tuples give a deterministic, config-sensitive cache key: changing
        # the filters must bust cached output that depended on the old membership.
        self._include = tuple(sorted(include)) if include else ()
        self._exclude = tuple(sorted(exclude)) if exclude else ()
        self.cache_version = f"1.1.0:i={','.join(self._include)}:e={','.join(self._exclude)}"

    def apply(self, builder: Builder) -> None:
        @builder.hooks.make.tap(self.name)
        async def _make(build: Build) -> None:
            self._discover(build)

    def _discover(self, build: Build) -> None:
        builder = build.builder
        config = builder.config
        if config is None:
            return
        content_root = (builder.site_dir / config.content_dir).resolve()
        if not content_root.is_dir():
            return

        build.graph.add_node(Document(id=_ROOT_ID, kind=NodeKind.DIRECTORY, source_path="."))
        # Directory subtrees pruned by ``exclude``; a child sorts after its parent
        # so the prefix is always recorded before its descendants are visited.
        pruned: set[str] = set()
        # Sorted walk: parents sort before their children, so a child's parent
        # directory node always exists by the time we link CONTAINMENT.
        for path in sorted(content_root.rglob("*")):
            rel = path.relative_to(content_root)
            rel_posix = rel.as_posix()
            if any(rel_posix == d or rel_posix.startswith(f"{d}/") for d in pruned):
                continue  # inside an excluded directory subtree
            if self._exclude and _matches_any(rel, self._exclude):
                if path.is_dir():
                    pruned.add(rel_posix)
                continue
            parent_id = _dir_id(rel.parent)
            if path.is_dir():
                node_id = _dir_id(rel)
                build.graph.add_node(
                    Document(
                        id=node_id,
                        kind=NodeKind.DIRECTORY,
                        source_path=rel.as_posix(),
                    )
                )
                self._contain(build, parent_id, node_id)
            elif path.is_file():
                if self._include and not _matches_any(rel, self._include):
                    continue  # not in the include allowlist
                node = build.hooks.load_node.call(str(path))
                if node is None:
                    continue  # no loader claimed this file (e.g. unknown type)
                node.id = f"path:{rel.with_suffix('').as_posix()}"
                node.source_path = rel.as_posix()
                build.graph.add_node(node)
                self._contain(build, parent_id, node.id)

    def _contain(self, build: Build, parent_id: NodeId, child_id: NodeId) -> None:
        build.create_connection(
            src=parent_id,
            dst=child_id,
            kind=ConnectionKind.CONTAINMENT,
            dependency=Dependency(kind="containment", request=child_id),
            sensitive_to=frozenset({"membership"}),
            restart_phase=Phase.GENERATE,
            reverse=True,
        )


def directory_loader(
    *,
    include: Sequence[str] | None = None,
    exclude: Sequence[str] | None = None,
) -> DirectoryLoaderPlugin:
    """Factory used in ``pyssg.config.py``.

    ``include`` / ``exclude`` are optional content-relative glob filters; see the
    module docstring for their semantics. Omitting both keeps the default
    behavior (load every file a loader claims).
    """
    return DirectoryLoaderPlugin(include=include, exclude=exclude)
