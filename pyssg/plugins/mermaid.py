"""Mermaid client-side diagram plugin.

Client-side rendering is the default: a fenced ``mermaid`` code block is rewritten
into markup the mermaid.js browser library understands, namely
``<pre class="mermaid">...</pre>``. The layout is responsible for loading
mermaid.js lazily; this plugin performs only a pure HTML transform and never
fetches or renders SVG (that is the opt-in build-time path, not implemented here).

Ordering: the markdown plugin renders at parse stage 200 and the syntax-highlight
plugin runs at stage 250. This plugin taps stage 230 so it consumes mermaid blocks
*before* highlighting would touch them, leaving every other code block intact.

The transform is pure: it depends only on its input HTML string, never on a clock
or randomness, so two builds of the same input are byte-identical.
This plugin only rewrites derived ``node.meta`` HTML; it owns no graph algorithm or
cache state (plugins declare facts, the engine owns invalidation).

Stdlib only; no third-party dependency is needed for client-side rendering.
"""

from __future__ import annotations

import html
import re
from typing import TYPE_CHECKING

from pyssg.core.node import Document
from pyssg.core.types import NodeKind

if TYPE_CHECKING:
    from pyssg.core.build import Build
    from pyssg.core.builder import Builder
    from pyssg.core.node import Node

# Parse-stage ordering: markdown renders at 200, highlight runs at 250. We sit at
# 230 so mermaid blocks are claimed before highlighting can rewrite them.
_PARSE_STAGE = 230

# Matches the markup markdown-it emits for a ```mermaid fenced block:
# ``<pre><code class="language-mermaid">ESCAPED</code></pre>``. The diagram text
# is captured non-greedily across newlines (re.DOTALL) so multiple blocks in one
# document each match independently. Only the ``language-mermaid`` class matches,
# so all other code blocks are left untouched.
_MERMAID_BLOCK = re.compile(
    r'<pre><code class="language-mermaid">(.*?)</code></pre>',
    re.DOTALL,
)


def clientside_mermaid(html_text: str) -> str:
    """Rewrite mermaid code blocks for client-side rendering by mermaid.js.

    Every ``<pre><code class="language-mermaid">ESCAPED</code></pre>`` becomes
    ``<pre class="mermaid">UNESCAPED</pre>``. The diagram text is HTML-unescaped
    (e.g. ``A--&gt;B`` back to ``A-->B``) because the mermaid.js library reads the
    raw text content of the ``<pre class="mermaid">`` element. All other code
    blocks and surrounding HTML are left unchanged.
    """

    def _replace(match: re.Match[str]) -> str:
        diagram = html.unescape(match.group(1))
        return f'<pre class="mermaid">{diagram}</pre>'

    return _MERMAID_BLOCK.sub(_replace, html_text)


class MermaidPlugin:
    """Rewrites mermaid code blocks into client-side mermaid.js markup."""

    name = "mermaid"
    cache_version = "1.0.0"

    def apply(self, builder: Builder) -> None:
        @builder.hooks.this_compilation.tap(self.name)
        def _wire(build: Build) -> None:
            @build.hooks.parse.tap(self.name, stage=_PARSE_STAGE)
            def _parse(node: Node) -> None:
                if node.kind is not NodeKind.MARKDOWN or not isinstance(node, Document):
                    return
                # Rewrite both copies: ``content_html`` is the rendered output and
                # ``__content_html_raw__`` is the pre-link-resolution source that
                # link rewriting reads. They must stay in sync.
                for key in ("__content_html_raw__", "content_html"):
                    current = node.meta.get(key)
                    if isinstance(current, str):
                        node.meta[key] = clientside_mermaid(current)


def mermaid() -> MermaidPlugin:
    """Factory used in ``pyssg.config.py``."""
    return MermaidPlugin()
