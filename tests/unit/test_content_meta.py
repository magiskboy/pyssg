"""Unit tests for the ``content_meta`` plugin helpers."""

from __future__ import annotations

import unittest

from markdown_it import MarkdownIt

from pyssg.plugins.content_meta import (
    first_paragraph_excerpt,
    outline,
    reading_time,
    slugify,
)


def _tokens(markdown: str) -> list[object]:
    return list(MarkdownIt("commonmark").parse(markdown))


class SlugifyTest(unittest.TestCase):
    def test_ascii_lowercases_and_hyphenates(self) -> None:
        self.assertEqual(slugify("Hello World"), "hello-world")

    def test_collapses_multiple_spaces(self) -> None:
        self.assertEqual(slugify("Hello   World"), "hello-world")

    def test_strips_punctuation(self) -> None:
        self.assertEqual(slugify("What's up, doc?!"), "whats-up-doc")

    def test_collapses_repeated_hyphens(self) -> None:
        self.assertEqual(slugify("a -- b"), "a-b")

    def test_trims_surrounding_whitespace_and_hyphens(self) -> None:
        self.assertEqual(slugify("  - leading and trailing -  "), "leading-and-trailing")

    def test_keeps_unicode_letters_without_ascii_folding(self) -> None:
        # Vietnamese letters must survive; the slug stays readable.
        self.assertEqual(slugify("Giới thiệu"), "giới-thiệu")
        self.assertEqual(slugify("Cài đặt nhanh"), "cài-đặt-nhanh")

    def test_empty_input_returns_empty(self) -> None:
        self.assertEqual(slugify(""), "")

    def test_whitespace_only_returns_empty(self) -> None:
        self.assertEqual(slugify("   \t\n "), "")

    def test_deterministic(self) -> None:
        self.assertEqual(slugify("Repeat Me"), slugify("Repeat Me"))


class OutlineTest(unittest.TestCase):
    def test_multiple_levels_in_document_order(self) -> None:
        result = outline(_tokens("# A\n\n## B\n\n### C"))  # type: ignore[arg-type]
        self.assertEqual(
            result,
            [
                {"level": 1, "text": "A", "slug": "a"},
                {"level": 2, "text": "B", "slug": "b"},
                {"level": 3, "text": "C", "slug": "c"},
            ],
        )

    def test_nested_same_level_repeats(self) -> None:
        result = outline(_tokens("## One\n\n### Two\n\n## Three"))  # type: ignore[arg-type]
        self.assertEqual([e["level"] for e in result], [2, 3, 2])
        self.assertEqual([e["text"] for e in result], ["One", "Two", "Three"])

    def test_no_headings_returns_empty(self) -> None:
        self.assertEqual(outline(_tokens("Just a paragraph.")), [])  # type: ignore[arg-type]

    def test_heading_slug_uses_text(self) -> None:
        result = outline(_tokens("# Getting Started"))  # type: ignore[arg-type]
        self.assertEqual(
            result, [{"level": 1, "text": "Getting Started", "slug": "getting-started"}]
        )


class ReadingTimeTest(unittest.TestCase):
    def test_zero_words_is_one_minute(self) -> None:
        self.assertEqual(reading_time(0), 1)

    def test_two_hundred_words_is_one_minute(self) -> None:
        self.assertEqual(reading_time(200), 1)

    def test_four_hundred_fifty_words_is_two_minutes(self) -> None:
        # 450 / 200 = 2.25 -> round -> 2.
        self.assertEqual(reading_time(450), 2)

    def test_five_hundred_words_rounds_to_two(self) -> None:
        # 500 / 200 = 2.5 -> banker's rounding -> 2.
        self.assertEqual(reading_time(500), 2)


class FirstParagraphExcerptTest(unittest.TestCase):
    def test_short_text_kept_whole(self) -> None:
        self.assertEqual(first_paragraph_excerpt("A short intro."), "A short intro.")

    def test_collapses_internal_whitespace(self) -> None:
        self.assertEqual(first_paragraph_excerpt("A\n  spaced   intro."), "A spaced intro.")

    def test_uses_only_first_paragraph(self) -> None:
        self.assertEqual(first_paragraph_excerpt("First para.\n\nSecond para."), "First para.")

    def test_long_text_truncated_on_word_boundary_with_ellipsis(self) -> None:
        text = "word " * 60  # 300 chars, well over the 200 limit
        result = first_paragraph_excerpt(text)
        self.assertTrue(result.endswith("…"))
        # Cut on a word boundary: no partial trailing word before the ellipsis.
        self.assertTrue(result[:-1].rstrip().endswith("word"))
        self.assertLessEqual(len(result), 201)

    def test_custom_limit(self) -> None:
        result = first_paragraph_excerpt("one two three four five", limit=7)
        self.assertEqual(result, "one two…")

    def test_empty_input_returns_empty(self) -> None:
        self.assertEqual(first_paragraph_excerpt(""), "")
        self.assertEqual(first_paragraph_excerpt("   \n\n  "), "")
