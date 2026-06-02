"""Unit tests for the internal Markdown link resolver."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pyssg.plugins.link_resolver import _target_id


class TargetIdTest(unittest.TestCase):
    def test_relative_ascii_link(self) -> None:
        self.assertEqual(_target_id("guide/index.md", "intro.md"), "path:guide/intro")

    def test_parent_relative_link(self) -> None:
        self.assertEqual(_target_id("guide/intro.md", "../about.md"), "path:about")

    def test_percent_encoded_href_is_decoded(self) -> None:
        # Obsidian stores links to spaced/Unicode files URL-encoded; the node id
        # uses the real path, so the href must be decoded to match.
        self.assertEqual(
            _target_id("index.md", "Web%20development/T%E1%BB%91i%20%C6%B0u.md"),
            "path:Web development/Tối ưu",
        )


_CONFIG = """\
from __future__ import annotations

from pyssg import Config
from pyssg.plugins import directory_loader, frontmatter, markdown, permalink, link_resolver, render

config = Config(
    plugins=[
        directory_loader(),
        frontmatter(),
        markdown(),
        permalink(),
        link_resolver(),
        render(),
    ],
)
"""


class EncodedLinkBuildTest(unittest.TestCase):
    """End-to-end: a percent-encoded .md link resolves to the target permalink."""

    def setUp(self) -> None:
        self.tmp = Path(self.enterContext(tempfile.TemporaryDirectory()))

    def test_encoded_link_resolves_to_html_url(self) -> None:
        from pyssg.cli import build_site

        site = self.tmp / "site"
        content = site / "content"
        content.mkdir(parents=True)
        # Link target with spaces + Vietnamese, referenced via its encoded href.
        (content / "index.md").write_text(
            "---\ntitle: Home\n---\nSee [perf](T%E1%BB%91i%20%C6%B0u.md).\n",
            encoding="utf-8",
        )
        (content / "Tối ưu.md").write_text("---\ntitle: Perf\n---\nBody.\n", encoding="utf-8")
        (site / "pyssg.config.py").write_text(_CONFIG, encoding="utf-8")
        build_site(site)

        home = (site / "dist" / "index.html").read_text(encoding="utf-8")
        # Resolved to the target page URL, not left as a dead .md link.
        self.assertIn('href="/Tối ưu/"', home)
        self.assertNotIn(".md", home)


if __name__ == "__main__":
    unittest.main()
