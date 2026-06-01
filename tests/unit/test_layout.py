"""Unit tests for layout package loading and validation."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pyssg.core.errors import LayoutError
from pyssg.layout import Layout, load_layout


def _make_layout(
    root: Path,
    *,
    manifest: str | None = 'name = "docs"\nversion = "0.1.0"\ndefault_template = "page.html.j2"\n',
    template: str | None = "page.html.j2",
    with_assets: bool = False,
) -> Path:
    """Build a layout package on disk and return its directory.

    Any piece can be omitted (pass None) to exercise the failure paths.
    """
    root.mkdir(parents=True, exist_ok=True)
    if manifest is not None:
        (root / "layout.toml").write_text(manifest, encoding="utf-8")
    if template is not None:
        templates = root / "templates"
        templates.mkdir(exist_ok=True)
        (templates / template).write_text("<html></html>", encoding="utf-8")
    if with_assets:
        (root / "assets").mkdir(exist_ok=True)
    return root


class LoadLayoutTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_path = Path(self.enterContext(tempfile.TemporaryDirectory()))

    def test_load_layout_fields(self) -> None:
        root = _make_layout(self.tmp_path / "docs", with_assets=True)
        layout = load_layout(root)
        self.assertIsInstance(layout, Layout)
        self.assertEqual(layout.name, "docs")
        self.assertEqual(layout.version, "0.1.0")
        self.assertEqual(layout.root, root)
        self.assertEqual(layout.templates_dir, root / "templates")
        self.assertEqual(layout.assets_dir, root / "assets")
        self.assertEqual(layout.default_template, "page.html.j2")

    def test_load_layout_assets_none_when_absent(self) -> None:
        root = _make_layout(self.tmp_path / "docs", with_assets=False)
        layout = load_layout(root)
        self.assertIsNone(layout.assets_dir)

    def test_load_layout_name_defaults_to_dir_name(self) -> None:
        root = _make_layout(
            self.tmp_path / "blog",
            manifest='version = "2.0.0"\n',  # no name / default_template keys
        )
        layout = load_layout(root)
        self.assertEqual(layout.name, "blog")
        self.assertEqual(layout.version, "2.0.0")
        self.assertEqual(layout.default_template, "page.html.j2")  # default applied

    def test_load_layout_version_default(self) -> None:
        root = _make_layout(self.tmp_path / "docs", manifest='name = "docs"\n')
        layout = load_layout(root)
        self.assertEqual(layout.version, "0.0.0")

    def test_load_layout_missing_directory(self) -> None:
        with self.assertRaisesRegex(LayoutError, "does not exist"):
            load_layout(self.tmp_path / "nope")

    def test_load_layout_missing_manifest(self) -> None:
        root = _make_layout(self.tmp_path / "docs", manifest=None)
        with self.assertRaisesRegex(LayoutError, r"missing layout\.toml"):
            load_layout(root)

    def test_load_layout_missing_templates_dir(self) -> None:
        root = _make_layout(self.tmp_path / "docs", template=None)
        with self.assertRaisesRegex(LayoutError, "missing a templates/ directory"):
            load_layout(root)

    def test_load_layout_default_template_file_missing(self) -> None:
        # templates/ exists (with a different file) but the declared default is absent.
        root = _make_layout(
            self.tmp_path / "docs",
            manifest='name = "docs"\ndefault_template = "missing.html.j2"\n',
            template="page.html.j2",
        )
        with self.assertRaisesRegex(LayoutError, "default template not found"):
            load_layout(root)

    def test_load_layout_rejects_non_string_manifest_value(self) -> None:
        root = _make_layout(self.tmp_path / "docs", manifest="name = 123\n")
        with self.assertRaisesRegex(LayoutError, "must be a string"):
            load_layout(root)
