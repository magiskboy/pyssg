"""Unit tests for the ``obsidian`` contrib integration."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pyssg.contrib.obsidian import (
    DEFAULT_VAULT_EXCLUDE,
    _render_embed,
    obsidian_attachments,
    obsidian_plugins,
    section_index_url,
)

# A 1x1 transparent PNG (smallest valid attachment to copy).
_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06"
    b"\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05"
    b"\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


class RenderEmbedTest(unittest.TestCase):
    def test_image_extension_renders_img(self) -> None:
        out = _render_embed("/a/logo.png", "logo.png", None)
        self.assertEqual(out, '<img src="/a/logo.png" alt="logo.png">')

    def test_numeric_alias_becomes_width(self) -> None:
        out = _render_embed("/logo.png", "logo.png", "200")
        self.assertIn('width="200"', out)

    def test_text_alias_becomes_alt(self) -> None:
        out = _render_embed("/logo.png", "logo.png", "Company logo")
        self.assertIn('alt="Company logo"', out)

    def test_non_image_renders_link(self) -> None:
        out = _render_embed("/report.pdf", "report.pdf", None)
        self.assertEqual(out, '<a href="/report.pdf">report.pdf</a>')


class SectionIndexUrlTest(unittest.TestCase):
    def test_section_index_routes_to_dir(self) -> None:
        self.assertEqual(section_index_url("/guide/_index/", "guide/_index.md"), "/guide/")

    def test_root_index_routes_to_root(self) -> None:
        self.assertEqual(section_index_url("/_index/", "_index.md"), "/")

    def test_regular_page_unchanged(self) -> None:
        self.assertEqual(section_index_url("/guide/intro/", "guide/intro.md"), "/guide/intro/")

    def test_missing_source_unchanged(self) -> None:
        self.assertEqual(section_index_url("/x/", None), "/x/")


class ObsidianFactoryTest(unittest.TestCase):
    def test_attachments_plugin_named(self) -> None:
        plugin = obsidian_attachments()
        self.assertEqual(plugin.name, "obsidian_attachments")
        self.assertTrue(plugin.cache_version)

    def test_pipeline_excludes_vault_dirs_and_gates_by_default(self) -> None:
        names = [p.name for p in obsidian_plugins()]
        self.assertIn("directory_loader", names)
        self.assertIn("obsidian_attachments", names)
        self.assertIn("publish_gate", names)
        self.assertIn("transclude", names)
        # Defaults cover Obsidian's own metadata folder and version-control noise.
        self.assertIn(".obsidian", DEFAULT_VAULT_EXCLUDE)
        self.assertIn(".git", DEFAULT_VAULT_EXCLUDE)


_CONFIG = """\
from __future__ import annotations

from pyssg import Config
from pyssg.contrib.obsidian import obsidian_plugins

config = Config(
    base_url="https://example.com",
    site={"title": "Vault"},
    plugins=obsidian_plugins(),
)
"""


class ObsidianVaultBuildTest(unittest.TestCase):
    """End-to-end: a small vault builds with embeds, gating and excludes."""

    def setUp(self) -> None:
        self.tmp_path = Path(self.enterContext(tempfile.TemporaryDirectory()))

    def _build_vault(self) -> Path:
        from pyssg.cli import build_site

        site = self.tmp_path / "site"
        content = site / "content"
        content.mkdir(parents=True)
        (content / "index.md").write_text(
            "---\ntitle: Home\npublish: true\n---\n"
            "Embed image: ![[logo.png]] and note: ![[Note]]\n",
            encoding="utf-8",
        )
        (content / "Note.md").write_text(
            "---\ntitle: Note\npublish: true\n---\nNote body.\n", encoding="utf-8"
        )
        # Denylist is the default: a note with no flag publishes; one marked
        # publish: false stays private.
        (content / "plain.md").write_text("---\ntitle: Plain\n---\nPlain body.\n", encoding="utf-8")
        (content / "private.md").write_text(
            "---\ntitle: Private\npublish: false\n---\nSecret.\n", encoding="utf-8"
        )
        # A Hugo-style section index should route to its directory root.
        (content / "guide").mkdir()
        (content / "guide" / "_index.md").write_text(
            "---\ntitle: Guide\n---\nGuide landing.\n", encoding="utf-8"
        )
        (content / "logo.png").write_bytes(_PNG)
        # Non-asset files that must NOT be copied into the output (a vault that is
        # really a repo can hold code, config and lockfiles).
        (content / "script.py").write_text("print('x')\n", encoding="utf-8")
        (content / "data.json").write_text("{}\n", encoding="utf-8")
        obsidian_dir = content / ".obsidian"
        obsidian_dir.mkdir()
        (obsidian_dir / "app.json").write_text("{}\n", encoding="utf-8")
        (site / "pyssg.config.py").write_text(_CONFIG, encoding="utf-8")
        build_site(site)
        return site / "dist"

    def test_only_asset_files_are_copied(self) -> None:
        dist = self._build_vault()
        self.assertTrue((dist / "logo.png").is_file())
        self.assertFalse((dist / "script.py").exists())
        self.assertFalse((dist / "data.json").exists())

    def test_image_embed_resolved_and_attachment_copied(self) -> None:
        dist = self._build_vault()
        home = (dist / "index.html").read_text(encoding="utf-8")
        self.assertIn('<img src="/logo.png" alt="logo.png">', home)
        # The binary was copied into the output at its vault-relative path.
        self.assertTrue((dist / "logo.png").is_file())

    def test_note_embed_transcluded(self) -> None:
        dist = self._build_vault()
        home = (dist / "index.html").read_text(encoding="utf-8")
        self.assertIn("Note body.", home)
        self.assertNotIn("![[Note]]", home)

    def test_publish_gate_and_vault_exclude(self) -> None:
        dist = self._build_vault()
        pages = {p.relative_to(dist).as_posix() for p in dist.rglob("*.html")}
        self.assertIn("index.html", pages)
        self.assertIn("Note/index.html", pages)
        self.assertIn("plain/index.html", pages)  # denylist: no flag -> published
        self.assertNotIn("private/index.html", pages)  # publish: false -> hidden
        # Nothing from .obsidian leaked into the output.
        self.assertFalse((dist / ".obsidian").exists())

    def test_section_index_routes_to_directory_root(self) -> None:
        dist = self._build_vault()
        self.assertTrue((dist / "guide" / "index.html").is_file())
        self.assertFalse((dist / "guide" / "_index").exists())


if __name__ == "__main__":
    unittest.main()
