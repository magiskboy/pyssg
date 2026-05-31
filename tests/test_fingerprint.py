"""Unit tests for the Fingerprint plugin."""

from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from pyssg.build import Build
from pyssg.config import Config
from pyssg.models import Output
from pyssg_plugins.fingerprint import ASSETS, Fingerprint


def make_build(out: Path) -> Build:
    return Build(config=Config(src=out.parent / "content", out=out))


def short_hash(data: bytes, length: int = 8) -> str:
    return hashlib.sha256(data).hexdigest()[:length]


class ManifestTest(unittest.TestCase):
    def test_css_and_js_are_hashed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            assets = root / "assets"
            assets.mkdir()
            (assets / "style.css").write_text("body{}", encoding="utf-8")
            (assets / "app.js").write_text("var x=1", encoding="utf-8")

            build = make_build(root / "public")
            Fingerprint(directory=str(assets))._collect(build)

            manifest = build.meta[ASSETS]
            assert isinstance(manifest, dict)
            css_hash = short_hash(b"body{}")
            self.assertEqual(
                manifest["/assets/style.css"], f"/assets/style.{css_hash}.css"
            )
            self.assertIn("/assets/app.js", manifest)

    def test_hash_changes_with_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            assets = Path(tmp) / "assets"
            assets.mkdir()
            css = assets / "style.css"

            css.write_text("a{}", encoding="utf-8")
            build = make_build(Path(tmp) / "public")
            Fingerprint(directory=str(assets))._collect(build)
            first = build.meta[ASSETS]
            assert isinstance(first, dict)

            css.write_text("b{}", encoding="utf-8")
            build = make_build(Path(tmp) / "public")
            Fingerprint(directory=str(assets))._collect(build)
            second = build.meta[ASSETS]
            assert isinstance(second, dict)

            self.assertNotEqual(first["/assets/style.css"], second["/assets/style.css"])

    def test_non_fingerprinted_files_are_not_in_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            assets = Path(tmp) / "assets"
            assets.mkdir()
            (assets / "logo.svg").write_text("<svg/>", encoding="utf-8")

            build = make_build(Path(tmp) / "public")
            Fingerprint(directory=str(assets))._collect(build)
            self.assertEqual(build.meta[ASSETS], {})

    def test_nested_path_keeps_parent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            assets = Path(tmp) / "assets"
            (assets / "css").mkdir(parents=True)
            (assets / "css" / "main.css").write_text("x{}", encoding="utf-8")

            build = make_build(Path(tmp) / "public")
            Fingerprint(directory=str(assets))._collect(build)
            manifest = build.meta[ASSETS]
            assert isinstance(manifest, dict)
            self.assertIn("/assets/css/main.css", manifest)
            self.assertTrue(
                manifest["/assets/css/main.css"].startswith("/assets/css/main.")
            )

    def test_custom_extensions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            assets = Path(tmp) / "assets"
            assets.mkdir()
            (assets / "icon.png").write_bytes(b"\x89PNG")

            build = make_build(Path(tmp) / "public")
            Fingerprint(directory=str(assets), extensions=(".png",))._collect(build)
            manifest = build.meta[ASSETS]
            assert isinstance(manifest, dict)
            self.assertIn("/assets/icon.png", manifest)

    def test_missing_directory_is_noop(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            build = make_build(Path(tmp) / "public")
            Fingerprint(directory=str(Path(tmp) / "nope"))._collect(build)
            self.assertEqual(build.meta[ASSETS], {})


class RewriteTest(unittest.TestCase):
    def collect(self, build: Build, css: bytes = b"body{}") -> str:
        # Returns the hashed url for /assets/style.css.
        return f"/assets/style.{short_hash(css)}.css"

    def setup(self, html: str, css: bytes = b"body{}") -> Build:
        tmp = tempfile.mkdtemp()
        assets = Path(tmp) / "assets"
        assets.mkdir()
        (assets / "style.css").write_bytes(css)
        build = make_build(Path(tmp) / "public")
        plugin = Fingerprint(directory=str(assets))
        plugin._collect(build)
        build.outputs.append(Output(path=Path("index.html"), content=html))
        plugin._optimize(build)
        return build

    def test_rewrites_reference_in_html(self) -> None:
        build = self.setup('<link href="/assets/style.css">')
        hashed = self.collect(build)
        self.assertIn(hashed, build.outputs[0].content)
        self.assertNotIn('href="/assets/style.css"', build.outputs[0].content)

    def test_does_not_corrupt_longer_path(self) -> None:
        # A ".css.map" sibling must not be partially rewritten.
        build = self.setup('<a href="/assets/style.css.map">')
        self.assertIn("/assets/style.css.map", build.outputs[0].content)

    def test_only_rewrites_html_outputs(self) -> None:
        tmp = tempfile.mkdtemp()
        assets = Path(tmp) / "assets"
        assets.mkdir()
        (assets / "style.css").write_bytes(b"body{}")
        build = make_build(Path(tmp) / "public")
        plugin = Fingerprint(directory=str(assets))
        plugin._collect(build)
        build.outputs.append(Output(path=Path("feed.xml"), content="/assets/style.css"))
        plugin._optimize(build)
        # Non-HTML outputs are left untouched.
        self.assertEqual(build.outputs[0].content, "/assets/style.css")

    def test_noop_without_manifest(self) -> None:
        build = make_build(Path(tempfile.mkdtemp()) / "public")
        build.meta[ASSETS] = {}
        build.outputs.append(Output(path=Path("i.html"), content="/assets/x.css"))
        Fingerprint()._optimize(build)
        self.assertEqual(build.outputs[0].content, "/assets/x.css")


class AssetGlobalTest(unittest.TestCase):
    def test_registers_asset_global(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            assets = Path(tmp) / "assets"
            assets.mkdir()
            (assets / "style.css").write_text("a{}", encoding="utf-8")
            build = make_build(Path(tmp) / "public")
            Fingerprint(directory=str(assets))._collect(build)

            globals_ = build.meta["template_globals"]
            assert isinstance(globals_, dict)
            self.assertIn("asset", globals_)

    def test_asset_global_can_be_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            assets = Path(tmp) / "assets"
            assets.mkdir()
            (assets / "style.css").write_text("a{}", encoding="utf-8")
            build = make_build(Path(tmp) / "public")
            Fingerprint(directory=str(assets), asset_global=False)._collect(build)
            self.assertNotIn("template_globals", build.meta)


class EmitTest(unittest.TestCase):
    def test_writes_hashed_and_verbatim_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            assets = root / "assets"
            assets.mkdir()
            (assets / "style.css").write_text("body{}", encoding="utf-8")
            (assets / "logo.svg").write_text("<svg/>", encoding="utf-8")
            out = root / "public"

            build = make_build(out)
            plugin = Fingerprint(directory=str(assets))
            plugin._collect(build)
            plugin._emit(build)

            css_hash = short_hash(b"body{}")
            self.assertEqual(
                (out / "assets" / f"style.{css_hash}.css").read_text(), "body{}"
            )
            # Verbatim, original name preserved.
            self.assertEqual((out / "assets" / "logo.svg").read_text(), "<svg/>")
            # The un-hashed css must not be emitted.
            self.assertFalse((out / "assets" / "style.css").exists())

    def test_custom_dest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            assets = root / "static"
            assets.mkdir()
            (assets / "app.js").write_text("x", encoding="utf-8")
            out = root / "public"

            build = make_build(out)
            plugin = Fingerprint(directory=str(assets), dest="s")
            plugin._collect(build)
            manifest = build.meta[ASSETS]
            assert isinstance(manifest, dict)
            self.assertIn("/s/app.js", manifest)
            plugin._emit(build)
            js_hash = short_hash(b"x")
            self.assertTrue((out / "s" / f"app.{js_hash}.js").exists())

    def test_emit_noop_without_plan(self) -> None:
        build = make_build(Path(tempfile.mkdtemp()) / "public")
        Fingerprint()._emit(build)  # no _collect ran
        self.assertFalse(build.config.out.exists())


if __name__ == "__main__":
    unittest.main()
