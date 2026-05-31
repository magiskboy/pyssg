"""Highlight plugin: syntax-highlight fenced code blocks at build time.

The plugin owns syntax highlighting end to end -- it post-processes the HTML
that the ``fenced_code`` markdown extension produces and exposes the matching
stylesheet, so neither the Markdown plugin nor the asset pipeline needs to know
about it. Two taps:

- ``transform`` (stage 100, after Markdown) rewrites every
  ``<pre><code class="language-X">...</code></pre>`` block: it unescapes the
  code, runs Pygments with a class-based ``HtmlFormatter`` and substitutes the
  highlighted ``<div class="highlight">...</div>`` markup. Blocks with an
  unknown language are left untouched; blocks without a language are only
  touched when ``default_lang`` or ``guess`` is set.
- ``collect`` registers a ``highlight_css()`` Jinja global through the shared
  ``build.meta["template_globals"]`` seam, so a layout inlines the stylesheet
  with ``<style>{{ highlight_css() }}</style>``. This needs no separate file and
  therefore no cache-busting; dark mode ships as a ``prefers-color-scheme``
  block built from ``dark_style``.

Pygments is imported lazily, so it is only required when this plugin is used
(install with ``pip install pyssg[highlight]``); the kernel stays dependency
free. The plugin depends on the ``fenced_code`` markdown extension being enabled
so code blocks carry a ``language-*`` class.
"""

from __future__ import annotations

import html
import re
from typing import TYPE_CHECKING

from pyssg.build import Build
from pyssg.builder import Builder
from pyssg.models import Source

if TYPE_CHECKING:
    from markupsafe import Markup
    from pygments.formatters import HtmlFormatter
    from pygments.lexer import Lexer

# Run after Markdown's transform (stage 0) so the fenced blocks already exist.
_TRANSFORM_STAGE = 100

# fenced_code emits the code HTML-escaped, so a literal ``</code>`` can never
# appear inside the body -- a non-greedy match up to the closing tags is safe.
_LANG_RE = re.compile(
    r'<pre><code class="language-([^"]+)">(.*?)</code></pre>', re.DOTALL
)
_PLAIN_RE = re.compile(r"<pre><code>(.*?)</code></pre>", re.DOTALL)


class Highlight:
    def __init__(
        self,
        *,
        style: str = "default",
        dark_style: str | None = "monokai",
        css_class: str = "highlight",
        default_lang: str | None = None,
        guess: bool = False,
    ) -> None:
        self._style = style
        self._dark_style = dark_style
        self._css_class = css_class
        self._default_lang = default_lang
        self._guess = guess
        self._formatter: HtmlFormatter | None = None
        self._css: str | None = None

    def apply(self, builder: Builder) -> None:
        builder.hooks.collect.tap("Highlight", self._collect)
        builder.hooks.transform.tap(
            "Highlight", self._transform, stage=_TRANSFORM_STAGE
        )

    def _collect(self, build: Build) -> None:
        css = self._stylesheet()
        try:
            css_global = _make_css_global(css)
        except ImportError:
            # markupsafe absent: highlighting still works without the helper.
            return
        template_globals = build.meta.setdefault("template_globals", {})
        if isinstance(template_globals, dict):
            template_globals["highlight_css"] = css_global

    def _transform(self, source: Source, build: Build) -> Source:
        if not source.content:
            return source
        content = _LANG_RE.sub(self._replace_lang, source.content)
        if self._default_lang or self._guess:
            content = _PLAIN_RE.sub(self._replace_plain, content)
        source.content = content
        return source

    def _replace_lang(self, match: re.Match[str]) -> str:
        lexer = self._lexer_by_name(match.group(1))
        if lexer is None:
            return match.group(0)
        return self._render(match.group(2), lexer)

    def _replace_plain(self, match: re.Match[str]) -> str:
        code = html.unescape(match.group(1))
        lexer = self._plain_lexer(code)
        if lexer is None:
            return match.group(0)
        return self._render_code(code, lexer)

    def _render(self, escaped: str, lexer: Lexer) -> str:
        return self._render_code(html.unescape(escaped), lexer)

    def _render_code(self, code: str, lexer: Lexer) -> str:
        from pygments import highlight

        return str(highlight(code, lexer, self._make_formatter()))

    def _lexer_by_name(self, name: str) -> Lexer | None:
        from pygments.lexers import get_lexer_by_name
        from pygments.util import ClassNotFound

        for candidate in (name, self._default_lang):
            if not candidate:
                continue
            try:
                return get_lexer_by_name(candidate)
            except ClassNotFound:
                continue
        return None

    def _plain_lexer(self, code: str) -> Lexer | None:
        if self._default_lang:
            return self._lexer_by_name(self._default_lang)
        from pygments.lexers import guess_lexer
        from pygments.util import ClassNotFound

        try:
            return guess_lexer(code)
        except ClassNotFound:
            return None

    def _make_formatter(self) -> HtmlFormatter:
        if self._formatter is None:
            from pygments.formatters import HtmlFormatter

            self._formatter = HtmlFormatter(style=self._style, cssclass=self._css_class)
        return self._formatter

    def _stylesheet(self) -> str:
        if self._css is not None:
            return self._css
        from pygments.formatters import HtmlFormatter

        selector = f".{self._css_class}"
        css = str(
            HtmlFormatter(style=self._style, cssclass=self._css_class).get_style_defs(
                selector
            )
        )
        if self._dark_style:
            dark = str(
                HtmlFormatter(
                    style=self._dark_style, cssclass=self._css_class
                ).get_style_defs(selector)
            )
            css += f"\n@media (prefers-color-scheme: dark) {{\n{dark}\n}}\n"
        self._css = css
        return css


def _make_css_global(css: str) -> object:
    """Build the ``highlight_css()`` Jinja global returning the stylesheet.

    The CSS is pure configuration (not per-page), so the computed string is
    captured directly; ``collect`` re-registers it each build, keeping it valid
    across dev-server rebuilds.
    """

    from markupsafe import Markup

    def highlight_css() -> Markup:
        return Markup(css)

    return highlight_css
