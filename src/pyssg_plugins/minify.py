"""Minify plugin: shrink HTML outputs by removing redundant whitespace.

Taps ``optimize`` (after all outputs exist, before they are written) and
rewrites the content of each matching ``Output`` in place. Standard library
only.

The minifier is deliberately conservative:

- Content of ``pre``, ``code``, ``textarea``, ``script`` and ``style`` is left
  untouched (whitespace there is significant).
- HTML comments are removed, except IE conditional comments (``<!--[if ...]>``).
- Whitespace-only runs between tags are collapsed, and other whitespace runs are
  reduced to a single space.
"""

from __future__ import annotations

import re

from pyssg.build import Build
from pyssg.builder import Builder

_PROTECTED = re.compile(
    r"<(pre|code|textarea|script|style)\b[^>]*>.*?</\1>",
    re.DOTALL | re.IGNORECASE,
)
_COMMENT = re.compile(r"<!--(?!\[if).*?-->", re.DOTALL)
_BETWEEN_TAGS = re.compile(r">\s+<")
_WHITESPACE = re.compile(r"\s{2,}")
_PLACEHOLDER = "\x00pyssg-protected-{}\x00"


class Minify:
    def __init__(self, *, suffixes: tuple[str, ...] = (".html", ".htm")) -> None:
        self._suffixes = suffixes

    def apply(self, builder: Builder) -> None:
        builder.hooks.optimize.tap("Minify", self._optimize)

    def _optimize(self, build: Build) -> None:
        for output in build.outputs:
            if output.path.suffix.lower() in self._suffixes:
                output.content = minify_html(output.content)


def minify_html(html: str) -> str:
    protected: list[str] = []

    def stash(match: re.Match[str]) -> str:
        protected.append(match.group(0))
        return _PLACEHOLDER.format(len(protected) - 1)

    html = _PROTECTED.sub(stash, html)
    html = _COMMENT.sub("", html)
    html = _BETWEEN_TAGS.sub("><", html)
    html = _WHITESPACE.sub(" ", html)
    html = html.strip()

    for index, original in enumerate(protected):
        html = html.replace(_PLACEHOLDER.format(index), original)
    return html
