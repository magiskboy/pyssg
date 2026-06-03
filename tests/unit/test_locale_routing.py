"""Unit tests for the shared locale-routing helpers used by summarizer plugins.

These pure helpers (in :mod:`pyssg.plugins._context`) let rss/taxonomy/collections
partition their generated pages per locale without depending on the i18n plugin's
run order: the routing decision is read from a document's ``meta["lang"]`` and
from a representative member URL.
"""

from __future__ import annotations

import unittest

from pyssg.core.node import Document
from pyssg.core.types import NodeKind
from pyssg.plugins._context import doc_locale, localize_route, locale_root


class DocLocaleTest(unittest.TestCase):
    def test_reads_lang_meta(self) -> None:
        doc = Document(id="d", kind=NodeKind.MARKDOWN, meta={"lang": "vi"})
        self.assertEqual(doc_locale(doc), "vi")

    def test_missing_lang_is_empty(self) -> None:
        doc = Document(id="d", kind=NodeKind.MARKDOWN)
        self.assertEqual(doc_locale(doc), "")

    def test_none_doc_is_empty(self) -> None:
        self.assertEqual(doc_locale(None), "")

    def test_non_string_lang_is_empty(self) -> None:
        doc = Document(id="d", kind=NodeKind.MARKDOWN, meta={"lang": 123})
        self.assertEqual(doc_locale(doc), "")


class LocaleRootTest(unittest.TestCase):
    def test_no_locale_is_root(self) -> None:
        self.assertEqual(locale_root("", "/posts/a/"), "/")

    def test_default_locale_served_at_root(self) -> None:
        # The default locale's pages are not prefixed, so they root at "/".
        self.assertEqual(locale_root("vi", "/posts/a/"), "/")

    def test_non_default_locale_keeps_prefix(self) -> None:
        self.assertEqual(locale_root("en", "/en/posts/a/"), "/en/")

    def test_locale_substring_not_mistaken_for_prefix(self) -> None:
        # "/english/" must not be read as the "en" locale prefix.
        self.assertEqual(locale_root("en", "/english/x/"), "/")


class LocalizeRouteTest(unittest.TestCase):
    def test_default_root_leaves_route_unchanged(self) -> None:
        self.assertEqual(localize_route("/", "/"), "/")
        self.assertEqual(localize_route("/blog/", "/"), "/blog/")

    def test_prefixes_locale_segment(self) -> None:
        self.assertEqual(localize_route("/", "/en/"), "/en/")
        self.assertEqual(localize_route("/blog/", "/en/"), "/en/blog/")


if __name__ == "__main__":
    unittest.main()
