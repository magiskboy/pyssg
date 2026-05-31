"""Unit tests for the preset plugin stacks."""

from __future__ import annotations

import unittest

from pyssg.plugin import Plugin
from pyssg_cli.presets import blog, docs, site
from pyssg_plugins import (
    Collections,
    Highlight,
    Listing,
    Markdown,
    MarkdownPage,
    Navigation,
    Permalink,
    ReadFile,
    WriteFile,
)


def types_in(plugins: list[Plugin]) -> list[type]:
    return [type(p) for p in plugins]


class PresetShapeTest(unittest.TestCase):
    def test_all_presets_are_valid_plugins(self) -> None:
        for stack in (docs(), blog(), site()):
            for plugin in stack:
                self.assertIsInstance(plugin, Plugin)

    def test_all_presets_read_and_write(self) -> None:
        for stack in (docs(), blog(), site()):
            self.assertIs(types_in(stack)[0], ReadFile)
            self.assertIs(types_in(stack)[-1], WriteFile)

    def test_docs_has_folder_navigation_no_listing(self) -> None:
        stack = docs()
        self.assertIn(Navigation, types_in(stack))
        self.assertIn(Permalink, types_in(stack))
        self.assertNotIn(Listing, types_in(stack))

    def test_blog_has_listing_and_collections(self) -> None:
        stack = blog()
        self.assertIn(Collections, types_in(stack))
        self.assertEqual(sum(t is Listing for t in types_in(stack)), 2)

    def test_site_is_minimal(self) -> None:
        stack = site()
        self.assertNotIn(Listing, types_in(stack))
        self.assertNotIn(Collections, types_in(stack))
        self.assertIn(Navigation, types_in(stack))

    def test_blog_page_size_is_configurable(self) -> None:
        stack = blog(page_size=3)
        listings = [p for p in stack if isinstance(p, Listing)]
        self.assertTrue(listings)

    def test_markdown_pages_flag_adds_plugin(self) -> None:
        for preset in (docs, blog, site):
            self.assertNotIn(MarkdownPage, types_in(preset()))
            self.assertIn(MarkdownPage, types_in(preset(markdown_pages=True)))

    def test_highlight_flag_adds_plugin_after_markdown(self) -> None:
        for preset in (docs, blog, site):
            self.assertNotIn(Highlight, types_in(preset()))
            stack = types_in(preset(highlight=True))
            self.assertIn(Highlight, stack)
            # Highlight must come after Markdown so the fenced blocks exist.
            self.assertGreater(stack.index(Highlight), stack.index(Markdown))


if __name__ == "__main__":
    unittest.main()
