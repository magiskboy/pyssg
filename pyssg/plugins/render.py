"""Render plugin.

Terminal render step: takes a generated ``Page``, builds the template context
``{page, site, collections, content_html, ...}`` and renders it via
the layout's Jinja2 templates. The context is enriched with site-wide derived
data (nav menu, breadcrumbs, prev/next, backlinks, tags, toc) read from the
graph and ``build.site_data`` so templates stay simple.

The render is cache-backed: the cache key is a digest of every context input
(with the large ``content_html`` folded in by hash), so an unchanged page is a
cache hit during the per-build render sweep.

Third-party (``Jinja2``) is confined to this peripheral plugin.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from pyssg.core.incremental.cache import cached
from pyssg.core.incremental.hashing import digest
from pyssg.core.node import Page
from pyssg.core.types import Phase
from pyssg.plugins._context import build_page_context

if TYPE_CHECKING:
    from pyssg.core.build import Build
    from pyssg.core.builder import Builder


class RenderPlugin:
    """Renders pages through the layout's Jinja2 templates."""

    name = "render"
    cache_version = "1.1.0"

    def apply(self, builder: Builder) -> None:
        layout = builder.layout
        env: Environment | None = None
        if layout is not None:
            env = Environment(
                loader=FileSystemLoader(str(layout.templates_dir)),
                autoescape=select_autoescape(default=False),
                undefined=StrictUndefined,
                auto_reload=False,
            )

        @builder.hooks.this_compilation.tap(self.name)
        def _wire(build: Build) -> None:
            @build.hooks.render_page.tap(self.name)
            def _render(_html: str, page: Page) -> str:
                return self._render_page(build, env, page)

    def _render_page(self, build: Build, env: Environment | None, page: Page) -> str:
        context = build_page_context(build, page)
        content_html = str(context.get("content_html", ""))
        layout = build.builder.layout
        if env is None or layout is None:
            return content_html

        template_name = page.template or layout.default_template
        # Cache key folds in every context input (content_html by hash) plus the
        # pipeline/plugin/config versions, so an unchanged page is a cache hit.
        key_context = {k: v for k, v in context.items() if k != "content_html"}
        key = digest(
            "render",
            page.id,
            template_name,
            key_context,
            context.get("__content_digest__", ""),
            build.plugin_set_version,
            build.relevant_config(Phase.RENDER),
        )
        render_context = {k: v for k, v in context.items() if not k.startswith("__")}
        return cached(
            build,
            key,
            lambda: env.get_template(template_name).render(**render_context),
        )


def render() -> RenderPlugin:
    """Factory used in ``pyssg.config.py``."""
    return RenderPlugin()
