"""Syntax-highlighting plugin: colourise fenced code via Pygments.

Runs in the parse phase at stage 250, i.e. *after* the markdown plugin (stage
200) has rendered ``node.meta["content_html"]`` and the verbatim copy
``node.meta["__content_html_raw__"]`` that downstream link rewriting reads, and
*after* an optional mermaid plugin (stage 230) which converts ``mermaid`` fences
into ``<pre class="mermaid">`` blocks that no longer match the ``<pre><code>``
markup this plugin rewrites -- so mermaid diagrams are skipped naturally.

This plugin only transforms already-rendered HTML in place: it reads the two
``content_html`` keys, replaces every code block with Pygments output, and writes
them back. It owns no graph algorithm or cache state (plugins declare facts, the
engine owns invalidation). ``cache_version`` folds in the style name so switching
themes busts the render cache.

Every computation is pure: it depends solely on the rendered HTML and the chosen
style, never on a clock or randomness, so two builds of the same input are
byte-identical.

``pygments`` is third-party. It is allowed in a peripheral plugin like
this one, but never in ``pyssg.core``.
"""

from __future__ import annotations

import html
import re
from typing import TYPE_CHECKING

from pygments import highlight as _pygments_highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import TextLexer, get_lexer_by_name
from pygments.util import ClassNotFound

from pyssg.core.node import Document
from pyssg.core.types import NodeKind

if TYPE_CHECKING:
    from pygments.lexer import Lexer

    from pyssg.core.build import Build
    from pyssg.core.builder import Builder
    from pyssg.core.node import Node

# Parse-stage ordering: markdown renders at 200, mermaid (if present) rewrites its
# fences at 230, so we colourise the remaining code blocks at 250.
_PARSE_STAGE = 250

# CSS class wrapping every highlighted block; also the key templates read for the
# generated stylesheet (``<style>{{ site.highlight_css }}</style>``).
_CSS_CLASS = "highlight"

# Config-site key holding the generated Pygments stylesheet.
_CSS_SITE_KEY = "highlight_css"

# Language fences left untouched so a mermaid plugin can claim them.
_MERMAID_LANG = "mermaid"

# Matches a markdown-it fenced code block:
#   <pre><code class="language-LANG">ESCAPED\n</code></pre>   (with a language)
#   <pre><code>ESCAPED\n</code></pre>                           (plain fence)
# ``language-(\S+)`` captures the info string; group "code" is the HTML-escaped
# body. re.DOTALL lets the body span newlines. Non-greedy so adjacent blocks do
# not merge into one match.
_CODE_BLOCK = re.compile(
    r'<pre><code(?: class="language-(?P<lang>[^"]+)")?>(?P<code>.*?)</code></pre>',
    re.DOTALL,
)


def _lexer_for(lang: str) -> Lexer:
    """Pygments lexer for ``lang``, falling back to ``TextLexer`` if unknown."""
    if not lang:
        return TextLexer()
    try:
        return get_lexer_by_name(lang)
    except ClassNotFound:
        # Unknown info string: render the code verbatim rather than failing.
        return TextLexer()


def highlight_html(html_text: str, highlighter: HtmlFormatter) -> str:
    """Replace every ``<pre><code>`` block in ``html_text`` with Pygments output.

    For each matched block: recover the source by ``html.unescape``-ing the
    escaped body, pick a lexer from the ``language-LANG`` class (``TextLexer`` when
    the language is missing or unknown), and render it with the shared
    ``highlighter``. ``mermaid`` fences are left verbatim so a mermaid plugin can
    claim them. HTML that does not match the code-block markup is untouched.
    """

    def _replace(match: re.Match[str]) -> str:
        lang = match.group("lang") or ""
        if lang == _MERMAID_LANG:
            # Leave mermaid blocks for the dedicated plugin.
            return match.group(0)
        # markdown-it HTML-escapes the body; recover the real source first.
        code = html.unescape(match.group("code"))
        # ``pygments.highlight`` is untyped (returns ``Any``); it always yields a
        # ``str`` for an ``HtmlFormatter``, so narrow it explicitly.
        rendered: str = _pygments_highlight(code, _lexer_for(lang), highlighter)
        return rendered

    return _CODE_BLOCK.sub(_replace, html_text)


class HighlightPlugin:
    """Colourises fenced code blocks in rendered Markdown HTML via Pygments."""

    name = "highlight"

    def __init__(self, style: str = "default") -> None:
        self._style = style
        # Bump the cache key when the theme changes so stale highlighted HTML is
        # busted on the next build.
        self.cache_version = f"1.0.0:{style}"
        # One formatter shared across every block. ``nowrap=False`` keeps the
        # ``<div class="highlight"><pre>...`` wrapper; ``cssclass`` names it.
        self._formatter = HtmlFormatter(nowrap=False, cssclass=_CSS_CLASS)

    def apply(self, builder: Builder) -> None:
        # Compute the theme stylesheet once and expose it to templates. The
        # ``setdefault`` lets a site override the CSS via config without us
        # clobbering it.
        if builder.config is not None:
            css = HtmlFormatter(style=self._style).get_style_defs(f".{_CSS_CLASS}")
            builder.config.site.setdefault(_CSS_SITE_KEY, css)

        @builder.hooks.this_compilation.tap(self.name)
        def _wire(build: Build) -> None:
            @build.hooks.parse.tap(self.name, stage=_PARSE_STAGE)
            def _parse(node: Node) -> None:
                if node.kind is not NodeKind.MARKDOWN or not isinstance(node, Document):
                    return
                raw = node.meta.get("__content_html_raw__")
                if isinstance(raw, str):
                    node.meta["__content_html_raw__"] = highlight_html(raw, self._formatter)
                rendered = node.meta.get("content_html")
                if isinstance(rendered, str):
                    node.meta["content_html"] = highlight_html(rendered, self._formatter)


def highlight(style: str = "default") -> HighlightPlugin:
    """Factory used in ``pyssg.config.py``."""
    return HighlightPlugin(style=style)
