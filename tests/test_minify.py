"""Unit tests for the Minify plugin."""

from __future__ import annotations

import unittest
from pathlib import Path

from pyssg.build import Build
from pyssg.config import Config
from pyssg.models import Output
from pyssg_plugins.minify import Minify, minify_html


class MinifyHtmlTest(unittest.TestCase):
    def test_collapses_whitespace_between_tags(self) -> None:
        self.assertEqual(minify_html("<p>a</p>\n\n  <p>b</p>"), "<p>a</p><p>b</p>")

    def test_collapses_internal_whitespace_runs(self) -> None:
        self.assertEqual(minify_html("<p>a     b</p>"), "<p>a b</p>")

    def test_removes_comments(self) -> None:
        self.assertEqual(minify_html("<p>a</p><!-- note -->"), "<p>a</p>")

    def test_keeps_conditional_comments(self) -> None:
        html = "<!--[if IE]><p>x</p><![endif]-->"
        self.assertIn("[if IE]", minify_html(html))

    def test_preserves_pre_content(self) -> None:
        html = "<pre>def f():\n    return  1</pre>"
        self.assertEqual(minify_html(html), html)

    def test_preserves_code_content(self) -> None:
        html = "<code>a   b</code>"
        self.assertEqual(minify_html(html), html)

    def test_preserves_script(self) -> None:
        html = "<script>let a =  1;\nlet b = 2;</script>"
        self.assertEqual(minify_html(html), html)

    def test_mixed_document(self) -> None:
        html = "<div>\n  <pre>a   b</pre>\n  <span>c   d</span>\n</div>"
        out = minify_html(html)
        self.assertIn("<pre>a   b</pre>", out)
        self.assertIn("<span>c d</span>", out)
        self.assertNotIn("\n", out)

    def test_strips_leading_trailing(self) -> None:
        self.assertEqual(minify_html("  <p>a</p>  "), "<p>a</p>")


class MinifyPluginTest(unittest.TestCase):
    def _build(self, outputs: list[Output]) -> Build:
        build = Build(config=Config(src=Path("c"), out=Path("p")))
        build.outputs = outputs
        return build

    def test_minifies_html_outputs(self) -> None:
        build = self._build([Output(path=Path("a.html"), content="<p>a</p>  <p>b</p>")])
        Minify()._optimize(build)
        self.assertEqual(build.outputs[0].content, "<p>a</p><p>b</p>")

    def test_leaves_non_html_untouched(self) -> None:
        original = "a    b"
        build = self._build([Output(path=Path("data.json"), content=original)])
        Minify()._optimize(build)
        self.assertEqual(build.outputs[0].content, original)

    def test_custom_suffixes(self) -> None:
        build = self._build([Output(path=Path("a.xml"), content="<a>1</a>  <b>2</b>")])
        Minify(suffixes=(".xml",))._optimize(build)
        self.assertEqual(build.outputs[0].content, "<a>1</a><b>2</b>")


if __name__ == "__main__":
    unittest.main()
