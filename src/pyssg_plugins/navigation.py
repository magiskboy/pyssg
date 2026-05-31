"""Navigation plugin: build named menus and optional sequential links.

Taps ``collect`` last (after Permalink, Collections and Listing) so every page
already has a URL. It writes ``build.meta["menus"][name]`` -- a list of
``NavNode`` -- which templates render as a menu, sidebar or footer.

Three ways to populate a menu, covering the three use cases:

- ``mode="folder"``      -- a hierarchical tree mirroring the folder structure
  (docs sidebar). An ``index.md`` describes its folder node; other pages are
  leaves. Section folders without an ``index.md`` become non-link headers.
- ``mode="frontmatter"`` -- a flat, ordered list of the pages that declare
  ``menu: <name>`` (top menu for a blog or company site).
- ``items=[...]``        -- an explicit tree supplied in the config (full
  control / override).

Siblings are ordered by frontmatter ``order`` then title. With
``sequential=True`` the menu is flattened in order and adjacent pages are
linked through ``source.meta["prev"|"next"]`` (docs prev/next).
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from pyssg.build import Build
from pyssg.builder import Builder
from pyssg.content import (
    URL,
    NavNode,
    is_draft,
    is_generated,
    menus,
    page_ref,
)
from pyssg.models import Source
from pyssg.schema import FieldSpec

Predicate = Callable[[Source], bool]

# Navigation runs after Permalink (-200), Collections (-100) and Listing (0).
_COLLECT_STAGE = 100


class Navigation:
    def __init__(
        self,
        *,
        menu: str = "main",
        mode: str = "folder",
        include: Predicate | None = None,
        items: list[dict[str, object]] | None = None,
        sequential: bool = False,
    ) -> None:
        self._menu = menu
        self._mode = mode
        self._include = include
        self._items = items
        self._sequential = sequential

    def apply(self, builder: Builder) -> None:
        # Declared here too: the site() preset uses Navigation without Collections.
        builder.schema.declare(FieldSpec("order", type="int", example="10"))
        builder.hooks.collect.tap("Navigation", self._collect, stage=_COLLECT_STAGE)

    def _collect(self, build: Build) -> None:
        if self._items is not None:
            tree = [_node_from_dict(item) for item in self._items]
        else:
            pages = [
                source
                for source in build.sources
                if not is_generated(source)
                and not is_draft(source)
                and (self._include is None or self._include(source))
            ]
            if self._mode == "frontmatter":
                tree = self._frontmatter_menu(pages)
            else:
                tree = self._folder_tree(pages)

        menus(build)[self._menu] = tree
        if self._sequential:
            _link_sequential(tree)

    def _frontmatter_menu(self, pages: list[Source]) -> list[NavNode]:
        nodes = [
            NavNode(
                title=_nav_title(page, _titleize(page.relpath.stem)),
                url=_url(page),
                order=_order(page),
                source=page,
            )
            for page in pages
            if self._in_menu(page)
        ]
        nodes.sort(key=lambda node: (node.order, node.title))
        return nodes

    def _in_menu(self, page: Source) -> bool:
        declaration = page.frontmatter.get("menu")
        if isinstance(declaration, str):
            return declaration == self._menu
        if isinstance(declaration, list):
            return self._menu in [str(item) for item in declaration]
        return False

    def _folder_tree(self, pages: list[Source]) -> list[NavNode]:
        root: list[NavNode] = []
        folders: dict[tuple[str, ...], NavNode] = {}

        def ensure_folder(parts: tuple[str, ...]) -> NavNode | None:
            if not parts:
                return None
            if parts in folders:
                return folders[parts]
            node = NavNode(title=_titleize(parts[-1]), url="")
            folders[parts] = node
            parent = ensure_folder(parts[:-1])
            (parent.children if parent else root).append(node)
            return node

        for page in pages:
            relpath = page.relpath
            parent_dir = relpath.parent
            folder_parts = () if parent_dir == Path(".") else parent_dir.parts

            if relpath.stem == "index":
                node = ensure_folder(folder_parts)
                if node is None:
                    continue  # the root index.md is the home page, not a menu item
                node.url = _url(page)
                node.title = _nav_title(page, node.title)
                node.order = _order(page)
                node.source = page
            else:
                leaf = NavNode(
                    title=_nav_title(page, _titleize(relpath.stem)),
                    url=_url(page),
                    order=_order(page),
                    source=page,
                )
                parent = ensure_folder(folder_parts)
                (parent.children if parent else root).append(leaf)

        _sort_tree(root)
        return root


def _link_sequential(tree: list[NavNode]) -> None:
    flat: list[Source] = []

    def walk(nodes: list[NavNode]) -> None:
        for node in nodes:
            if node.source is not None:
                flat.append(node.source)
            walk(node.children)

    walk(tree)
    for index, source in enumerate(flat):
        if index > 0:
            source.meta["prev"] = page_ref(flat[index - 1])
        if index < len(flat) - 1:
            source.meta["next"] = page_ref(flat[index + 1])


def _sort_tree(nodes: list[NavNode]) -> None:
    nodes.sort(key=lambda node: (node.order, node.title))
    for node in nodes:
        _sort_tree(node.children)


def _node_from_dict(data: dict[str, object]) -> NavNode:
    title = data.get("title")
    url = data.get("url")
    order = data.get("order")
    children = data.get("children")

    child_nodes: list[NavNode] = []
    if isinstance(children, list):
        child_nodes = [_node_from_dict(d) for d in children if isinstance(d, dict)]

    return NavNode(
        title=str(title) if title is not None else "",
        url=str(url) if url is not None else "",
        order=order if isinstance(order, int) else 0,
        children=child_nodes,
    )


def _url(source: Source) -> str:
    value = source.meta.get(URL)
    return str(value) if value is not None else ""


def _nav_title(source: Source, default: str) -> str:
    value = source.frontmatter.get("nav_title") or source.frontmatter.get("title")
    return str(value) if value else default


def _order(source: Source) -> int:
    value = source.frontmatter.get("order")
    return value if isinstance(value, int) else 0


def _titleize(name: str) -> str:
    return name.replace("-", " ").replace("_", " ").title()
