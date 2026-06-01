"""Unit tests: graph + edge semantics."""

from __future__ import annotations

import unittest

from pyssg.core.dependency import Connection, Dependency
from pyssg.core.graph import DependencyGraph
from pyssg.core.node import Document, Page
from pyssg.core.types import ConnectionKind, NodeKind, Phase


def _doc(nid: str) -> Document:
    return Document(id=nid, kind=NodeKind.MARKDOWN, source_path=f"{nid}.md")


def _conn(
    src: str,
    dst: str | None,
    kind: ConnectionKind,
    *,
    sensitive_to: frozenset[str] = frozenset(),
    restart_phase: Phase = Phase.RENDER,
    reverse: bool = False,
    request: str = "req",
) -> Connection:
    return Connection(
        src=src,
        dst=dst,
        kind=kind,
        dependency=Dependency(kind="link", request=request),
        sensitive_to=sensitive_to,
        restart_phase=restart_phase,
        reverse=reverse,
    )


class GraphTest(unittest.TestCase):
    def test_add_get_contains_remove(self) -> None:
        g = DependencyGraph()
        a = _doc("a")
        g.add_node(a)
        self.assertIs(g.get("a"), a)
        self.assertIn("a", g)
        self.assertIsNone(g.get("missing"))
        g.remove("a")
        self.assertIsNone(g.get("a"))
        self.assertNotIn("a", g)

    def test_forward_edges_and_kind_filter(self) -> None:
        g = DependencyGraph()
        g.add_node(_doc("a"))
        link = _conn("a", "b", ConnectionKind.LINK, reverse=True)
        embed = _conn("a", "c", ConnectionKind.EMBED, reverse=False)
        g.connect(link)
        g.connect(embed)
        forward = g.out_edges("a")
        self.assertEqual(len(forward), 2)
        self.assertIn(link, forward)
        self.assertIn(embed, forward)
        self.assertEqual(g.out_edges("a", ConnectionKind.LINK), [link])
        self.assertEqual(g.out_edges("a", ConnectionKind.EMBED), [embed])

    def test_in_edges_only_for_reverse_true(self) -> None:
        """in_edges is available only for reverse=True edges."""
        g = DependencyGraph()
        link = _conn("a", "b", ConnectionKind.LINK, reverse=True)  # reverse -> indexed
        embed = _conn("a", "b", ConnectionKind.EMBED, reverse=False)  # NOT indexed
        g.connect(link)
        g.connect(embed)
        self.assertEqual(g.in_edges("b"), [link])
        self.assertEqual(g.in_edges("b", ConnectionKind.EMBED), [])

    def test_edge_semantics_table_link(self) -> None:
        """LINK: sensitive to title/url/exists, restart RENDER, reverse True."""
        g = DependencyGraph()
        link = _conn(
            "a",
            "b",
            ConnectionKind.LINK,
            sensitive_to=frozenset({"title", "url", "exists"}),
            restart_phase=Phase.RENDER,
            reverse=True,
        )
        g.connect(link)
        (incoming,) = g.in_edges("b", ConnectionKind.LINK)
        self.assertEqual(incoming.sensitive_to, frozenset({"title", "url", "exists"}))
        self.assertIs(incoming.restart_phase, Phase.RENDER)
        self.assertIs(incoming.reverse, True)

    def test_placeholder_edge_in_forward_not_reverse(self) -> None:
        """Unresolved edge (dst=None) is a forward placeholder only."""
        g = DependencyGraph()
        placeholder = _conn("a", None, ConnectionKind.LINK, reverse=True)
        g.connect(placeholder)
        self.assertEqual(g.out_edges("a"), [placeholder])
        self.assertEqual(g.in_edges("a"), [])  # nothing points anywhere resolvable yet

    def test_disconnect_removes_both_directions(self) -> None:
        g = DependencyGraph()
        link = _conn("a", "b", ConnectionKind.LINK, reverse=True)
        g.connect(link)
        g.disconnect(link)
        self.assertEqual(g.out_edges("a"), [])
        self.assertEqual(g.in_edges("b"), [])

    def test_remove_node_cleans_incident_edges(self) -> None:
        g = DependencyGraph()
        g.add_node(_doc("a"))
        g.add_node(_doc("b"))
        a_to_b = _conn("a", "b", ConnectionKind.LINK, reverse=True)
        b_to_a = _conn("b", "a", ConnectionKind.LINK, reverse=True)
        g.connect(a_to_b)
        g.connect(b_to_a)
        g.remove("b")
        # b's outgoing edge is gone, and a no longer shows b as an incoming peer.
        self.assertEqual(g.out_edges("b"), [])
        self.assertEqual(g.in_edges("a"), [])
        # a's edge toward the now-removed b is also cleaned from the forward index.
        self.assertEqual(g.out_edges("a"), [])

    def test_connection_of_finds_by_dependency(self) -> None:
        g = DependencyGraph()
        dep = Dependency(kind="wikilink", request="[[Bar]]")
        conn = Connection(src="a", dst="b", kind=ConnectionKind.LINK, dependency=dep, reverse=True)
        g.connect(conn)
        self.assertIs(g.connection_of("a", dep), conn)
        self.assertIsNone(g.connection_of("a", Dependency(kind="x", request="y")))

    def test_page_generated_from_provenance(self) -> None:
        page = Page(id="p", kind=NodeKind.PAGE, url="/p/", generated_from=["a", "b"])
        self.assertEqual(page.url, "/p/")
        self.assertEqual(page.generated_from, ["a", "b"])
        self.assertIs(page.state, Phase.LOAD)

    def test_reverse_flag_drives_in_edges(self) -> None:
        """Reference edge table: only reverse kinds appear in in_edges."""
        for kind, reverse in [
            (ConnectionKind.CONTAINMENT, True),
            (ConnectionKind.LINK, True),
            (ConnectionKind.EMBED, False),
            (ConnectionKind.ASSET_REF, False),
            (ConnectionKind.TEMPLATE, True),
            (ConnectionKind.DATA_REF, True),
            (ConnectionKind.COLLECTION, True),
            (ConnectionKind.GENERATED_FROM, True),
        ]:
            with self.subTest(kind=kind, reverse=reverse):
                g = DependencyGraph()
                conn = _conn("src", "dst", kind, reverse=reverse)
                g.connect(conn)
                self.assertIs((g.in_edges("dst") == [conn]), reverse)
