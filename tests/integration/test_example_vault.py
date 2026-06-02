"""Integration test: the shipped Obsidian example vault builds correctly.

Exercises the same path the adapter takes (the ``obsidian`` preset with the vault
as an absolute ``content_dir`` and the output outside the vault), so the example
project that ships with the adapter is guaranteed to keep working.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from pyssg.cli import build_site

_REPO_ROOT = Path(__file__).resolve().parents[2]
_VAULT = _REPO_ROOT / "adapters" / "pyssg-obsidian" / "example-vault"

_CONFIG = """\
from __future__ import annotations

from pyssg.presets import obsidian

config = obsidian(
    site={{"title": "Demo Vault"}},
    base_url="https://example.com",
    content_dir={vault!r},
    output_dir={output!r},
)
"""


class ExampleVaultBuildTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(self.enterContext(tempfile.TemporaryDirectory()))

    def _build(self) -> Path:
        self.assertTrue(_VAULT.is_dir(), f"example vault missing at {_VAULT}")
        site = self.tmp / "site"
        site.mkdir()
        dist = site / "dist"
        (site / "pyssg.config.py").write_text(
            _CONFIG.format(vault=str(_VAULT), output=str(dist)),
            encoding="utf-8",
        )
        build_site(site)
        return dist

    def test_published_pages_and_excludes(self) -> None:
        dist = self._build()
        pages = {p.relative_to(dist).as_posix() for p in dist.rglob("*.html")}
        self.assertIn("index.html", pages)
        self.assertIn("Getting Started/index.html", pages)
        self.assertIn("Concepts/Linking/index.html", pages)
        self.assertIn("Concepts/Embeds/index.html", pages)
        # Private note has no publish flag; .obsidian is vault noise.
        self.assertNotIn("Private/Secret/index.html", pages)
        self.assertFalse((dist / ".obsidian").exists())

    def test_attachment_embed_and_copy(self) -> None:
        dist = self._build()
        home = (dist / "index.html").read_text(encoding="utf-8")
        self.assertIn('<img src="/attachments/architecture.png"', home)
        self.assertTrue((dist / "attachments" / "architecture.png").is_file())

    def test_note_transclusion(self) -> None:
        dist = self._build()
        embeds = (dist / "Concepts" / "Embeds" / "index.html").read_text(encoding="utf-8")
        # The Getting Started note is transcluded into the Embeds page.
        self.assertIn("Open this folder as a vault", embeds)

    def test_wikilinks_resolve(self) -> None:
        dist = self._build()
        home = (dist / "index.html").read_text(encoding="utf-8")
        self.assertIn('href="/Getting Started/"', home)
        self.assertNotIn("broken-link", home)

    def test_manifest_id_matches_docs(self) -> None:
        manifest = json.loads((_VAULT.parent / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["id"], "pyssg-publish")


if __name__ == "__main__":
    unittest.main()
