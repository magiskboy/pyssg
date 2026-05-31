"""Unit tests for the Highlight plugin."""

from __future__ import annotations

import unittest
from pathlib import Path

from pyssg.build import Build
from pyssg.config import Config
from pyssg.models import Source
from pyssg_plugins.highlight import Highlight


def make_build() -> Build:
    return Build(config=Config(src=Path("content"), out=Path("public")))


def make_source(content: str) -> Source:
    return Source(path=Path("a.md"), relpath=Path("a.md"), content=content)


def fenced(lang: str, body: str) -> str:
    return f'<pre><code class="language-{lang}">{body}</code></pre>'


class TransformTest(unittest.TestCase):
    def test_known_language_is_highlighted(self) -> None:
        source = make_source(fenced("python", "def f():\n    pass\n"))
        Highlight()._transform(source, make_build())
        self.assertIn('<div class="highlight">', source.content)
        # Pygments wraps keywords in token spans.
        self.assertIn('<span class="k">def</span>', source.content)
        self.assertNotIn('class="language-python"', source.content)

    def test_escaped_entities_are_unescaped_before_highlighting(self) -> None:
        # fenced_code HTML-escapes the body; the plugin must decode it so the
        # lexer sees the real source, then Pygments re-escapes its output.
        source = make_source(fenced("python", "x = a &lt; b &amp; c\n"))
        Highlight()._transform(source, make_build())
        self.assertNotIn("&amp;lt;", source.content)
        self.assertIn("&lt;", source.content)
        self.assertIn("&amp;", source.content)

    def test_unknown_language_is_left_untouched(self) -> None:
        original = fenced("no-such-lang", "whatever\n")
        source = make_source(original)
        Highlight()._transform(source, make_build())
        self.assertEqual(source.content, original)

    def test_multiple_blocks_are_all_highlighted(self) -> None:
        source = make_source(fenced("python", "x = 1\n") + fenced("python", "y = 2\n"))
        Highlight()._transform(source, make_build())
        self.assertEqual(source.content.count('<div class="highlight">'), 2)

    def test_surrounding_html_is_preserved(self) -> None:
        source = make_source(
            "<p>intro</p>" + fenced("python", "x = 1\n") + "<p>end</p>"
        )
        Highlight()._transform(source, make_build())
        self.assertTrue(source.content.startswith("<p>intro</p>"))
        self.assertTrue(source.content.endswith("<p>end</p>"))

    def test_empty_content_is_returned_unchanged(self) -> None:
        source = make_source("")
        result = Highlight()._transform(source, make_build())
        self.assertIs(result, source)
        self.assertEqual(source.content, "")

    def test_content_without_code_blocks_is_unchanged(self) -> None:
        original = "<p>just prose</p>"
        source = make_source(original)
        Highlight()._transform(source, make_build())
        self.assertEqual(source.content, original)

    def test_custom_css_class_is_used(self) -> None:
        source = make_source(fenced("python", "x = 1\n"))
        Highlight(css_class="chroma")._transform(source, make_build())
        self.assertIn('<div class="chroma">', source.content)


class PlainBlockTest(unittest.TestCase):
    def test_plain_block_untouched_by_default(self) -> None:
        original = "<pre><code>x = 1\n</code></pre>"
        source = make_source(original)
        Highlight()._transform(source, make_build())
        self.assertEqual(source.content, original)

    def test_plain_block_highlighted_with_default_lang(self) -> None:
        source = make_source("<pre><code>def f():\n    pass\n</code></pre>")
        Highlight(default_lang="python")._transform(source, make_build())
        self.assertIn('<div class="highlight">', source.content)
        self.assertIn('<span class="k">def</span>', source.content)

    def test_plain_block_highlighted_when_guessing(self) -> None:
        source = make_source("<pre><code>def f():\n    return 1\n</code></pre>")
        Highlight(guess=True)._transform(source, make_build())
        self.assertIn('<div class="highlight">', source.content)


class StylesheetTest(unittest.TestCase):
    def test_collect_registers_highlight_css_global(self) -> None:
        build = make_build()
        Highlight()._collect(build)
        globals_ = build.meta["template_globals"]
        assert isinstance(globals_, dict)
        self.assertIn("highlight_css", globals_)
        css = str(globals_["highlight_css"]())
        self.assertIn(".highlight", css)

    def test_dark_style_emits_prefers_color_scheme_block(self) -> None:
        build = make_build()
        Highlight(dark_style="monokai")._collect(build)
        globals_ = build.meta["template_globals"]
        assert isinstance(globals_, dict)
        css = str(globals_["highlight_css"]())
        self.assertIn("@media (prefers-color-scheme: dark)", css)

    def test_no_dark_style_omits_media_query(self) -> None:
        build = make_build()
        Highlight(dark_style=None)._collect(build)
        globals_ = build.meta["template_globals"]
        assert isinstance(globals_, dict)
        css = str(globals_["highlight_css"]())
        self.assertNotIn("prefers-color-scheme", css)

    def test_stylesheet_targets_custom_css_class(self) -> None:
        build = make_build()
        Highlight(css_class="chroma", dark_style=None)._collect(build)
        globals_ = build.meta["template_globals"]
        assert isinstance(globals_, dict)
        css = str(globals_["highlight_css"]())
        self.assertIn(".chroma", css)


class IntegrationTest(unittest.TestCase):
    def test_highlight_runs_after_markdown_in_builder(self) -> None:
        from pyssg.builder import Builder
        from pyssg_plugins.markdown import Markdown

        builder = Builder(Config(src=Path("content"), out=Path("public")))
        Markdown(extensions=["fenced_code"]).apply(builder)
        Highlight().apply(builder)

        source = Source(
            path=Path("a.md"),
            relpath=Path("a.md"),
            body="```python\ndef f():\n    pass\n```\n",
        )
        build = make_build()
        result = builder.hooks.transform.call(source, build)
        self.assertIn('<div class="highlight">', result.content)
        self.assertIn('<span class="k">def</span>', result.content)


if __name__ == "__main__":
    unittest.main()
