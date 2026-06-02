"""Regression tests for the raw-emit render contract (issue #61).

A page with ``template=None`` must be emitted *verbatim* (its ``content_html``),
with no layout wrapping, even on a site that has a theme. The summarizer plugins
(sitemap, rss, llms) rely on this. The bug these guard against was hidden because
no test exercised a raw page *through a layout* -- so this builds a real themed
site and checks the emitted bytes.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path


class RawPageRenderTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_path = Path(self.enterContext(tempfile.TemporaryDirectory()))

    def _build(self) -> Path:
        from pyssg.cli import build_site

        site = self.tmp_path / "site"
        (site / "content").mkdir(parents=True)
        (site / "content" / "index.md").write_text(
            "---\ntitle: Home\n---\n# Home\nWelcome.\n", encoding="utf-8"
        )
        (site / "content" / "guide.md").write_text(
            "---\ntitle: Guide\nexcerpt: How to\n---\n# Guide\nSteps.\n", encoding="utf-8"
        )
        (site / "pyssg.config.py").write_text(
            "from __future__ import annotations\n"
            "from pyssg.presets import docs\n"
            "from pyssg.contrib.llms import llms\n"
            "config = docs(site={'title': 'T', 'description': 'D'}, "
            "extra_plugins=[llms()])\n"
            "config.base_url = 'https://example.com'\n",
            encoding="utf-8",
        )
        build_site(site)
        return site / "dist"

    def test_summarizer_pages_are_raw_through_a_layout(self) -> None:
        dist = self._build()
        sitemap = (dist / "sitemap.xml").read_text(encoding="utf-8")
        feed = (dist / "feed.xml").read_text(encoding="utf-8")
        llms_txt = (dist / "llms.txt").read_text(encoding="utf-8")
        llms_full = (dist / "llms-full.txt").read_text(encoding="utf-8")

        # Raw: starts with the format's own preamble, never the HTML layout.
        self.assertTrue(sitemap.startswith("<?xml"))
        self.assertTrue(feed.startswith("<?xml"))
        self.assertTrue(llms_txt.startswith("# T"))
        for raw in (sitemap, feed, llms_txt, llms_full):
            self.assertNotIn("<!doctype html>", raw)

    def test_regular_page_is_still_wrapped_in_the_layout(self) -> None:
        # Control: a normal document page must still go through the theme.
        home = (self._build() / "index.html").read_text(encoding="utf-8")
        self.assertIn("<!doctype html>", home.lower())


if __name__ == "__main__":
    unittest.main()
