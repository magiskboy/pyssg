"""Unit tests for the frontmatter schema registry and validator."""

from __future__ import annotations

import io
import unittest
from contextlib import redirect_stderr
from datetime import date, datetime
from pathlib import Path

from pyssg.errors import BuildError
from pyssg.models import Source
from pyssg.schema import FieldSpec, FrontmatterSchema


def source_with(**frontmatter: object) -> Source:
    return Source(
        path=Path("a.md"), relpath=Path("a.md"), frontmatter=dict(frontmatter)
    )


def validate(spec: FieldSpec, value: object) -> Source:
    schema = FrontmatterSchema()
    schema.declare(spec)
    source = source_with(**{spec.name: value})
    schema.validate(source, block_line=2)
    return source


class FieldSpecTest(unittest.TestCase):
    def test_rejects_unknown_type(self) -> None:
        with self.assertRaises(ValueError):
            FieldSpec("x", type="number")

    def test_rejects_unknown_severity(self) -> None:
        with self.assertRaises(ValueError):
            FieldSpec("x", severity="fatal")


class DeclareTest(unittest.TestCase):
    def test_same_type_declared_twice_is_fine(self) -> None:
        schema = FrontmatterSchema()
        schema.declare(FieldSpec("date", type="date"))
        schema.declare(FieldSpec("date", type="date"))
        self.assertEqual(len(schema.specs()), 1)

    def test_conflicting_type_is_authoring_error(self) -> None:
        schema = FrontmatterSchema()
        schema.declare(FieldSpec("date", type="date"))
        with self.assertRaises(BuildError) as ctx:
            schema.declare(FieldSpec("date", type="str"))
        self.assertEqual(ctx.exception.stage, "config")


class TypeCheckTest(unittest.TestCase):
    def test_str_accepts_text_and_coerces_number(self) -> None:
        self.assertEqual(validate(FieldSpec("t"), "hi").frontmatter["t"], "hi")
        self.assertEqual(validate(FieldSpec("t"), 2026).frontmatter["t"], "2026")

    def test_int_accepts_int_and_coerces_digit_string(self) -> None:
        self.assertEqual(validate(FieldSpec("o", type="int"), 5).frontmatter["o"], 5)
        self.assertEqual(validate(FieldSpec("o", type="int"), "7").frontmatter["o"], 7)

    def test_int_rejects_boolean(self) -> None:
        with self.assertRaises(BuildError) as ctx:
            validate(FieldSpec("o", type="int"), True)
        self.assertIn("whole number", ctx.exception.message)

    def test_bool_coerces_words(self) -> None:
        self.assertIs(
            validate(FieldSpec("d", type="bool"), "false").frontmatter["d"], False
        )
        self.assertIs(
            validate(FieldSpec("d", type="bool"), "yes").frontmatter["d"], True
        )

    def test_bool_rejects_other_text(self) -> None:
        with self.assertRaises(BuildError):
            validate(FieldSpec("d", type="bool"), "maybe")

    def test_date_normalises_to_iso_string(self) -> None:
        self.assertEqual(
            validate(FieldSpec("date", type="date"), date(2026, 1, 31)).frontmatter[
                "date"
            ],
            "2026-01-31",
        )
        self.assertEqual(
            validate(
                FieldSpec("date", type="date"), datetime(2026, 1, 31, 9, 0)
            ).frontmatter["date"],
            "2026-01-31",
        )
        self.assertEqual(
            validate(FieldSpec("date", type="date"), "2026-01-31").frontmatter["date"],
            "2026-01-31",
        )

    def test_date_rejects_unparseable(self) -> None:
        with self.assertRaises(BuildError) as ctx:
            validate(FieldSpec("date", type="date"), "January first")
        self.assertIn("date like", ctx.exception.message)

    def test_list_accepts_list_and_wraps_scalar(self) -> None:
        self.assertEqual(
            validate(FieldSpec("tags", type="list"), ["a", "b"]).frontmatter["tags"],
            ["a", "b"],
        )
        self.assertEqual(
            validate(FieldSpec("tags", type="list"), "python").frontmatter["tags"],
            ["python"],
        )
        self.assertEqual(
            validate(FieldSpec("tags", type="list"), None).frontmatter["tags"], []
        )

    def test_list_without_coerce_rejects_scalar(self) -> None:
        with self.assertRaises(BuildError):
            validate(FieldSpec("tags", type="list", coerce=False), "python")

    def test_mapping_rejects_non_dict(self) -> None:
        with self.assertRaises(BuildError):
            validate(FieldSpec("m", type="mapping"), "x")


class SeverityAndRequiredTest(unittest.TestCase):
    def test_required_missing_field_errors(self) -> None:
        schema = FrontmatterSchema()
        schema.declare(FieldSpec("title", required=True))
        with self.assertRaises(BuildError) as ctx:
            schema.validate(source_with(), block_line=2)
        self.assertIn("missing required", ctx.exception.message)

    def test_warn_severity_does_not_raise(self) -> None:
        schema = FrontmatterSchema()
        schema.declare(FieldSpec("title", required=True, severity="warn"))
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            schema.validate(source_with(), block_line=2)
        self.assertIn("missing required", stderr.getvalue())

    def test_error_carries_block_location(self) -> None:
        schema = FrontmatterSchema()
        schema.declare(FieldSpec("order", type="int"))
        with self.assertRaises(BuildError) as ctx:
            schema.validate(source_with(order="oops"), block_line=2)
        location = ctx.exception.location
        self.assertIsNotNone(location)
        assert location is not None
        self.assertEqual(location.line, 2)
        self.assertEqual(location.file, Path("a.md"))


class UnknownKeysTest(unittest.TestCase):
    def test_undeclared_keys_are_left_untouched(self) -> None:
        schema = FrontmatterSchema()
        schema.declare(FieldSpec("order", type="int"))
        source = source_with(order=1, anything={"nested": [1, 2]}, custom="kept")
        schema.validate(source, block_line=2)
        self.assertEqual(source.frontmatter["anything"], {"nested": [1, 2]})
        self.assertEqual(source.frontmatter["custom"], "kept")


if __name__ == "__main__":
    unittest.main()
