"""Contrib plugin: gate which documents are published, by frontmatter flag.

Selective publishing for a personal-knowledge-base or draft workflow: only the
notes you mark are turned into pages, the rest stay private. The decision is read
from a single frontmatter key (``publish`` by default) and enforced through the
``route`` hook -- a suppressed document routes to the empty string, so the
permalink generator emits no page for it (and nothing links to a 404).

Two modes:

- **allowlist** (``publish_required=True``, the default): a document is published
  only when its flag is truthy (``publish: true``). This mirrors Obsidian Publish
  and is the safe default -- a note is private unless you opt it in.
- **denylist** (``publish_required=False``): every document is published *except*
  those whose flag is explicitly ``false`` (``publish: false``), i.e. opt-out.

It taps ``route`` at a late stage so its veto is final, after any other plugin
(e.g. i18n) has shaped the URL. The decision is a pure function of the document's
frontmatter and the static mode, so builds stay byte-identical and incremental
rebuilds equal full rebuilds; the mode and key are folded into ``cache_version``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pyssg.core.build import Build
    from pyssg.core.builder import Builder
    from pyssg.core.node import Node

# Late enough that the URL is final before we decide whether to keep the page;
# i18n routes at 500, so 600 runs after it.
_ROUTE_STAGE = 600


def should_publish(meta: dict[str, object], *, key: str, publish_required: bool) -> bool:
    """Whether a document with these frontmatter ``meta`` values is published.

    In allowlist mode (``publish_required=True``) the ``key`` value must be truthy.
    In denylist mode it is published unless the value is explicitly ``False``.
    """
    flag = meta.get(key)
    if publish_required:
        return bool(flag)
    return flag is not False


class PublishGatePlugin:
    """Suppresses pages for documents not selected for publishing."""

    name = "publish_gate"

    def __init__(self, *, key: str = "publish", publish_required: bool = True) -> None:
        self._key = key
        self._required = publish_required
        mode = "allow" if publish_required else "deny"
        self.cache_version = f"1.0.0:{mode}:{key}"

    def apply(self, builder: Builder) -> None:
        @builder.hooks.this_compilation.tap(self.name)
        def _wire(build: Build) -> None:
            @build.hooks.route.tap(self.name, stage=_ROUTE_STAGE)
            def _route(url: str, node: Node) -> str:
                if not url:
                    return url  # already suppressed upstream; nothing to add
                published = should_publish(
                    node.meta, key=self._key, publish_required=self._required
                )
                return url if published else ""


def publish_gate(*, key: str = "publish", publish_required: bool = True) -> PublishGatePlugin:
    """Factory used in ``pyssg.config.py``.

    ``key`` is the frontmatter field to read (default ``"publish"``).
    ``publish_required`` selects allowlist (default) vs denylist mode.
    """
    return PublishGatePlugin(key=key, publish_required=publish_required)
