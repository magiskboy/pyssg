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
from pyssg.plugins._context import build_page_context, make_translator
from pyssg.plugins.i18n import discover_locales, load_strings

if TYPE_CHECKING:
    from pyssg.core.build import Build
    from pyssg.core.builder import Builder

# Ultimate fallback locale: a theme ships its base UI strings as ``en.toml``, so a
# single-language site with no i18n plugin still resolves ``t(...)`` to real text.
_BASE_LOCALE = "en"


def _default_locale(build: Build) -> str:
    """The i18n routing plugin's default locale, or ``""`` when it is not loaded."""
    data = build.site_data.get("i18n")
    return str(data.get("default_locale", "")) if isinstance(data, dict) else ""


class RenderPlugin:
    """Renders pages through the layout's Jinja2 templates."""

    name = "render"
    # 1.2.0: template=None now emits the body raw (no layout) even when a layout
    # exists, so previously-wrapped summarizer outputs must be re-rendered.
    cache_version = "1.2.0"

    def apply(self, builder: Builder) -> None:
        layout = builder.layout
        env: Environment | None = None
        # UI-string tables for the translator ``t``. Loaded once here (like the
        # Jinja env) and independently of the i18n routing plugin, so even a
        # single-language site gets its theme's strings. A digest of the slices a
        # page reads is folded into the render cache key.
        strings: dict[str, dict[str, str]] = {}
        if layout is not None:
            env = Environment(
                loader=FileSystemLoader(str(layout.templates_dir)),
                autoescape=select_autoescape(default=False),
                undefined=StrictUndefined,
                auto_reload=False,
            )
            theme_dir = layout.root / "i18n"
            site_dir = builder.site_dir / "i18n"
            strings = load_strings(theme_dir, site_dir, discover_locales(theme_dir, site_dir))

        @builder.hooks.this_compilation.tap(self.name)
        def _wire(build: Build) -> None:
            @build.hooks.render_page.tap(self.name)
            def _render(_html: str, page: Page) -> str:
                return self._render_page(build, env, strings, page)

    def _render_page(
        self, build: Build, env: Environment | None, strings: dict[str, dict[str, str]], page: Page
    ) -> str:
        context = build_page_context(build, page)
        content_html = str(context.get("content_html", ""))
        layout = build.builder.layout
        # ``template is None`` means "emit the body verbatim, no layout": regular
        # pages are given a concrete template by the permalink plugin, so a None
        # here is a summarizer page (sitemap/rss/llms). Without a layout/env every
        # page is emitted raw.
        if env is None or layout is None or page.template is None:
            return content_html

        template_name = page.template
        lang = str(context.get("lang", ""))
        # The i18n routing plugin (when loaded) names the site's default locale;
        # otherwise fall back to the theme base so a single-language site resolves.
        default_locale = _default_locale(build) or _BASE_LOCALE
        # Cache key folds in every context input (content_html by hash) plus the
        # pipeline/plugin/config versions, so an unchanged page is a cache hit. The
        # i18n digest covers the only template-namespace input not already in the
        # context: the string slices the translator can read for this page.
        key_context = {k: v for k, v in context.items() if k != "content_html"}
        key = digest(
            "render",
            page.id,
            template_name,
            key_context,
            context.get("__content_digest__", ""),
            digest("i18n", strings.get(lang, {}), strings.get(default_locale, {})),
            build.plugin_set_version,
            build.relevant_config(Phase.RENDER),
        )
        render_context = {k: v for k, v in context.items() if not k.startswith("__")}
        # The translator is a closure, not a hashable input -- it is fully captured
        # by the i18n digest above, so inject it only into the template namespace.
        render_context["t"] = make_translator(strings, lang, default_locale)
        return cached(
            build,
            key,
            lambda: env.get_template(template_name).render(**render_context),
        )


def render() -> RenderPlugin:
    """Factory used in ``pyssg.config.py``."""
    return RenderPlugin()
