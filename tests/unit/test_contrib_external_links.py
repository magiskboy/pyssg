"""Unit tests for the ``external_links`` contrib plugin."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pyssg.contrib.external_links import external_links, rewrite_external_links


class RewriteExternalLinksTest(unittest.TestCase):
    def _rewrite(self, html: str) -> str:
        return rewrite_external_links(html, target="_blank", rel="noopener noreferrer")

    def test_external_http_link_gets_target_and_rel(self) -> None:
        out = self._rewrite('<a href="http://example.com">x</a>')
        self.assertIn('target="_blank"', out)
        self.assertIn('rel="noopener noreferrer"', out)

    def test_https_link_is_rewritten(self) -> None:
        out = self._rewrite('<a href="https://example.com/page">x</a>')
        self.assertIn('href="https://example.com/page"', out)
        self.assertIn('target="_blank"', out)

    def test_internal_link_is_untouched(self) -> None:
        html = '<a href="/guide/">x</a>'
        self.assertEqual(self._rewrite(html), html)

    def test_relative_link_is_untouched(self) -> None:
        html = '<a href="./other.md">x</a>'
        self.assertEqual(self._rewrite(html), html)

    def test_mailto_is_untouched(self) -> None:
        html = '<a href="mailto:a@b.com">x</a>'
        self.assertEqual(self._rewrite(html), html)

    def test_rewrite_is_idempotent(self) -> None:
        once = self._rewrite('<a href="https://example.com">x</a>')
        twice = self._rewrite(once)
        self.assertEqual(once, twice)

    def test_preexisting_target_is_respected(self) -> None:
        html = '<a class="x" target="_self" href="https://example.com">y</a>'
        self.assertEqual(self._rewrite(html), html)

    def test_custom_target_and_rel(self) -> None:
        out = rewrite_external_links('<a href="https://e.com">x</a>', target="ext", rel="nofollow")
        self.assertIn('target="ext"', out)
        self.assertIn('rel="nofollow"', out)

    def test_factory_returns_named_plugin(self) -> None:
        plugin = external_links()
        self.assertEqual(plugin.name, "external_links")
        self.assertTrue(plugin.cache_version)


class ExternalLinksBuildTest(unittest.TestCase):
    """End-to-end: the plugin rewrites links in a real build via a preset."""

    def setUp(self) -> None:
        self.tmp_path = Path(self.enterContext(tempfile.TemporaryDirectory()))

    def test_external_link_rewritten_in_output(self) -> None:
        from pyssg.cli import build_site

        site = self.tmp_path / "site"
        (site / "content").mkdir(parents=True)
        (site / "content" / "index.md").write_text(
            "---\ntitle: Home\n---\nSee [example](https://example.com) and [guide](./guide.md).\n",
            encoding="utf-8",
        )
        (site / "content" / "guide.md").write_text(
            "---\ntitle: Guide\n---\n# Guide\n", encoding="utf-8"
        )
        (site / "pyssg.config.py").write_text(
            "from __future__ import annotations\n"
            "from pyssg.presets import docs\n"
            "from pyssg.contrib.external_links import external_links\n"
            "config = docs(site={'title': 'T'}, extra_plugins=[external_links()])\n",
            encoding="utf-8",
        )
        build_site(site)
        home = (site / "dist" / "index.html").read_text(encoding="utf-8")
        self.assertIn('href="https://example.com"', home)
        self.assertIn('target="_blank"', home)
        self.assertIn('rel="noopener noreferrer"', home)
        # The internal link to guide resolved to a site URL, not rewritten.
        self.assertIn('href="/guide/"', home)
        self.assertNotIn('href="/guide/" target', home)


if __name__ == "__main__":
    unittest.main()
