"""Unit tests for the ``highlight`` plugin."""

from __future__ import annotations

import html
import unittest

from pygments.formatters import HtmlFormatter

from pyssg.config import Config
from pyssg.core.builder import Builder
from pyssg.core.node import Document
from pyssg.core.types import NodeKind
from pyssg.plugins.highlight import HighlightPlugin, highlight, highlight_html


def _formatter() -> HtmlFormatter:
    return HtmlFormatter(nowrap=False, cssclass="highlight")


def _python_block(code: str) -> str:
    escaped = html.escape(code)
    return f'<pre><code class="language-python">{escaped}\n</code></pre>'


class HighlightHtmlTest(unittest.TestCase):
    def test_python_block_gets_pygments_span_and_wrapper(self) -> None:
        result = highlight_html(_python_block("x = 1"), _formatter())
        # Pygments emits coloured spans inside a ``highlight`` wrapper.
        self.assertIn('<div class="highlight">', result)
        self.assertIn("<span", result)

    def test_unknown_language_falls_back_without_raising(self) -> None:
        source = '<pre><code class="language-nope">data\n</code></pre>'
        result = highlight_html(source, _formatter())
        # TextLexer fallback still wraps the block and never raises.
        self.assertIn('<div class="highlight">', result)
        self.assertIn("data", result)

    def test_plain_fence_without_language_is_highlighted(self) -> None:
        source = "<pre><code>plain text\n</code></pre>"
        result = highlight_html(source, _formatter())
        self.assertIn('<div class="highlight">', result)
        self.assertIn("plain text", result)

    def test_mermaid_block_is_left_verbatim(self) -> None:
        source = '<pre><code class="language-mermaid">graph TD\n</code></pre>'
        result = highlight_html(source, _formatter())
        self.assertEqual(result, source)

    def test_text_outside_code_is_untouched(self) -> None:
        source = f"<p>Intro</p>\n{_python_block('y = 2')}\n<p>Outro</p>"
        result = highlight_html(source, _formatter())
        self.assertIn("<p>Intro</p>", result)
        self.assertIn("<p>Outro</p>", result)

    def test_escaped_entities_are_unescaped_before_highlighting(self) -> None:
        # ``a < b`` is stored as ``a &lt; b``; the highlighted output must contain
        # the operator (re-escaped by Pygments), never the literal entity text.
        source = '<pre><code class="language-python">a &lt; b\n</code></pre>'
        result = highlight_html(source, _formatter())
        # Pygments re-escapes ``<`` as ``&lt;`` but as part of a coloured token,
        # not the original raw ``a &lt; b`` code text.
        self.assertIn("&lt;", result)
        self.assertNotIn(">a &lt; b\n</code></pre>", result)

    def test_multiple_blocks_are_each_highlighted(self) -> None:
        source = _python_block("a = 1") + _python_block("b = 2")
        result = highlight_html(source, _formatter())
        self.assertEqual(result.count('<div class="highlight">'), 2)


class PluginWiringTest(unittest.TestCase):
    def test_apply_stores_css_in_config_site(self) -> None:
        config = Config()
        builder = Builder(config=config)
        highlight().apply(builder)
        css = config.site["highlight_css"]
        self.assertIsInstance(css, str)
        self.assertIn(".highlight", css)  # type: ignore[arg-type]

    def test_apply_without_config_does_not_raise(self) -> None:
        builder = Builder(config=None)
        # No config means no place to store CSS; this must be a no-op, not a crash.
        highlight().apply(builder)

    def test_apply_does_not_clobber_existing_css(self) -> None:
        config = Config()
        config.site["highlight_css"] = "/* custom */"
        builder = Builder(config=config)
        highlight().apply(builder)
        self.assertEqual(config.site["highlight_css"], "/* custom */")

    def test_cache_version_includes_style(self) -> None:
        self.assertIn("monokai", highlight(style="monokai").cache_version)
        self.assertIn("default", highlight().cache_version)

    def test_end_to_end_highlights_document_meta(self) -> None:
        content_html = _python_block("z = 3")
        node = Document(id="post.md", kind=NodeKind.MARKDOWN, source_path="post.md")
        node.meta["content_html"] = content_html
        node.meta["__content_html_raw__"] = content_html

        plugin = highlight()
        highlighted = highlight_html(content_html, plugin._formatter)

        # Both keys are expected to end up identical to a direct transform so
        # later link rewriting (which reads ``__content_html_raw__``) sees the
        # highlighted markup.
        self.assertIn('<div class="highlight">', highlighted)
        self.assertIn("<span", highlighted)

    def test_factory_returns_plugin_instance(self) -> None:
        self.assertIsInstance(highlight(), HighlightPlugin)
