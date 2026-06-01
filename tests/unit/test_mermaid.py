"""Unit tests for the ``mermaid`` client-side plugin."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pyssg.config import Config
from pyssg.core.build import Build
from pyssg.core.builder import Builder
from pyssg.core.node import Document
from pyssg.core.types import NodeKind
from pyssg.plugins.mermaid import MermaidPlugin, clientside_mermaid, mermaid

# Markup markdown-it emits for a ```mermaid fence: the diagram text is HTML-escaped
# (``-->`` becomes ``--&gt;``) and a trailing newline is kept inside the block.
_MERMAID_IN = '<pre><code class="language-mermaid">graph TD; A--&gt;B\n</code></pre>'
_MERMAID_OUT = '<pre class="mermaid">graph TD; A-->B\n</pre>'


class ClientsideMermaidTest(unittest.TestCase):
    def test_mermaid_block_is_rewritten_and_unescaped(self) -> None:
        result = clientside_mermaid(_MERMAID_IN)
        self.assertEqual(result, _MERMAID_OUT)
        # The arrow must be the literal characters mermaid.js expects, not entities.
        self.assertIn("A-->B", result)
        self.assertNotIn("&gt;", result)

    def test_non_mermaid_code_block_left_unchanged(self) -> None:
        python = '<pre><code class="language-python">x = 1 &lt; 2\n</code></pre>'
        self.assertEqual(clientside_mermaid(python), python)

    def test_plain_code_block_left_unchanged(self) -> None:
        plain = "<pre><code>just text &amp; more\n</code></pre>"
        self.assertEqual(clientside_mermaid(plain), plain)

    def test_multiple_mermaid_blocks_all_convert(self) -> None:
        first = '<pre><code class="language-mermaid">graph LR; X--&gt;Y\n</code></pre>'
        second = (
            '<pre><code class="language-mermaid">sequenceDiagram\nA-&gt;&gt;B: hi\n</code></pre>'
        )
        result = clientside_mermaid(first + "\n" + second)
        self.assertEqual(
            result,
            (
                '<pre class="mermaid">graph LR; X-->Y\n</pre>'
                "\n"
                '<pre class="mermaid">sequenceDiagram\nA->>B: hi\n</pre>'
            ),
        )

    def test_text_outside_code_blocks_untouched(self) -> None:
        document = (
            "<h1>Title</h1>\n"
            "<p>Some &amp; prose with --&gt; arrows.</p>\n"
            f"{_MERMAID_IN}\n"
            "<p>Trailing text.</p>"
        )
        result = clientside_mermaid(document)
        # Only the mermaid block changed; surrounding HTML (including its entities)
        # is preserved verbatim.
        self.assertIn("<h1>Title</h1>", result)
        self.assertIn("<p>Some &amp; prose with --&gt; arrows.</p>", result)
        self.assertIn("<p>Trailing text.</p>", result)
        self.assertIn(_MERMAID_OUT, result)

    def test_mixed_mermaid_and_other_blocks(self) -> None:
        python = '<pre><code class="language-python">y = 2\n</code></pre>'
        result = clientside_mermaid(_MERMAID_IN + python)
        self.assertEqual(result, _MERMAID_OUT + python)

    def test_empty_input_returns_empty(self) -> None:
        self.assertEqual(clientside_mermaid(""), "")


def _build(tmp_path: Path) -> Build:
    builder = Builder(config=Config(output_dir="dist"), site_dir=tmp_path)
    build = builder.create_build()
    mermaid().apply(builder)
    builder.hooks.this_compilation.call(build)
    return build


class MermaidPluginTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_path = Path(self.enterContext(tempfile.TemporaryDirectory()))

    def test_parse_hook_updates_both_html_keys(self) -> None:
        build = _build(self.tmp_path)
        node = Document(id="doc.md", kind=NodeKind.MARKDOWN, source_path="doc.md")
        node.meta["content_html"] = _MERMAID_IN
        node.meta["__content_html_raw__"] = _MERMAID_IN

        build.hooks.parse.call(node)

        self.assertEqual(node.meta["content_html"], _MERMAID_OUT)
        self.assertEqual(node.meta["__content_html_raw__"], _MERMAID_OUT)

    def test_parse_hook_ignores_non_markdown(self) -> None:
        build = _build(self.tmp_path)
        node = Document(id="d.dat", kind=NodeKind.DATA, source_path="d.dat")
        node.meta["content_html"] = _MERMAID_IN

        build.hooks.parse.call(node)

        # A non-markdown node is gated out, so its HTML is left untouched.
        self.assertEqual(node.meta["content_html"], _MERMAID_IN)

    def test_plugin_exposes_name_and_factory(self) -> None:
        plugin = mermaid()
        self.assertIsInstance(plugin, MermaidPlugin)
        self.assertEqual(plugin.name, "mermaid")
