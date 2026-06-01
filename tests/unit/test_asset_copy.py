"""Unit tests for the asset_copy plugin."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pyssg.config import Config
from pyssg.core.build import Build
from pyssg.core.builder import Builder
from pyssg.layout import Layout
from pyssg.plugins.asset_copy import copy_assets


def _layout_with_assets(root: Path) -> Layout:
    """A minimal Layout record whose ``assets_dir`` is populated."""
    assets = root / "assets"
    templates = root / "templates"
    assets.mkdir(parents=True)
    templates.mkdir(parents=True)
    return Layout(
        name="test",
        version="0.0.0",
        root=root,
        templates_dir=templates,
        assets_dir=assets,
        default_template="page.html.j2",
    )


def _build(tmp_path: Path, layout: Layout | None) -> Build:
    builder = Builder(config=Config(output_dir="dist"), site_dir=tmp_path)
    builder.layout = layout
    return builder.create_build()


class CopyAssetsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_path = Path(self.enterContext(tempfile.TemporaryDirectory()))

    def test_copy_assets_mirrors_tree(self) -> None:
        layout = _layout_with_assets(self.tmp_path / "layout")
        assert layout.assets_dir is not None  # narrow Optional for type checker
        (layout.assets_dir / "css").mkdir()
        (layout.assets_dir / "css" / "site.css").write_text("body{}")
        (layout.assets_dir / "logo.svg").write_text("<svg/>")

        build = _build(self.tmp_path, layout)
        copy_assets(build)

        out = self.tmp_path / "dist" / "assets"
        self.assertEqual((out / "css" / "site.css").read_text(), "body{}")
        self.assertEqual((out / "logo.svg").read_text(), "<svg/>")

    def test_copy_assets_noop_without_layout(self) -> None:
        build = _build(self.tmp_path, None)
        copy_assets(build)
        self.assertFalse((self.tmp_path / "dist").exists())

    def test_copy_assets_skips_unchanged_files(self) -> None:
        layout = _layout_with_assets(self.tmp_path / "layout")
        assert layout.assets_dir is not None  # narrow Optional for type checker
        src = layout.assets_dir / "a.txt"
        src.write_text("v1")

        build = _build(self.tmp_path, layout)
        copy_assets(build)
        dst = self.tmp_path / "dist" / "assets" / "a.txt"
        mtime = dst.stat().st_mtime_ns

        # An unchanged source must not rewrite the destination file.
        copy_assets(build)
        self.assertEqual(dst.stat().st_mtime_ns, mtime)

    def test_copy_assets_updates_changed_files(self) -> None:
        layout = _layout_with_assets(self.tmp_path / "layout")
        assert layout.assets_dir is not None  # narrow Optional for type checker
        src = layout.assets_dir / "a.txt"
        src.write_text("v1")

        build = _build(self.tmp_path, layout)
        copy_assets(build)

        src.write_text("v2")
        copy_assets(build)
        self.assertEqual((self.tmp_path / "dist" / "assets" / "a.txt").read_text(), "v2")

    def test_copy_assets_leaves_unknown_output_files(self) -> None:
        layout = _layout_with_assets(self.tmp_path / "layout")
        assert layout.assets_dir is not None  # narrow Optional for type checker
        (layout.assets_dir / "a.txt").write_text("v1")

        out_assets = self.tmp_path / "dist" / "assets"
        out_assets.mkdir(parents=True)
        (out_assets / "keep.txt").write_text("user file")

        build = _build(self.tmp_path, layout)
        copy_assets(build)

        # The plugin never deletes files it did not place.
        self.assertEqual((out_assets / "keep.txt").read_text(), "user file")
        self.assertEqual((out_assets / "a.txt").read_text(), "v1")
