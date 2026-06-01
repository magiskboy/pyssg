"""Unit + end-to-end tests for the ``apidoc`` contrib plugin."""

from __future__ import annotations

import ast
import tempfile
import unittest
from pathlib import Path

from pyssg.contrib.apidoc import (
    _format_signature,  # signature helper (tested directly)
    apidoc,
    extract_package,
    parse_docstring,
    render_docstring_markdown,
)

_FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "apidoc_pkg"


def _func(src: str) -> ast.FunctionDef | ast.AsyncFunctionDef:
    node = ast.parse(src).body[0]
    assert isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    return node


class SignatureTest(unittest.TestCase):
    def test_plain_and_annotated_defaults(self) -> None:
        sig = _format_signature(_func("def f(a, b: int = 3): ..."))
        self.assertEqual(sig, "(a, b: int = 3)")

    def test_unannotated_default_has_no_spaces(self) -> None:
        self.assertEqual(_format_signature(_func("def f(a=1): ...")), "(a=1)")

    def test_posonly_kwonly_varargs(self) -> None:
        sig = _format_signature(_func("def f(a, /, b, *args, c, **kw): ..."))
        self.assertEqual(sig, "(a, /, b, *args, c, **kw)")

    def test_keyword_only_marker_without_vararg(self) -> None:
        self.assertEqual(_format_signature(_func("def f(a, *, b): ...")), "(a, *, b)")

    def test_return_annotation(self) -> None:
        sig = _format_signature(_func("def f(x: str) -> bool: ..."))
        self.assertEqual(sig, "(x: str) -> bool")


class GoogleParserTest(unittest.TestCase):
    def test_args_returns_raises(self) -> None:
        doc = parse_docstring(
            "Summary line.\n\n"
            "Args:\n"
            "    name (str): Who to greet.\n"
            "    loud: Shout it.\n\n"
            "Returns:\n"
            "    str: The greeting.\n\n"
            "Raises:\n"
            "    ValueError: If empty.\n"
        )
        self.assertEqual(doc.summary, "Summary line.")
        self.assertEqual(
            [(p.name, p.type, p.description) for p in doc.params],
            [("name", "str", "Who to greet."), ("loud", "", "Shout it.")],
        )
        self.assertEqual(doc.returns[0].type, "str")
        self.assertEqual(doc.returns[0].description, "The greeting.")
        self.assertEqual(doc.raises[0].name, "ValueError")

    def test_other_section_kept_verbatim(self) -> None:
        doc = parse_docstring("S.\n\nExample:\n    do_thing()\n")
        self.assertEqual(doc.sections, (("Example", "do_thing()"),))


class NumpyParserTest(unittest.TestCase):
    def test_parameters_and_returns(self) -> None:
        doc = parse_docstring(
            "Clamp.\n\n"
            "Parameters\n----------\n"
            "value : float\n    The value.\n"
            "low : float\n    Lower bound.\n\n"
            "Returns\n-------\n"
            "float\n    The result.\n"
        )
        self.assertEqual(doc.summary, "Clamp.")
        self.assertEqual(
            [(p.name, p.type) for p in doc.params], [("value", "float"), ("low", "float")]
        )
        self.assertEqual(doc.returns[0].type, "float")
        self.assertEqual(doc.returns[0].description, "The result.")


class RestParserTest(unittest.TestCase):
    def test_params_types_returns_raises(self) -> None:
        doc = parse_docstring(
            "Read.\n\n"
            ":param count: How many.\n"
            ":type count: int\n"
            ":returns: The records.\n"
            ":rtype: list\n"
            ":raises IOError: On failure.\n"
        )
        self.assertEqual(doc.summary, "Read.")
        self.assertEqual(
            (doc.params[0].name, doc.params[0].type, doc.params[0].description),
            ("count", "int", "How many."),
        )
        self.assertEqual(doc.returns[0].type, "list")
        self.assertEqual(doc.returns[0].description, "The records.")
        self.assertEqual(
            (doc.raises[0].name, doc.raises[0].description), ("IOError", "On failure.")
        )


class RenderTest(unittest.TestCase):
    def test_params_render_as_html_table(self) -> None:
        md = render_docstring_markdown(parse_docstring("S.\n\nArgs:\n    x (int): the x.\n"))
        self.assertIn("<table>", md)
        self.assertIn("<code>x</code>", md)
        self.assertIn("<code>int</code>", md)
        # No blank line inside the table block (so CommonMark keeps it raw HTML).
        table = md[md.index("<table>") : md.index("</table>")]
        self.assertNotIn("\n\n", table)

    def test_html_is_escaped(self) -> None:
        md = render_docstring_markdown(parse_docstring("S.\n\nArgs:\n    x: a < b & c.\n"))
        self.assertIn("a &lt; b &amp; c.", md)
        self.assertNotIn("a < b & c", md)

    def test_unparseable_docstring_is_all_summary(self) -> None:
        doc = parse_docstring("Just a plain sentence with no sections.")
        self.assertEqual(doc.summary, "Just a plain sentence with no sections.")
        self.assertEqual(doc.params, ())


class ExtractPackageTest(unittest.TestCase):
    def test_module_set_excludes_private(self) -> None:
        names = [name for name, _ in extract_package(_FIXTURE)]
        self.assertEqual(
            names,
            [
                "apidoc_pkg",
                "apidoc_pkg.io_utils",
                "apidoc_pkg.mathx",
                "apidoc_pkg.sub",
                "apidoc_pkg.sub.helpers",
            ],
        )
        self.assertNotIn("apidoc_pkg._private", names)

    def test_private_module_and_member_appear_when_requested(self) -> None:
        names = [name for name, _ in extract_package(_FIXTURE, include_private=True)]
        self.assertIn("apidoc_pkg._private", names)
        helpers = dict(extract_package(_FIXTURE, include_private=True))["apidoc_pkg.sub.helpers"]
        self.assertIn("Box._secret", helpers)

    def test_init_always_shown_dunder_hidden(self) -> None:
        helpers = dict(extract_package(_FIXTURE))["apidoc_pkg.sub.helpers"]
        self.assertIn("Box.__init__", helpers)

    def test_single_file_root(self) -> None:
        result = extract_package(_FIXTURE / "mathx.py")
        self.assertEqual([name for name, _ in result], ["mathx"])

    def test_extraction_is_deterministic(self) -> None:
        self.assertEqual(extract_package(_FIXTURE), extract_package(_FIXTURE))

    def test_factory_returns_named_plugin(self) -> None:
        plugin = apidoc(package="pkg")
        self.assertEqual(plugin.name, "apidoc")
        self.assertTrue(plugin.cache_version)


class ApiDocBuildTest(unittest.TestCase):
    """End-to-end: the plugin emits reference pages into a real build."""

    def setUp(self) -> None:
        self.tmp_path = Path(self.enterContext(tempfile.TemporaryDirectory()))

    def _make_site(self) -> Path:
        site = self.tmp_path / "site"
        (site / "content").mkdir(parents=True)
        (site / "content" / "index.md").write_text(
            "---\ntitle: Home\n---\n# Home\n", encoding="utf-8"
        )
        # A small package to document, outside content_dir.
        pkg = site / "mypkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text(
            '"""My package."""\n\n\n'
            "def add(a: int, b: int) -> int:\n"
            '    """Add two numbers.\n\n'
            "    Args:\n"
            "        a: First.\n"
            "        b: Second.\n\n"
            "    Returns:\n"
            "        int: The sum.\n"
            '    """\n'
            "    return a + b\n",
            encoding="utf-8",
        )
        (site / "pyssg.config.py").write_text(
            "from __future__ import annotations\n"
            "from pyssg.presets import docs\n"
            "from pyssg.contrib.apidoc import apidoc\n"
            "config = docs(site={'title': 'T'}, extra_plugins=[apidoc(package='mypkg')])\n",
            encoding="utf-8",
        )
        return site

    def test_reference_page_emitted(self) -> None:
        from pyssg.cli import build_site

        site = self._make_site()
        build_site(site)
        page = site / "dist" / "references" / "mypkg" / "index.html"
        self.assertTrue(page.is_file())
        html = page.read_text(encoding="utf-8")
        self.assertIn("My package.", html)
        self.assertIn("Add two numbers.", html)
        self.assertIn("<table>", html)  # the params table survived rendering
        self.assertIn("The sum.", html)

    def test_references_section_in_nav(self) -> None:
        from pyssg.cli import build_site

        site = self._make_site()
        build_site(site)
        home = (site / "dist" / "index.html").read_text(encoding="utf-8")
        # The nav groups by first URL segment, so the page sits under /references/.
        self.assertIn("/references/mypkg/", home)

    def test_incremental_equals_full_build(self) -> None:
        from pyssg.cli import build_site

        site = self._make_site()
        build_site(site)
        first = (site / "dist" / "references" / "mypkg" / "index.html").read_text("utf-8")
        # A second full build must be byte-identical (determinism / no clock).
        build_site(site)
        second = (site / "dist" / "references" / "mypkg" / "index.html").read_text("utf-8")
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
