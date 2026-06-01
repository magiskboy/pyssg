"""Directory loader plugin.

Walks ``content_dir`` and turns it into graph nodes: a ``DIRECTORY`` document for
each folder and a content node for each file (delegated to the ``load_node``
hook, so the markdown plugin owns ``.md`` handling). It wires CONTAINMENT edges
(parent -> child) which later milestones use for navigation/membership.

Pure: the tree walk is sorted for deterministic output (two builds of the same
tree are byte-identical).
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from pyssg.core.dependency import Dependency
from pyssg.core.node import Document
from pyssg.core.types import ConnectionKind, NodeId, NodeKind, Phase

if TYPE_CHECKING:
    from pyssg.core.build import Build
    from pyssg.core.builder import Builder

_ROOT_ID: NodeId = "dir:."


def _dir_id(rel: Path) -> NodeId:
    posix = rel.as_posix()
    return _ROOT_ID if posix == "." else f"dir:{posix}"


class DirectoryLoaderPlugin:
    """Discovers the content tree into directory + file nodes."""

    name = "directory_loader"
    cache_version = "1.0.0"

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
        # Sorted walk: parents sort before their children, so a child's parent
        # directory node always exists by the time we link CONTAINMENT.
        for path in sorted(content_root.rglob("*")):
            rel = path.relative_to(content_root)
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


def directory_loader() -> DirectoryLoaderPlugin:
    """Factory used in ``pyssg.config.py``."""
    return DirectoryLoaderPlugin()
