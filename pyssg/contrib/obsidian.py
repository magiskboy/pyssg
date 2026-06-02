"""Contrib: Obsidian vault integration.

Turns an Obsidian vault into a PySSG site with one call. It is a thin
*composition* layer -- it owns no new build algorithm beyond attachment handling;
everything else is the existing built-in pipeline wired with vault-friendly
defaults:

- vault noise (``.obsidian/``, ``.trash/``, ``.git/``) is excluded from the
  content walk via :func:`pyssg.plugins.directory_loader`'s ``exclude`` filter;
  the Obsidian adapter discovers folder-specific excludes (Templates, daily
  notes) from the vault's own settings and passes them in too;
- selective publishing is delegated to the :mod:`pyssg.contrib.publish_gate`
  plugin (denylist by default for a whole-vault wiki: a note is published unless
  it sets ``publish: false``; switch to an allowlist with ``publish_required``);
- Hugo-style ``_index.md`` section pages are routed to their directory root;
- ``[[wikilinks]]`` / ``![[note]]`` embeds / ``#tags`` are handled by the
  built-in ``wikilink`` / ``transclude`` / ``taxonomy`` plugins.

The one genuinely Obsidian-specific algorithm lives here: **attachment embeds**.
Obsidian writes image/file embeds as ``![[image.png]]`` and stores the binary
anywhere in the vault. :class:`ObsidianAttachmentsPlugin` resolves such embeds by
filename, rewrites them to ``<img>``/``<a>`` pointing at a stable URL, and copies
the referenced binaries into the output -- the built-in pipeline only copies a
*theme's* assets, not vault attachments.

Everything is pure: the attachment index and the copy are deterministic
functions of the on-disk vault, so builds stay byte-identical and incremental
rebuilds equal full rebuilds.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING

from pyssg.contrib.publish_gate import publish_gate
from pyssg.plugins import (
    asset_copy,
    content_meta,
    directory_loader,
    frontmatter,
    highlight,
    link_resolver,
    markdown,
    mermaid,
    nav,
    permalink,
    render,
    rss,
    sitemap,
    taxonomy,
    transclude,
    wikilink,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from pyssg.core.build import Build
    from pyssg.core.builder import Builder
    from pyssg.core.node import Document, Node
    from pyssg.plugins.api import Plugin

# Vault directories that are never publishable content. Excluded by default;
# callers add more (e.g. an Obsidian Templates folder, discovered from the vault's
# own settings). The set covers Obsidian's own metadata plus the dev-tooling noise
# common when a vault is also a code repository, so a stray ``node_modules`` or
# ``.venv`` never leaks README files or assets into the site.
DEFAULT_VAULT_EXCLUDE: tuple[str, ...] = (
    ".obsidian",
    ".trash",
    ".git",
    ".github",
    "node_modules",
    ".venv",
    "__pycache__",
)

# Embed extensions rendered as inline images; any other attachment embed becomes
# a download link.
IMAGE_EXTENSIONS: frozenset[str] = frozenset(
    {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".bmp", ".avif", ".ico"}
)

# File extensions treated as vault attachments: the only non-markdown files that
# are indexed for embeds and copied into the output. Restricting to known media
# types keeps a repository-as-vault from dragging code, lockfiles or ``.git``
# internals into the published site (and keeps the copy cheap). Embeds of any
# other extension simply report a missing attachment.
ATTACHMENT_EXTENSIONS: frozenset[str] = IMAGE_EXTENSIONS | frozenset(
    {
        ".pdf",
        ".mp3",
        ".wav",
        ".ogg",
        ".m4a",
        ".flac",
        ".mp4",
        ".webm",
        ".mov",
        ".mkv",
    }
)

# ![[target]], ![[target|alias]], ![[target#section]] -- group 1 is the target,
# group 2 the optional alias (display text or, for images, a pixel width).
_EMBED = re.compile(r"!\[\[([^\]|#]+?)(?:#[^\]|]+)?(?:\|([^\]]+))?\]\]")

# Cache key for the per-build attachment index stashed on ``site_data``.
_INDEX_KEY = "__obsidian_attachments__"

# Run before the note-transclusion sweep (``expand_content``) and alongside the
# other ``finalize_content`` taps; the stage only orders ties within this hook.
_FINALIZE_STAGE = 90


def _matches_any(rel: Path, patterns: tuple[str, ...]) -> bool:
    """Whether ``rel`` matches any glob in ``patterns`` (``full_match`` semantics)."""
    pure = PurePosixPath(rel.as_posix())
    return any(pure.full_match(pattern) for pattern in patterns)


def _attachment_paths(content_root: Path, exclude: tuple[str, ...]) -> list[str]:
    """Content-relative posix paths of every attachment file under the vault.

    Only files whose extension is in :data:`ATTACHMENT_EXTENSIONS` count, so a
    repository-as-vault does not pour code, config or ``.git`` internals into the
    output. Honors the same ``exclude`` globs as the content walk and prunes
    excluded directory subtrees. Sorted for a deterministic, byte-identical result.
    """
    pruned: set[str] = set()
    found: list[str] = []
    for path in sorted(content_root.rglob("*")):
        rel = path.relative_to(content_root)
        rel_posix = rel.as_posix()
        if any(rel_posix == d or rel_posix.startswith(f"{d}/") for d in pruned):
            continue
        if exclude and _matches_any(rel, exclude):
            if path.is_dir():
                pruned.add(rel_posix)
            continue
        if path.is_file() and path.suffix.lower() in ATTACHMENT_EXTENSIONS:
            found.append(rel_posix)
    return found


def _attachment_index(build: Build, exclude: tuple[str, ...]) -> dict[str, str]:
    """Map attachment filename (lowercased) -> site URL, built once per build.

    On a duplicate filename the lexicographically first path wins (deterministic);
    callers embedding ambiguous names should use a more specific path.
    """
    cached = build.site_data.get(_INDEX_KEY)
    if isinstance(cached, dict):
        return {str(k): str(v) for k, v in cached.items()}
    config = build.builder.config
    index: dict[str, str] = {}
    if config is not None:
        content_root = (build.builder.site_dir / config.content_dir).resolve()
        if content_root.is_dir():
            for rel_posix in _attachment_paths(content_root, exclude):
                name = PurePosixPath(rel_posix).name.lower()
                index.setdefault(name, f"/{rel_posix}")
    build.site_data[_INDEX_KEY] = index
    return index


def _render_embed(url: str, target: str, alias: str | None) -> str:
    """HTML for a resolved attachment embed (inline image or download link)."""
    suffix = PurePosixPath(target).suffix.lower()
    if suffix in IMAGE_EXTENSIONS:
        if alias and alias.isdigit():
            return f'<img src="{url}" alt="{target}" width="{alias}">'
        alt = alias if alias else target
        return f'<img src="{url}" alt="{alt}">'
    label = alias if alias else target
    return f'<a href="{url}">{label}</a>'


def rewrite_attachment_embeds(build: Build, html: str, exclude: tuple[str, ...]) -> str:
    """``finalize_content`` tap: resolve ``![[file.ext]]`` attachment embeds.

    Only embeds whose target carries a non-``.md`` extension are handled here;
    note embeds (``![[Note]]``) are left untouched for the transclude plugin. An
    attachment that cannot be resolved renders as a ``broken-embed`` marker rather
    than vanishing.
    """
    index = _attachment_index(build, exclude)

    def _replace(match: re.Match[str]) -> str:
        target = match.group(1).strip()
        suffix = PurePosixPath(target).suffix.lower()
        if not suffix or suffix == ".md":
            return match.group(0)  # a note embed; leave it for transclude
        alias = match.group(2).strip() if match.group(2) else None
        url = index.get(PurePosixPath(target).name.lower())
        if url is None:
            return f'<span class="broken-embed">missing attachment: {target}</span>'
        return _render_embed(url, target, alias)

    return _EMBED.sub(_replace, html)


def _copy_attachments(build: Build, exclude: tuple[str, ...]) -> None:
    """Mirror the vault's attachment files into the output, preserving paths.

    A file is (re)written only when missing or its bytes differ, so rebuilds stay
    cheap and the output is byte-identical to a full rebuild; files the plugin did
    not place are never touched.
    """
    config = build.builder.config
    if config is None:
        return
    content_root = (build.builder.site_dir / config.content_dir).resolve()
    if not content_root.is_dir():
        return
    out_root = build.builder.site_dir / config.output_dir
    for rel_posix in _attachment_paths(content_root, exclude):
        src = content_root / rel_posix
        dst = out_root / rel_posix
        if not dst.exists() or src.read_bytes() != dst.read_bytes():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dst)


class ObsidianAttachmentsPlugin:
    """Resolves ``![[file.ext]]`` embeds and copies vault attachments to output."""

    name = "obsidian_attachments"

    def __init__(self, *, exclude: Sequence[str] | None = None) -> None:
        self._exclude = tuple(sorted(exclude)) if exclude else ()
        self.cache_version = f"1.0.0:e={','.join(self._exclude)}"

    def apply(self, builder: Builder) -> None:
        @builder.hooks.this_compilation.tap(self.name)
        def _wire(build: Build) -> None:
            @build.hooks.finalize_content.tap(self.name, stage=_FINALIZE_STAGE)
            def _rewrite(html: str, _doc: Document) -> str:
                return rewrite_attachment_embeds(build, html, self._exclude)

            @build.hooks.evaluate_collections.tap(self.name)
            def _copy(b: Build) -> None:
                _copy_attachments(b, self._exclude)


def obsidian_attachments(*, exclude: Sequence[str] | None = None) -> ObsidianAttachmentsPlugin:
    """Factory for the attachment plugin (used standalone or by :func:`obsidian_plugins`)."""
    return ObsidianAttachmentsPlugin(exclude=exclude)


# Section-index route stage: early, so the normalized URL flows through any later
# route taps (i18n routes at 500, the publish gate at 600).
_SECTION_INDEX_STAGE = 150


def section_index_url(url: str, source_path: str | None) -> str:
    """Map a Hugo-style ``_index.md`` page onto its directory root URL.

    ``content/guide/_index.md`` is routed to ``/guide/`` instead of
    ``/guide/_index/`` (and a top-level ``_index.md`` to ``/``), so a vault using
    the ``_index`` section-page convention gets real section landing pages without
    an explicit ``permalink``. Any other page is returned unchanged. Pure: the
    result depends only on the URL and source path.
    """
    if not source_path or PurePosixPath(source_path).stem != "_index":
        return url
    suffix = "_index/"
    return url[: -len(suffix)] if url.endswith(suffix) else url


class ObsidianSectionIndexPlugin:
    """Routes ``_index.md`` files to their directory root (Hugo section pages)."""

    name = "obsidian_section_index"
    cache_version = "1.0.0"

    def apply(self, builder: Builder) -> None:
        @builder.hooks.this_compilation.tap(self.name)
        def _wire(build: Build) -> None:
            @build.hooks.route.tap(self.name, stage=_SECTION_INDEX_STAGE)
            def _route(url: str, node: Node) -> str:
                return section_index_url(url, node.source_path)


def obsidian_section_index() -> ObsidianSectionIndexPlugin:
    """Factory for the ``_index.md`` section-page router."""
    return ObsidianSectionIndexPlugin()


def obsidian_plugins(
    *,
    include: Sequence[str] | None = None,
    exclude: Sequence[str] | None = None,
    publish_required: bool = False,
    publish_key: str = "publish",
    section_index: bool = True,
    highlight_style: str = "default",
    rss_title: str | None = None,
) -> list[Plugin]:
    """Return the full Obsidian-flavored plugin pipeline, in apply order.

    The default vault excludes (:data:`DEFAULT_VAULT_EXCLUDE`) are always applied;
    ``exclude`` adds to them and ``include`` (if given) restricts which files load.
    ``publish_required`` selects the publishing mode: the default ``False`` is a
    denylist (every note is published unless it sets ``publish: false``), suited to
    a whole-vault wiki; pass ``True`` for an allowlist (publish only ``publish:
    true`` notes). ``section_index`` (default on) routes Hugo-style ``_index.md``
    files to their directory root. Drop the result straight into a
    :class:`~pyssg.Config` (``Config(plugins=obsidian_plugins())``) or splice extra
    plugins after it.
    """
    vault_exclude: tuple[str, ...] = (*DEFAULT_VAULT_EXCLUDE, *(tuple(exclude) if exclude else ()))
    plugins: list[Plugin] = [
        directory_loader(include=include, exclude=vault_exclude),
        frontmatter(),
        markdown(),
        mermaid(),
        highlight(style=highlight_style),
        content_meta(),
        permalink(),
        wikilink(),
        link_resolver(),
        obsidian_attachments(exclude=vault_exclude),
        transclude(),
        publish_gate(key=publish_key, publish_required=publish_required),
        nav(),
        taxonomy(),
        sitemap(),
        rss(title=rss_title),
        asset_copy(),
        render(),
    ]
    if section_index:
        plugins.append(obsidian_section_index())
    return plugins
