"""Seo plugin: emit SEO and social head tags from frontmatter plus ``site``.

The plugin computes the data, the theme renders it -- mirroring how every other
tier-2 plugin exposes a model rather than HTML. Two taps:

- ``render`` (stage -100, before Template) builds a per-page ``seo`` struct on
  ``source.meta`` from the frontmatter and the ``site`` config.
- ``collect`` registers a ``seo()`` Jinja global through the shared
  ``build.meta["template_globals"]`` seam (Template merges it into the
  environment). The global renders the head block in Python -- so it works on a
  bare layout with just ``{{ seo() }}`` -- and a shipped ``partials/seo.html``
  wraps it as a no-Python override point for themes.

Template-tier plugin: ``jinja2``/``markupsafe`` are imported lazily, so this is
only needed when the Template plugin (the ``template`` extra) is in use.

Tags produced: ``<meta name="description">``, ``robots`` (noindex for drafts),
``<link rel="canonical">``, Open Graph, Twitter Card, and JSON-LD (``WebSite``
for the home page, ``Article``/``BlogPosting`` for dated pages).

Absolute URLs (canonical, og:url, og:image, JSON-LD) require ``site["base_url"]``;
when it is unset they are omitted and a single warning is emitted, since
crawlers ignore relative social tags.
"""

from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import TYPE_CHECKING

from pyssg.build import Build
from pyssg.builder import Builder
from pyssg.content import URL, absolute_url, is_draft, is_generated, site
from pyssg.errors import warn
from pyssg.models import Source
from pyssg.schema import FieldSpec

if TYPE_CHECKING:
    from markupsafe import Markup

# Seo runs before Template (default render stage 0) so the struct exists when
# the layout renders.
_RENDER_STAGE = -100

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


class Seo:
    def __init__(
        self,
        *,
        schema_type: str = "Article",
        twitter_handle: str | None = None,
        excerpt_chars: int = 160,
    ) -> None:
        self._schema_type = schema_type
        self._twitter_handle = twitter_handle
        self._excerpt_chars = excerpt_chars

    def apply(self, builder: Builder) -> None:
        builder.schema.declare(
            FieldSpec("description", type="str", example="A one-line page summary")
        )
        builder.schema.declare(FieldSpec("image", type="str", example="og-cover.png"))
        builder.schema.declare(FieldSpec("noindex", type="bool", example="true"))
        builder.schema.declare(FieldSpec("date", type="date", example="2026-01-31"))
        builder.schema.declare(FieldSpec("tags", type="list", example="[python, web]"))
        builder.hooks.collect.tap("Seo", self._collect)
        builder.hooks.render.tap("Seo", self._build, stage=_RENDER_STAGE)

    def _collect(self, build: Build) -> None:
        if not str(site(build).get("base_url", "")):
            warn(
                "Seo: site['base_url'] is not set, so canonical/og:url/og:image "
                "and JSON-LD are omitted. Set base_url for production SEO tags."
            )
        template_globals = build.meta.setdefault("template_globals", {})
        if isinstance(template_globals, dict):
            template_globals["seo"] = _make_seo_global()

    def _build(self, source: Source, build: Build) -> None:
        options = site(build)
        base_url = str(options.get("base_url", ""))
        frontmatter = source.frontmatter
        url = str(source.meta.get(URL, ""))

        title = str(frontmatter.get("title") or options.get("title") or "")
        description = self._description(source, options)
        is_home = source.relpath.stem == "index" and source.relpath.parent == Path(".")
        is_article = bool(frontmatter.get("date")) and not is_generated(source)
        canonical = absolute_url(base_url, url) if base_url and url else ""
        image = _image(frontmatter, options, base_url)
        published = _iso(frontmatter.get("date")) if is_article else ""
        modified = (_iso(frontmatter.get("lastmod")) or published) if is_article else ""

        model: dict[str, object] = {
            "title": title,
            "description": description,
            "canonical": canonical,
            "image": image,
            "type": "article" if is_article else "website",
            "site_name": str(options.get("title") or ""),
            "locale": str(options.get("locale") or ""),
            "twitter_card": "summary_large_image" if image else "summary",
            "twitter_site": self._twitter_handle or str(options.get("twitter") or ""),
            "noindex": is_draft(source) or bool(frontmatter.get("noindex", False)),
            "published": published,
            "modified": modified,
            "tags": _str_list(frontmatter.get("tags")),
        }
        model["jsonld"] = self._jsonld(
            source,
            options,
            title=title,
            description=description,
            canonical=canonical,
            image=image,
            is_article=is_article,
            is_home=is_home,
        )
        source.meta["seo"] = model

    def _description(self, source: Source, options: dict[str, object]) -> str:
        explicit = source.frontmatter.get("description") or source.frontmatter.get(
            "summary"
        )
        if isinstance(explicit, str) and explicit.strip():
            return explicit.strip()
        excerpt = _excerpt(source.content, self._excerpt_chars)
        if excerpt:
            return excerpt
        return str(options.get("description") or options.get("tagline") or "")

    def _jsonld(
        self,
        source: Source,
        options: dict[str, object],
        *,
        title: str,
        description: str,
        canonical: str,
        image: str,
        is_article: bool,
        is_home: bool,
    ) -> str:
        # Absolute URLs are required for meaningful structured data.
        if not canonical:
            return ""
        if is_article:
            data: dict[str, object] = {
                "@context": "https://schema.org",
                "@type": self._schema_type,
                "headline": title,
                "url": canonical,
                "mainEntityOfPage": canonical,
            }
            if description:
                data["description"] = description
            published = _iso(source.frontmatter.get("date"))
            if published:
                data["datePublished"] = published
            modified = _iso(source.frontmatter.get("lastmod")) or published
            if modified:
                data["dateModified"] = modified
            author = source.frontmatter.get("author") or options.get("author")
            if isinstance(author, str) and author:
                data["author"] = {"@type": "Person", "name": author}
            if image:
                data["image"] = image
        elif is_home:
            data = {
                "@context": "https://schema.org",
                "@type": "WebSite",
                "name": str(options.get("title") or ""),
                "url": canonical,
            }
            if description:
                data["description"] = description
        else:
            return ""
        # Escape the script-closing sequence so the JSON cannot break out of the
        # surrounding <script> element.
        return json.dumps(data, ensure_ascii=False).replace("</", "<\\/")


def _make_seo_global() -> object:
    """Build the ``seo()`` Jinja global that renders the head block.

    Uses ``pass_context`` so it reads ``page`` from the current render context;
    it needs no closure over the build, which keeps it valid across rebuilds.
    """

    import jinja2
    from markupsafe import Markup

    @jinja2.pass_context
    def seo(context: jinja2.runtime.Context) -> Markup:
        page = context.get("page")
        model = page.get("seo") if isinstance(page, dict) else None
        if not isinstance(model, dict):
            return Markup("")
        return Markup(_render_tags(model))

    return seo


def _render_tags(model: dict[str, object]) -> str:
    esc = html.escape
    title = str(model.get("title", ""))
    description = str(model.get("description", ""))
    canonical = str(model.get("canonical", ""))
    image = str(model.get("image", ""))
    lines: list[str] = []

    if description:
        lines.append(f'<meta name="description" content="{esc(description)}">')
    if model.get("noindex"):
        lines.append('<meta name="robots" content="noindex">')
    if canonical:
        lines.append(f'<link rel="canonical" href="{esc(canonical)}">')

    lines.append(f'<meta property="og:title" content="{esc(title)}">')
    if description:
        lines.append(f'<meta property="og:description" content="{esc(description)}">')
    lines.append(
        f'<meta property="og:type" content="{esc(str(model.get("type", "website")))}">'
    )
    if canonical:
        lines.append(f'<meta property="og:url" content="{esc(canonical)}">')
    site_name = str(model.get("site_name", ""))
    if site_name:
        lines.append(f'<meta property="og:site_name" content="{esc(site_name)}">')
    locale = str(model.get("locale", ""))
    if locale:
        lines.append(f'<meta property="og:locale" content="{esc(locale)}">')
    if image:
        lines.append(f'<meta property="og:image" content="{esc(image)}">')

    if model.get("type") == "article":
        published = str(model.get("published", ""))
        if published:
            lines.append(
                f'<meta property="article:published_time" content="{esc(published)}">'
            )
        modified = str(model.get("modified", ""))
        if modified:
            lines.append(
                f'<meta property="article:modified_time" content="{esc(modified)}">'
            )
        tags = model.get("tags")
        if isinstance(tags, list):
            for tag in tags:
                lines.append(f'<meta property="article:tag" content="{esc(str(tag))}">')

    twitter_card = esc(str(model.get("twitter_card", "summary")))
    lines.append(f'<meta name="twitter:card" content="{twitter_card}">')
    lines.append(f'<meta name="twitter:title" content="{esc(title)}">')
    if description:
        lines.append(f'<meta name="twitter:description" content="{esc(description)}">')
    if image:
        lines.append(f'<meta name="twitter:image" content="{esc(image)}">')
    twitter_site = str(model.get("twitter_site", ""))
    if twitter_site:
        lines.append(f'<meta name="twitter:site" content="{esc(twitter_site)}">')

    jsonld = str(model.get("jsonld", ""))
    if jsonld:
        lines.append(f'<script type="application/ld+json">{jsonld}</script>')

    return "\n".join(lines)


def _image(
    frontmatter: dict[str, object], options: dict[str, object], base_url: str
) -> str:
    raw = frontmatter.get("image") or options.get("og_image")
    if not isinstance(raw, str) or not raw:
        return ""
    if raw.startswith(("http://", "https://")):
        return raw
    return absolute_url(base_url, raw) if base_url else ""


def _excerpt(content: str, limit: int) -> str:
    if not content:
        return ""
    text = _WS_RE.sub(" ", _TAG_RE.sub(" ", content)).strip()
    if not text:
        return ""
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0].rstrip()
    return (cut or text[:limit]) + "…"


def _iso(value: object) -> str:
    return value if isinstance(value, str) and value else ""


def _str_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    return []
