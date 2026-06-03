"""Markdown loader + parser plugin.

Loads ``.md`` files (``load_node``) and, in the parse phase, renders the body to
``content_html`` and records the heading tree (the ``toc`` extension's
``toc_tokens``) on ``node.ast`` for the content-meta plugin. Frontmatter splitting
runs in an earlier parse stage (see the frontmatter plugin), so this plugin reads
``__body__`` if present, falling back to the raw text.

Rendering uses `Python-Markdown <https://python-markdown.github.io/>`_. The
built-in extension set is ``fenced_code`` (so ```` ``` ```` blocks become
``<pre><code class="language-...">``, which the mermaid/highlight plugins rewrite),
``tables`` (GFM-style pipe tables), ``sane_lists`` and ``toc``. The ``toc``
extension assigns heading ``id`` attributes using the project's :func:`slugify`,
so in-page anchors resolve and the same slug is shared with the link resolver's
fragment links.

Callers can extend the engine without subclassing: :func:`markdown` accepts
``extensions`` (extra extensions appended to the built-in set) and
``extension_configs`` (forwarded verbatim to Python-Markdown). For deeper
customisation, subclass :class:`MarkdownPlugin` and override one of the small
hooks it exposes (:attr:`~MarkdownPlugin.default_extensions`,
:meth:`~MarkdownPlugin.resolve_extension_configs`, or
:meth:`~MarkdownPlugin.build_markdown`).

The parser instance is reused across documents but ``reset()`` is called before
every parse, so no state leaks between documents and two builds are byte-identical.

Third-party (``markdown``) lives only in this peripheral plugin, never in
``pyssg.core``.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

import markdown as md_lib

from pyssg.core.node import Document
from pyssg.core.types import NodeKind
from pyssg.plugins.content_meta import slugify

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from markdown.extensions import Extension

    from pyssg.core.build import Build
    from pyssg.core.builder import Builder
    from pyssg.core.node import Node

# Parse-stage ordering: frontmatter (100) strips YAML before markdown (200) renders.
_PARSE_STAGE = 200

# Bumped when the rendering engine changed (markdown-it-py -> Python-Markdown) so
# the persistent render cache is busted on the next build. Per-instance extension
# configuration is folded in on top of this (see ``_compute_cache_version``).
_BASE_CACHE_VERSION = "2.0.0"


def _toc_slugify(value: str, separator: str) -> str:
    """Adapter so the ``toc`` extension uses the project's :func:`slugify`.

    Python-Markdown calls ``slugify(value, separator)``; our slugifier always uses
    a hyphen separator, so the second argument is intentionally ignored. Sharing
    one slugifier keeps heading ``id``s consistent with the link resolver's
    fragment slugs.
    """
    return slugify(value)


def _text(value: object) -> str:
    return value if isinstance(value, str) else ""


def _first_heading(toc_tokens: object) -> str | None:
    """Text of the first heading in the document, read from ``toc_tokens``."""
    if isinstance(toc_tokens, list) and toc_tokens:
        first = toc_tokens[0]
        if isinstance(first, dict):
            name = first.get("name")
            if isinstance(name, str) and name:
                return name
    return None


def _derive_title(node: Document, toc_tokens: object) -> str:
    """Title precedence: frontmatter ``title`` -> first heading -> file stem."""
    existing = node.meta.get("title")
    if isinstance(existing, str) and existing:
        return existing
    heading = _first_heading(toc_tokens)
    if heading:
        return heading
    return Path(node.source_path).stem if node.source_path else node.id


class MarkdownPlugin:
    """Parses Markdown documents to HTML via Python-Markdown.

    The plugin is designed to be customised either by configuration or by
    subclassing:

    * Pass ``extensions`` / ``extension_configs`` to add to the built-in engine
      without writing any code.
    * Subclass and override :attr:`default_extensions`,
      :meth:`resolve_extension_configs`, or :meth:`build_markdown` for full
      control over the parser, while reusing the load/parse wiring.
    """

    name = "markdown"

    #: Extensions enabled on every instance, before any caller-supplied
    #: ``extensions`` are appended. The ``toc`` extension's slugify hook is wired
    #: in :meth:`resolve_extension_configs`. Override in a subclass to change the
    #: built-in set.
    default_extensions: tuple[str, ...] = (
        "fenced_code",
        "tables",
        "sane_lists",
        "toc",
    )

    def __init__(
        self,
        *,
        extensions: Sequence[str | Extension] = (),
        extension_configs: Mapping[str, Mapping[str, Any]] | None = None,
    ) -> None:
        """Configure the renderer.

        Args:
            extensions: Extra Python-Markdown extensions (names or instances)
                appended after :attr:`default_extensions`.
            extension_configs: Per-extension options forwarded verbatim to
                Python-Markdown. A ``"toc"`` entry is merged with the project
                slugify default, so callers can set e.g. ``permalink`` without
                losing consistent heading ``id``s.
        """
        self._extensions: list[str | Extension] = list(extensions)
        self._extension_configs: dict[str, Mapping[str, Any]] = dict(extension_configs or {})
        # Fold the configuration into the cache key so a different extension set
        # never reuses HTML rendered under the old configuration.
        self.cache_version = self._compute_cache_version()
        # One parser instance, configured deterministically; reset() per parse.
        self._md = self.build_markdown()

    def resolve_extension_configs(self) -> dict[str, Any]:
        """Return the ``extension_configs`` dict passed to Python-Markdown.

        Starts from the caller-supplied configs and ensures the ``toc`` extension
        uses the project :func:`slugify` unless the caller overrode ``slugify``
        explicitly. Override in a subclass to inject further defaults.
        """
        configs: dict[str, Any] = {
            key: dict(value) for key, value in self._extension_configs.items()
        }
        toc_config = dict(configs.get("toc", {}))
        toc_config.setdefault("slugify", _toc_slugify)
        configs["toc"] = toc_config
        return configs

    def build_markdown(self) -> md_lib.Markdown:
        """Construct the Python-Markdown instance reused across documents.

        Override in a subclass to swap the engine wholesale; the default builds it
        from :attr:`default_extensions`, the caller's extra ``extensions`` and
        :meth:`resolve_extension_configs`.
        """
        return md_lib.Markdown(
            extensions=[*self.default_extensions, *self._extensions],
            extension_configs=self.resolve_extension_configs(),
            output_format="html",
        )

    def _compute_cache_version(self) -> str:
        """Derive a cache key that changes when the extension configuration does.

        The default (no extra extensions or configs) keeps the bare
        :data:`_BASE_CACHE_VERSION` so existing caches survive an upgrade. Any
        configuration appends a short digest of it. Non-serialisable config values
        (e.g. callables) fall back to ``repr``; that may be unstable across runs,
        which only costs a cache miss, never byte-identical output.
        """
        if not self._extensions and not self._extension_configs:
            return _BASE_CACHE_VERSION
        payload = {
            "extensions": [
                ext if isinstance(ext, str) else f"{type(ext).__module__}.{type(ext).__qualname__}"
                for ext in self._extensions
            ],
            "extension_configs": self._extension_configs,
        }
        digest = hashlib.sha256(
            json.dumps(payload, sort_keys=True, default=repr).encode("utf-8")
        ).hexdigest()[:12]
        return f"{_BASE_CACHE_VERSION}:{digest}"

    def apply(self, builder: Builder) -> None:
        @builder.hooks.this_compilation.tap(self.name)
        def _wire(build: Build) -> None:
            @build.hooks.load_node.tap(self.name)
            def _load(path: str) -> Node | None:
                if not path.endswith(".md"):
                    return None
                node = Document(id=path, kind=NodeKind.MARKDOWN, source_path=path)
                node.meta["__raw__"] = Path(path).read_text(encoding="utf-8")
                return node

            @build.hooks.parse.tap(self.name, stage=_PARSE_STAGE)
            def _parse(node: Node) -> None:
                if node.kind is not NodeKind.MARKDOWN or not isinstance(node, Document):
                    return
                body = node.meta.get("__body__")
                text = _text(body) if body is not None else _text(node.meta.get("__raw__"))
                # reset() clears the per-document state (including toc_tokens) so
                # one reused parser stays pure across documents.
                self._md.reset()
                html = self._md.convert(text)
                # ``toc_tokens`` is set dynamically by the toc extension (not in the
                # Markdown stub). Copy it before the next reset reassigns it.
                raw_toc = getattr(self._md, "toc_tokens", [])
                toc_tokens: list[object] = list(raw_toc) if isinstance(raw_toc, list) else []
                node.ast = toc_tokens
                node.meta["content_html"] = html
                # Keep the pre-link-resolution HTML so link_resolver can rewrite
                # from a stable source on every finalize.
                node.meta["__content_html_raw__"] = html
                node.meta["title"] = _derive_title(node, toc_tokens)


def markdown(
    *,
    extensions: Sequence[str | Extension] = (),
    extension_configs: Mapping[str, Mapping[str, Any]] | None = None,
) -> MarkdownPlugin:
    """Factory used in ``pyssg.config.py``.

    Args:
        extensions: Extra Python-Markdown extensions appended to the built-in set.
        extension_configs: Per-extension options forwarded to Python-Markdown.
    """
    return MarkdownPlugin(extensions=extensions, extension_configs=extension_configs)
