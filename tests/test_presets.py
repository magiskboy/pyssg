"""Unit tests for the preset plugin stacks."""

from __future__ import annotations

import unittest

from pyssg.plugin import Plugin
from pyssg_cli.presets import blog, docs, i18n_blog, i18n_docs, site
from pyssg_plugins import (
    BrokenLinks,
    Collections,
    Highlight,
    I18n,
    Listing,
    Markdown,
    MarkdownPage,
    Minify,
    Navigation,
    Permalink,
    ReadFile,
    Redirects,
    Robots,
    Rss,
    Sitemap,
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

    def test_extras_flags_wire_their_plugins(self) -> None:
        stack = docs(sitemap=True, robots=True, markdown_pages=True, minify=True)
        types = types_in(stack)
        for plugin_type in (Sitemap, Robots, MarkdownPage, Minify):
            self.assertIn(plugin_type, types)

    def test_broken_links_flag_adds_plugin(self) -> None:
        self.assertNotIn(BrokenLinks, types_in(docs()))
        self.assertIn(BrokenLinks, types_in(docs(broken_links=True)))

    def test_strict_links_flag_enables_strict_plugin(self) -> None:
        stack = blog(strict_links=True)
        plugins = [p for p in stack if isinstance(p, BrokenLinks)]
        self.assertEqual(len(plugins), 1)
        self.assertTrue(plugins[0]._strict)

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


class I18nBlogPresetTest(unittest.TestCase):
    def _stack(self, **kwargs: object) -> list[Plugin]:
        params: dict[str, object] = {"locales": ["vi", "en"], "default_locale": "vi"}
        params.update(kwargs)
        return i18n_blog(**params)  # type: ignore[arg-type]

    def test_is_a_valid_read_write_stack(self) -> None:
        stack = self._stack()
        for plugin in stack:
            self.assertIsInstance(plugin, Plugin)
        self.assertIs(types_in(stack)[0], ReadFile)
        self.assertIs(types_in(stack)[-1], WriteFile)

    def test_has_i18n_and_grouped_structure(self) -> None:
        types = types_in(self._stack())
        self.assertIn(I18n, types)
        self.assertIn(Collections, types)
        self.assertIn(Navigation, types)

    def test_one_index_listing_per_locale_plus_tag_listing(self) -> None:
        # Three locales -> three per-locale index listings + one tag listing.
        listings = [
            p for p in self._stack(locales=["vi", "en", "ja"]) if isinstance(p, Listing)
        ]
        self.assertEqual(len(listings), 4)

    def test_one_rss_feed_per_locale(self) -> None:
        feeds = [p for p in self._stack() if isinstance(p, Rss)]
        self.assertEqual(len(feeds), 2)
        self.assertNotIn(Rss, types_in(self._stack(rss=False)))

    def test_default_locale_at_root_no_redirect(self) -> None:
        # The default locale lives at the root, so no "/" redirect is added.
        self.assertNotIn(Redirects, types_in(self._stack()))

    def test_default_locale_index_at_root_others_prefixed(self) -> None:
        listings = [p for p in self._stack() if isinstance(p, Listing)]
        index_urls = {p._base_url for p in listings if p._collection is not None}
        self.assertIn("/", index_urls)
        self.assertIn("/en/", index_urls)

    def test_default_locale_feed_at_root_others_prefixed(self) -> None:
        paths = {p._path for p in self._stack() if isinstance(p, Rss)}
        self.assertEqual(paths, {"feed.xml", "en/feed.xml"})

    def test_default_locale_must_be_in_locales(self) -> None:
        with self.assertRaises(ValueError):
            i18n_blog(locales=["vi", "en"], default_locale="fr")


class I18nDocsPresetTest(unittest.TestCase):
    def _stack(self, **kwargs: object) -> list[Plugin]:
        params: dict[str, object] = {"locales": ["en", "vi"], "default_locale": "en"}
        params.update(kwargs)
        return i18n_docs(**params)  # type: ignore[arg-type]

    def test_is_a_valid_read_write_stack(self) -> None:
        stack = self._stack()
        for plugin in stack:
            self.assertIsInstance(plugin, Plugin)
        self.assertIs(types_in(stack)[0], ReadFile)
        self.assertIs(types_in(stack)[-1], WriteFile)

    def test_has_i18n_navigation_no_listing(self) -> None:
        types = types_in(self._stack())
        self.assertIn(I18n, types)
        self.assertIn(Navigation, types)
        self.assertNotIn(Listing, types)

    def test_default_locale_at_root_no_redirect(self) -> None:
        self.assertNotIn(Redirects, types_in(self._stack()))

    def test_default_locale_must_be_in_locales(self) -> None:
        with self.assertRaises(ValueError):
            i18n_docs(locales=["en", "vi"], default_locale="fr")


if __name__ == "__main__":
    unittest.main()
