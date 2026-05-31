"""Unit tests for the Frontmatter plugin (PyYAML-backed)."""

from __future__ import annotations

import unittest
from pathlib import Path

from pyssg.build import Build
from pyssg.config import Config
from pyssg.errors import BuildError
from pyssg.models import Source
from pyssg.schema import FieldSpec, FrontmatterSchema
from pyssg_plugins.frontmatter import Frontmatter


def make_source(raw: str) -> Source:
    return Source(path=Path("a.md"), relpath=Path("a.md"), raw=raw)


def make_build() -> Build:
    return Build(config=Config(src=Path("content"), out=Path("public")))


def parse(raw: str, schema: FrontmatterSchema | None = None) -> Source:
    source = make_source(raw)
    plugin = Frontmatter()
    if schema is not None:
        plugin._schema = schema
    plugin._parse(source, make_build())
    return source


class SplitTest(unittest.TestCase):
    def test_extracts_frontmatter_and_body(self) -> None:
        source = parse("---\ntitle: Hello\n---\nBody text\n")
        self.assertEqual(source.frontmatter, {"title": "Hello"})
        self.assertEqual(source.body, "Body text")

    def test_no_frontmatter_keeps_whole_body(self) -> None:
        source = parse("Just body\nmore\n")
        self.assertEqual(source.frontmatter, {})
        self.assertEqual(source.body, "Just body\nmore\n")

    def test_unclosed_delimiter_is_not_frontmatter(self) -> None:
        source = parse("---\ntitle: Hello\nBody without close\n")
        self.assertEqual(source.frontmatter, {})
        self.assertTrue(source.body.startswith("---"))

    def test_empty_frontmatter_block(self) -> None:
        source = parse("---\n---\nBody\n")
        self.assertEqual(source.frontmatter, {})
        self.assertEqual(source.body, "Body")


class YamlValueTest(unittest.TestCase):
    def test_typed_scalars(self) -> None:
        source = parse("---\ncount: 3\nratio: 1.5\ndraft: true\nempty: null\n---\nx\n")
        self.assertEqual(
            source.frontmatter,
            {"count": 3, "ratio": 1.5, "draft": True, "empty": None},
        )

    def test_inline_list(self) -> None:
        source = parse("---\ntags: [python, ssg, web]\n---\nx\n")
        self.assertEqual(source.frontmatter, {"tags": ["python", "ssg", "web"]})

    def test_block_list(self) -> None:
        source = parse("---\ntags:\n  - python\n  - ssg\n---\nx\n")
        self.assertEqual(source.frontmatter, {"tags": ["python", "ssg"]})

    def test_quoted_colon_value(self) -> None:
        source = parse('---\na: "x: y"\n---\nbody\n')
        self.assertEqual(source.frontmatter, {"a": "x: y"})


class YamlErrorTest(unittest.TestCase):
    def test_syntax_error_reports_file_line(self) -> None:
        # Unbalanced bracket on the second frontmatter line (file line 3).
        raw = "---\ntitle: ok\ntags: [unclosed\n---\nbody\n"
        with self.assertRaises(BuildError) as ctx:
            parse(raw)
        error = ctx.exception
        self.assertIsNotNone(error.location)
        assert error.location is not None
        self.assertEqual(error.location.file, Path("a.md"))
        self.assertIsNotNone(error.location.line)

    def test_non_mapping_is_error(self) -> None:
        raw = "---\n- just\n- a list\n---\nbody\n"
        with self.assertRaises(BuildError) as ctx:
            parse(raw)
        self.assertIn("mapping", ctx.exception.message)


class SchemaValidationTest(unittest.TestCase):
    def test_unquoted_date_is_normalised_to_iso_string(self) -> None:
        # PyYAML parses an unquoted ISO date into a datetime.date; the validator
        # normalises it to a string so date-sorting and RSS (string-based) work.
        schema = FrontmatterSchema()
        schema.declare(FieldSpec("date", type="date"))
        source = parse("---\ndate: 2026-01-31\n---\nbody\n", schema)
        self.assertEqual(source.frontmatter["date"], "2026-01-31")

    def test_invalid_field_reports_file_and_block_line(self) -> None:
        schema = FrontmatterSchema()
        schema.declare(FieldSpec("order", type="int"))
        with self.assertRaises(BuildError) as ctx:
            parse("---\norder: high\n---\nbody\n", schema)
        location = ctx.exception.location
        self.assertIsNotNone(location)
        assert location is not None
        self.assertEqual(location.file, Path("a.md"))


if __name__ == "__main__":
    unittest.main()
