"""Unit tests for frontmatter splitting, including malformed-YAML tolerance."""

from __future__ import annotations

import unittest

from pyssg.plugins.frontmatter import split_frontmatter


class SplitFrontmatterTest(unittest.TestCase):
    def test_no_frontmatter_returns_raw(self) -> None:
        meta, body = split_frontmatter("# Title\n\nBody.\n")
        self.assertEqual(meta, {})
        self.assertEqual(body, "# Title\n\nBody.\n")

    def test_valid_frontmatter_parsed(self) -> None:
        meta, body = split_frontmatter("---\ntitle: Home\npublish: true\n---\nBody.\n")
        self.assertEqual(meta["title"], "Home")
        self.assertEqual(meta["publish"], True)
        self.assertEqual(body, "Body.\n")

    def test_obsidian_template_placeholder_does_not_crash(self) -> None:
        # `{{date}}` parses as a nested mapping used as a key (unhashable) and
        # would otherwise raise; we treat it as no frontmatter and keep the body.
        raw = "---\ndate: {{date}}\n---\nTemplate body.\n"
        meta, body = split_frontmatter(raw)
        self.assertEqual(meta, {})
        self.assertEqual(body, "Template body.\n")

    def test_malformed_yaml_does_not_crash(self) -> None:
        raw = "---\ntitle: [unterminated\n---\nBody.\n"
        meta, body = split_frontmatter(raw)
        self.assertEqual(meta, {})
        self.assertEqual(body, "Body.\n")

    def test_non_mapping_frontmatter_ignored(self) -> None:
        meta, body = split_frontmatter("---\n- just\n- a\n- list\n---\nBody.\n")
        self.assertEqual(meta, {})
        self.assertEqual(body, "Body.\n")


if __name__ == "__main__":
    unittest.main()
