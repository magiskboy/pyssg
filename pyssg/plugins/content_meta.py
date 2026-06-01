"""Content-meta plugin: TOC/outline, word count, reading time, excerpt.

Runs in the parse phase at stage 300, i.e. *after* the markdown plugin (stage 200)
has populated ``node.ast`` with markdown-it tokens, ``node.meta["content_html"]``
and ``node.meta["title"]``. This plugin only reads those derived facts plus the
raw body and writes four new ``node.meta`` keys; it owns no graph algorithm or
cache state (plugins declare facts, the engine owns invalidation).

Every computation here is pure: it depends solely on the declared inputs, never
on a clock or randomness, so two builds of the same input are byte-identical.

``markdown-it-py`` is third-party. It is allowed in a peripheral plugin
like this one, but never in ``pyssg.core``.
"""

from __future__ import annotations

import re
import unicodedata
from typing import TYPE_CHECKING

from markdown_it.token import Token

from pyssg.core.node import Document
from pyssg.core.types import NodeKind

if TYPE_CHECKING:
    from pyssg.core.build import Build
    from pyssg.core.builder import Builder
    from pyssg.core.node import Node

# Parse-stage ordering: markdown renders at 200, so we read its tokens at 300.
_PARSE_STAGE = 300

# Average adult reading speed in words per minute; the conventional SSG default.
_WORDS_PER_MINUTE = 200

# Default soft cap for a generated excerpt, in characters.
_EXCERPT_LIMIT = 200

# Characters dropped by ``slugify``: anything that is neither a Unicode word
# character (letters, digits, underscore, combining marks) nor a hyphen.
# ``re.UNICODE`` is implicit for ``str`` patterns on Python 3, so ``\w`` already
# covers Unicode letters (e.g. Vietnamese), which is exactly what we want: we
# keep readable Unicode slugs and never ASCII-fold.
_NON_SLUG_CHARS = re.compile(r"[^\w-]+", re.UNICODE)
_WHITESPACE_RUN = re.compile(r"\s+")
_HYPHEN_RUN = re.compile(r"-{2,}")


def slugify(text: str) -> str:
    """Return a GitHub-style slug for a heading.

    Rules, applied in order:

    1. NFC-normalise so visually identical strings slug identically (determinism).
    2. Lowercase and strip surrounding whitespace.
    3. Replace each run of whitespace with a single hyphen.
    4. Remove every character that is not a Unicode word char or a hyphen.
       Unicode letters are kept (no ASCII folding), so a Vietnamese heading such
       as ``"Giới thiệu"`` yields a readable ``"giới-thiệu"``.
    5. Collapse runs of hyphens and trim leading/trailing hyphens.

    Empty or whitespace-only input returns ``""``.
    """
    # NFC keeps precomposed forms stable across inputs that encode the same
    # grapheme differently; without it two equal-looking headings could differ.
    normalised = unicodedata.normalize("NFC", text).strip().lower()
    if not normalised:
        return ""
    hyphenated = _WHITESPACE_RUN.sub("-", normalised)
    cleaned = _NON_SLUG_CHARS.sub("", hyphenated)
    collapsed = _HYPHEN_RUN.sub("-", cleaned)
    return collapsed.strip("-")


def _heading_level(tag: str) -> int | None:
    """Map an ``h1``..``h6`` tag to its integer level, else ``None``."""
    if len(tag) == 2 and tag[0] == "h" and tag[1].isdigit():
        level = int(tag[1])
        if 1 <= level <= 6:
            return level
    return None


def outline(tokens: list[Token]) -> list[dict[str, object]]:
    """Build a flat table of contents from markdown-it tokens, in document order.

    A heading is the pair ``heading_open`` (its ``tag`` gives the level) followed
    by an ``inline`` token whose ``.content`` is the heading text. Each entry is
    ``{"level": int, "text": str, "slug": str}``. The list stays flat (one entry
    per heading); nesting is a presentation concern left to the consumer.
    """
    entries: list[dict[str, object]] = []
    for index, token in enumerate(tokens):
        if token.type != "heading_open":
            continue
        level = _heading_level(token.tag)
        if level is None:
            continue
        if index + 1 >= len(tokens):
            continue
        inline = tokens[index + 1]
        if inline.type != "inline":
            continue
        text = inline.content
        entries.append({"level": level, "text": text, "slug": slugify(text)})
    return entries


def _word_count(plain_text: str) -> int:
    """Count whitespace-separated tokens.

    Fenced code blocks are excluded by ``_plain_text_for_count`` before this runs,
    so a plain ``split()`` is an honest word count of prose. We do not attempt to
    strip inline markdown markup: ``*emphasis*`` counts as one word either way,
    and the error is negligible for a reading-time estimate.
    """
    return len(plain_text.split())


def reading_time(word_count: int) -> int:
    """Estimated reading time in whole minutes, at least 1.

    ``max(1, round(word_count / WORDS_PER_MINUTE))`` so even a near-empty document
    reports one minute rather than zero.
    """
    return max(1, round(word_count / _WORDS_PER_MINUTE))


# A fenced code block: ``` or ~~~ fence, anything until a closing fence (or EOF).
# Used only to drop code from the word count; it never touches stored content.
_FENCED_CODE = re.compile(r"^([`~]{3,}).*?(?:^\1[`~]*\s*$|\Z)", re.MULTILINE | re.DOTALL)


def _plain_text_for_count(body: str) -> str:
    """Body text with fenced code blocks removed, for word counting only."""
    return _FENCED_CODE.sub("", body)


def first_paragraph_excerpt(plain_text: str, limit: int = _EXCERPT_LIMIT) -> str:
    """Derive a plain-text excerpt from the first paragraph.

    Takes everything up to the first blank line (the first paragraph), collapses
    all internal whitespace to single spaces, and truncates to ``limit``
    characters on a word boundary, appending an ellipsis when content was cut.
    Returns ``""`` for empty input.
    """
    stripped = plain_text.strip()
    if not stripped:
        return ""
    # First paragraph = text up to the first blank line.
    first = re.split(r"\n[ \t]*\n", stripped, maxsplit=1)[0]
    collapsed = _WHITESPACE_RUN.sub(" ", first).strip()
    if len(collapsed) <= limit:
        return collapsed
    # Cut on a word boundary: take the longest prefix within the limit that ends
    # at a space, falling back to a hard cut if the first word is itself too long.
    window = collapsed[: limit + 1]
    cut = window.rfind(" ")
    truncated = collapsed[:cut] if cut > 0 else collapsed[:limit]
    return truncated.rstrip() + "…"


def _text(value: object) -> str:
    return value if isinstance(value, str) else ""


def _existing_excerpt(meta: dict[str, object]) -> str | None:
    """Return a non-empty frontmatter excerpt/description if present."""
    for key in ("excerpt", "description"):
        value = meta.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None


class ContentMetaPlugin:
    """Derives TOC, word count, reading time and excerpt from parsed Markdown."""

    name = "content_meta"
    cache_version = "1.0.0"

    def apply(self, builder: Builder) -> None:
        @builder.hooks.this_compilation.tap(self.name)
        def _wire(build: Build) -> None:
            @build.hooks.parse.tap(self.name, stage=_PARSE_STAGE)
            def _parse(node: Node) -> None:
                if node.kind is not NodeKind.MARKDOWN or not isinstance(node, Document):
                    return

                tokens = node.ast if isinstance(node.ast, list) else []
                node.meta["toc"] = outline(tokens)

                body = node.meta.get("__body__")
                raw = _text(body) if body is not None else _text(node.meta.get("__raw__"))
                plain = _plain_text_for_count(raw)

                count = _word_count(plain)
                node.meta["word_count"] = count
                node.meta["reading_time"] = reading_time(count)

                existing = _existing_excerpt(node.meta)
                node.meta["excerpt"] = (
                    existing if existing is not None else first_paragraph_excerpt(plain)
                )


def content_meta() -> ContentMetaPlugin:
    """Factory used in ``pyssg.config.py``."""
    return ContentMetaPlugin()
