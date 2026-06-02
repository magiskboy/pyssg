"""Unit tests for the ``graph`` contrib plugin (document graph view)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from pyssg.config import Config
from pyssg.contrib.graph import (
    _ASSET_CSS_ID,
    _ASSET_JS_ID,
    _JSON_ID,
    _JSON_URL,
    _PAGE_ID,
    GraphConfig,
    GraphPlugin,
    build_graph_data,
    graph,
    inject_local_graph,
    materialize_graph,
)
from pyssg.core.build import Build
from pyssg.core.builder import Builder
from pyssg.core.dependency import Dependency
from pyssg.core.node import Document, Page
from pyssg.core.types import ConnectionKind, NodeKind


def _build(base_url: str = "https://example.com", **site: object) -> Build:
    builder = Builder(config=Config(base_url=base_url, site=site))
    return builder.create_build()


def _add(build: Build, doc_id: str, url: str, **meta: object) -> None:
    """Add a Markdown document plus its derived page (permalink convention)."""
    source = str(meta.pop("source_path", doc_id + ".md"))
    build.graph.add_node(
        Document(id=doc_id, kind=NodeKind.MARKDOWN, source_path=source, meta=dict(meta))
    )
    build.graph.add_node(
        Page(id=f"page:{doc_id}", kind=NodeKind.PAGE, url=url, generated_from=[doc_id])
    )


def _link(build: Build, src: str, dst: str) -> None:
    """Record a resolved LINK edge between two documents."""
    build.create_connection(
        src=src,
        dst=dst,
        kind=ConnectionKind.LINK,
        dependency=Dependency(kind="link", request=f"{src}->{dst}"),
        reverse=True,
    )


def _data(build: Build, cfg: GraphConfig | None = None) -> dict[str, object]:
    return build_graph_data(build, cfg or GraphConfig())


def _nodes(data: dict[str, object]) -> list[dict[str, object]]:
    nodes = data["nodes"]
    assert isinstance(nodes, list)
    return nodes


def _links(data: dict[str, object]) -> list[dict[str, object]]:
    links = data["links"]
    assert isinstance(links, list)
    return links


class NodeExtractionTest(unittest.TestCase):
    def test_nodes_carry_expected_shape(self) -> None:
        build = _build()
        _add(build, "a", "/a/", title="A", tags=["x"])
        node = _nodes(_data(build))[0]
        self.assertEqual(node["id"], "a")
        self.assertEqual(node["title"], "A")
        self.assertEqual(node["url"], "/a/")
        self.assertEqual(node["tags"], ["x"])
        self.assertEqual(node["kind"], "page")
        self.assertIn("group", node)
        self.assertIn("inDegree", node)
        self.assertIn("outDegree", node)

    def test_skips_virtual_pages_without_provenance(self) -> None:
        build = _build()
        _add(build, "a", "/a/", title="A")
        build.graph.add_node(Page(id="page:tagindex", kind=NodeKind.PAGE, url="/tags/"))
        ids = {n["id"] for n in _nodes(_data(build))}
        self.assertEqual(ids, {"a"})

    def test_skips_non_markdown_documents(self) -> None:
        build = _build()
        build.graph.add_node(Document(id="d", kind=NodeKind.DATA, meta={"title": "D"}))
        build.graph.add_node(Page(id="page:d", kind=NodeKind.PAGE, url="/d/", generated_from=["d"]))
        self.assertEqual(_nodes(_data(build)), [])

    def test_title_falls_back_to_url(self) -> None:
        build = _build()
        _add(build, "a", "/a/")
        self.assertEqual(_nodes(_data(build))[0]["title"], "/a/")

    def test_nodes_sorted_by_id(self) -> None:
        build = _build()
        _add(build, "c", "/c/", title="C")
        _add(build, "a", "/a/", title="A")
        _add(build, "b", "/b/", title="B")
        self.assertEqual([n["id"] for n in _nodes(_data(build))], ["a", "b", "c"])


class EdgeExtractionTest(unittest.TestCase):
    def test_directed_link_becomes_edge_with_degrees(self) -> None:
        build = _build()
        _add(build, "a", "/a/", title="A")
        _add(build, "b", "/b/", title="B")
        _link(build, "a", "b")
        data = _data(build)
        self.assertEqual(_links(data), [{"source": "a", "target": "b", "bidirectional": False}])
        by_id = {n["id"]: n for n in _nodes(data)}
        self.assertEqual((by_id["a"]["outDegree"], by_id["a"]["inDegree"]), (1, 0))
        self.assertEqual((by_id["b"]["outDegree"], by_id["b"]["inDegree"]), (0, 1))

    def test_bidirectional_collapses_to_one_edge(self) -> None:
        build = _build()
        _add(build, "a", "/a/", title="A")
        _add(build, "b", "/b/", title="B")
        _link(build, "a", "b")
        _link(build, "b", "a")
        links = _links(_data(build))
        self.assertEqual(links, [{"source": "a", "target": "b", "bidirectional": True}])

    def test_duplicate_links_deduplicated(self) -> None:
        build = _build()
        _add(build, "a", "/a/", title="A")
        _add(build, "b", "/b/", title="B")
        _link(build, "a", "b")
        _link(build, "a", "b")
        self.assertEqual(len(_links(_data(build))), 1)

    def test_unresolved_and_self_and_external_targets_skipped(self) -> None:
        build = _build()
        _add(build, "a", "/a/", title="A")
        _link(build, "a", "a")  # self-link
        _link(build, "a", "missing")  # target not a node
        build.create_connection(
            src="a",
            dst=None,
            kind=ConnectionKind.LINK,
            dependency=Dependency(kind="link", request="broken"),
        )
        self.assertEqual(_links(_data(build)), [])


class FilterTest(unittest.TestCase):
    def test_include_exclude_path_globs(self) -> None:
        build = _build()
        _add(build, "docs/a", "/docs/a/", title="A", source_path="docs/a.md")
        _add(build, "blog/b", "/blog/b/", title="B", source_path="blog/b.md")
        inc = {n["id"] for n in _nodes(_data(build, GraphConfig(include=("docs/*",))))}
        self.assertEqual(inc, {"docs/a"})
        exc = {n["id"] for n in _nodes(_data(build, GraphConfig(exclude=("blog/*",))))}
        self.assertEqual(exc, {"docs/a"})

    def test_tag_filters(self) -> None:
        build = _build()
        _add(build, "a", "/a/", title="A", tags=["keep"])
        _add(build, "b", "/b/", title="B", tags=["drop"])
        inc = {n["id"] for n in _nodes(_data(build, GraphConfig(include_tags=("keep",))))}
        self.assertEqual(inc, {"a"})
        exc = {n["id"] for n in _nodes(_data(build, GraphConfig(exclude_tags=("drop",))))}
        self.assertEqual(exc, {"a"})

    def test_frontmatter_opt_out(self) -> None:
        build = _build()
        _add(build, "a", "/a/", title="A", graph=False)
        _add(build, "b", "/b/", title="B")
        self.assertEqual({n["id"] for n in _nodes(_data(build))}, {"b"})

    def test_drop_orphans(self) -> None:
        build = _build()
        _add(build, "a", "/a/", title="A")
        _add(build, "b", "/b/", title="B")
        _add(build, "lonely", "/lonely/", title="L")
        _link(build, "a", "b")
        ids = {n["id"] for n in _nodes(_data(build, GraphConfig(drop_orphans=True)))}
        self.assertEqual(ids, {"a", "b"})

    def test_min_degree(self) -> None:
        build = _build()
        _add(build, "a", "/a/", title="A")
        _add(build, "b", "/b/", title="B")
        _add(build, "c", "/c/", title="C")
        _link(build, "a", "b")
        _link(build, "a", "c")  # a has degree 2, b and c have degree 1
        ids = {n["id"] for n in _nodes(_data(build, GraphConfig(min_degree=2)))}
        self.assertEqual(ids, {"a"})


class GroupTest(unittest.TestCase):
    def test_group_by_folder(self) -> None:
        build = _build()
        _add(build, "docs/a", "/docs/a/", title="A", source_path="docs/a.md")
        _add(build, "root", "/root/", title="R", source_path="root.md")
        by_id = {n["id"]: n for n in _nodes(_data(build, GraphConfig(group_by="folder")))}
        self.assertEqual(by_id["docs/a"]["group"], "docs")
        self.assertEqual(by_id["root"]["group"], "root")

    def test_group_by_tag(self) -> None:
        build = _build()
        _add(build, "a", "/a/", title="A", tags=["python", "web"])
        _add(build, "b", "/b/", title="B")
        by_id = {n["id"]: n for n in _nodes(_data(build, GraphConfig(group_by="tag")))}
        self.assertEqual(by_id["a"]["group"], "python")
        self.assertEqual(by_id["b"]["group"], "untagged")


class TagNodeTest(unittest.TestCase):
    def test_tag_nodes_promoted_with_edges(self) -> None:
        build = _build()
        _add(build, "a", "/a/", title="A", tags=["python"])
        data = _data(build, GraphConfig(tag_nodes=True))
        by_id = {n["id"]: n for n in _nodes(data)}
        self.assertIn("tag:python", by_id)
        self.assertEqual(by_id["tag:python"]["kind"], "tag")
        self.assertEqual(by_id["tag:python"]["title"], "python")
        self.assertIn({"source": "a", "target": "tag:python", "bidirectional": False}, _links(data))

    def test_tag_nodes_off_by_default(self) -> None:
        build = _build()
        _add(build, "a", "/a/", title="A", tags=["python"])
        ids = {n["id"] for n in _nodes(_data(build))}
        self.assertEqual(ids, {"a"})


class ConfigSerializationTest(unittest.TestCase):
    def test_client_config_subset_serialized(self) -> None:
        build = _build()
        _add(build, "a", "/a/", title="A")
        cfg = GraphConfig(colors={"docs": "#fff"}, local_depth=2, size_min=5, size_max=50)
        config = _data(build, cfg)["config"]
        assert isinstance(config, dict)
        self.assertEqual(config["colors"], {"docs": "#fff"})
        self.assertEqual(config["localDepth"], 2)
        self.assertEqual(config["sizeMin"], 5)
        self.assertEqual(config["sizeMax"], 50)
        # Filtering knobs are server-side only and must not leak to the client.
        self.assertNotIn("include", config)
        self.assertNotIn("minDegree", config)


class DeterminismTest(unittest.TestCase):
    def test_two_builds_are_byte_identical(self) -> None:
        def make() -> str:
            build = _build()
            _add(build, "b", "/b/", title="B", tags=["t"])
            _add(build, "a", "/a/", title="A", tags=["t"])
            _link(build, "a", "b")
            return json.dumps(_data(build, GraphConfig(tag_nodes=True)), sort_keys=True)

        self.assertEqual(make(), make())


class MaterializeTest(unittest.TestCase):
    def _page(self, build: Build, pid: str) -> Page:
        page = build.graph.get(pid)
        assert isinstance(page, Page)
        return page

    def test_emits_json_and_assets_and_global_page(self) -> None:
        build = _build(title="My Site")
        _add(build, "a", "/a/", title="A")
        materialize_graph(build, GraphConfig())

        js = self._page(build, _JSON_ID)
        self.assertEqual(js.url, _JSON_URL)
        self.assertIsNone(js.template)
        payload = json.loads(str(js.meta["content_html"]))
        self.assertEqual(payload["nodes"][0]["id"], "a")

        self.assertIn("cytoscape", str(self._page(build, _ASSET_JS_ID).meta["content_html"]))
        self.assertIn("graph-page", str(self._page(build, _ASSET_CSS_ID).meta["content_html"]))

        page = self._page(build, _PAGE_ID)
        self.assertEqual(page.url, "/graph/")
        html = str(page.meta["content_html"])
        self.assertIn('id="graph-data"', html)
        self.assertIn("My Site - Graph", html)
        self.assertIn("kb-graph", html)

    def test_global_page_disabled_removed(self) -> None:
        build = _build()
        _add(build, "a", "/a/", title="A")
        materialize_graph(build, GraphConfig())
        self.assertIsInstance(build.graph.get(_PAGE_ID), Page)
        materialize_graph(build, GraphConfig(global_page=False))
        self.assertIsNone(build.graph.get(_PAGE_ID))

    def test_idempotent(self) -> None:
        build = _build()
        _add(build, "a", "/a/", title="A")
        materialize_graph(build, GraphConfig())
        first = str(self._page(build, _JSON_ID).meta["content_html"])
        materialize_graph(build, GraphConfig())
        second = str(self._page(build, _JSON_ID).meta["content_html"])
        self.assertEqual(first, second)
        self.assertEqual(len([n for n in build.graph.nodes() if n.id == _JSON_ID]), 1)


class LocalInjectTest(unittest.TestCase):
    def _doc_page(self, build: Build) -> Page:
        _add(build, "a", "/a/", title="A")
        page = build.graph.get("page:a")
        assert isinstance(page, Page)
        page.template = "post.html.j2"
        return page

    def test_injects_panel_into_document_page(self) -> None:
        build = _build()
        page = self._doc_page(build)
        out = inject_local_graph("<html><body><h1>A</h1></body></html>", page, build, GraphConfig())
        self.assertIn('id="kb-local-graph"', out)
        self.assertIn('data-node-id="a"', out)
        self.assertIn("graph.js", out)
        self.assertTrue(out.endswith("</body></html>"))

    def test_placeholder_marker_replaced_in_place(self) -> None:
        build = _build()
        page = self._doc_page(build)
        html = "<html><body><aside><!-- pyssg:local-graph --></aside><main>x</main></body></html>"
        out = inject_local_graph(html, page, build, GraphConfig())
        # The panel lands where the marker was (inside the aside), not at body end.
        self.assertIn('<aside><aside id="kb-local-graph"', out)
        self.assertNotIn("pyssg:local-graph -->", out)
        # The marker appears once, so the panel element is injected exactly once.
        self.assertEqual(out.count('id="kb-local-graph"'), 1)
        # Assets are still loaded before </body>.
        self.assertIn("graph.js", out)

    def test_skips_raw_template_none_pages(self) -> None:
        build = _build()
        page = self._doc_page(build)
        page.template = None
        html = "<html><body>x</body></html>"
        self.assertEqual(inject_local_graph(html, page, build, GraphConfig()), html)

    def test_skips_when_no_body(self) -> None:
        build = _build()
        page = self._doc_page(build)
        html = "just text"
        self.assertEqual(inject_local_graph(html, page, build, GraphConfig()), html)

    def test_per_page_opt_out(self) -> None:
        build = _build()
        page = self._doc_page(build)
        doc = build.graph.get("a")
        assert isinstance(doc, Document)
        doc.meta["graph_local"] = False
        html = "<html><body>x</body></html>"
        self.assertEqual(inject_local_graph(html, page, build, GraphConfig()), html)


class FactoryTest(unittest.TestCase):
    def test_factory_returns_named_plugin(self) -> None:
        plugin = graph()
        self.assertIsInstance(plugin, GraphPlugin)
        self.assertEqual(plugin.name, "graph")
        self.assertTrue(plugin.cache_version)

    def test_factory_passes_options(self) -> None:
        plugin = graph(tag_nodes=True, local_depth=3, colors={"a": "#000"})
        self.assertTrue(plugin.config.tag_nodes)
        self.assertEqual(plugin.config.local_depth, 3)
        self.assertEqual(plugin.config.colors, {"a": "#000"})

    def test_local_graph_off_by_default(self) -> None:
        self.assertFalse(graph().config.local)


class GraphBuildTest(unittest.TestCase):
    """End-to-end: the plugin emits files in a real build via a preset."""

    def setUp(self) -> None:
        self.tmp_path = Path(self.enterContext(tempfile.TemporaryDirectory()))

    def test_graph_files_written_to_output(self) -> None:
        from pyssg.cli import build_site

        site = self.tmp_path / "site"
        (site / "content").mkdir(parents=True)
        (site / "content" / "index.md").write_text(
            "---\ntitle: Home\n---\n# Home\nSee [guide](guide.md).\n", encoding="utf-8"
        )
        (site / "content" / "guide.md").write_text(
            "---\ntitle: Guide\ntags: [howto]\n---\n# Guide\nContent.\n", encoding="utf-8"
        )
        (site / "pyssg.config.py").write_text(
            "from __future__ import annotations\n"
            "from pyssg.presets import docs\n"
            "from pyssg.contrib.graph import graph\n"
            "config = docs(site={'title': 'T'}, extra_plugins=[graph(local=True)])\n"
            "config.base_url = 'https://example.com'\n",
            encoding="utf-8",
        )
        build_site(site)

        data = json.loads((site / "dist" / "graph.json").read_text(encoding="utf-8"))
        ids = {n["id"] for n in data["nodes"]}
        self.assertEqual(ids, {"path:index", "path:guide"})
        self.assertIn(
            {"source": "path:index", "target": "path:guide", "bidirectional": False},
            data["links"],
        )
        # Renderer assets and the global page are emitted.
        self.assertTrue((site / "dist" / "assets" / "graph" / "graph.js").is_file())
        self.assertTrue((site / "dist" / "assets" / "graph" / "graph.css").is_file())
        self.assertTrue((site / "dist" / "graph" / "index.html").is_file())
        # The local-graph panel is injected into a document page.
        guide_html = (site / "dist" / "guide" / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="kb-local-graph"', guide_html)
        self.assertIn('data-node-id="path:guide"', guide_html)


if __name__ == "__main__":
    unittest.main()
