"""Render-context assembly shared by the render plugin.

Builds the template context for a page from the graph and ``build.site_data``
(filled by the nav/taxonomy plugins during ``evaluate_collections``). Every
lookup is defensive: a minimal site that loads none of the nav/taxonomy plugins
still renders (the extra keys are just empty), which keeps the basic pipeline and
its golden tests working unchanged.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pyssg.core.incremental.hashing import digest
from pyssg.core.node import Document
from pyssg.core.types import ConnectionKind

if TYPE_CHECKING:
    from collections.abc import Callable

    from pyssg.core.build import Build
    from pyssg.core.node import Page

# A small ordered/linked record: {"title": ..., "url": ...}.
type Crumb = dict[str, str]


def _public_meta(meta: dict[str, object]) -> dict[str, object]:
    return {k: v for k, v in meta.items() if not k.startswith("__") and k != "content_html"}


def _as_str_list(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(v) for v in value]
    return []


def _url_titles(build: Build) -> dict[str, str]:
    raw = build.site_data.get("url_titles")
    if isinstance(raw, dict):
        return {str(k): str(v) for k, v in raw.items()}
    return {}


def _i18n_data(build: Build) -> dict[str, object]:
    raw = build.site_data.get("i18n")
    return raw if isinstance(raw, dict) else {}


def _languages(build: Build) -> list[str]:
    """All configured locale codes (empty when the i18n plugin is not loaded)."""
    langs = _i18n_data(build).get("languages")
    return [str(code) for code in langs] if isinstance(langs, list) else []


def _default_locale(build: Build) -> str:
    """The default locale code (empty when the i18n plugin is not loaded)."""
    value = _i18n_data(build).get("default_locale")
    return str(value) if isinstance(value, str) else ""


def make_translator(
    strings: dict[str, dict[str, str]], lang: str, default_locale: str
) -> Callable[..., str]:
    """Build the ``t(key, **vars)`` callable templates use to localise UI strings.

    Lookup falls back ``lang -> default_locale -> key`` so a missing translation
    degrades to the default language and finally to the key itself (visible, easy
    to spot). ``**vars`` are interpolated with :meth:`str.format`; a malformed
    template or missing variable falls back to the raw string rather than raising,
    keeping a render robust against an incomplete translation table.
    """
    lang_table = strings.get(lang, {})
    default_table = strings.get(default_locale, {})

    def t(key: str, **fmt: object) -> str:
        value = lang_table.get(key)
        if value is None:
            value = default_table.get(key)
        if value is None:
            return key
        if fmt:
            try:
                return value.format(**fmt)
            except (KeyError, IndexError, ValueError):
                return value
        return value

    return t


def _page_i18n(build: Build, page: Page) -> tuple[str, list[object]]:
    """``(lang, translations)`` for a page; ``("", [])`` when not localised."""
    by_url = _i18n_data(build).get("by_url")
    if isinstance(by_url, dict):
        entry = by_url.get(page.url)
        if isinstance(entry, dict):
            translations = entry.get("translations")
            tr_list = translations if isinstance(translations, list) else []
            return str(entry.get("lang", "")), tr_list
    return "", []


def page_url_of(build: Build, doc_id: str) -> str | None:
    """URL of the page generated from a document (permalink id convention)."""
    page = build.graph.get(f"page:{doc_id}")
    if page is not None and hasattr(page, "url"):
        return str(page.url)
    return None


def doc_locale(doc: Document | None) -> str:
    """Locale tag a document carries, or ``""`` when it is not localised.

    The i18n plugin stamps ``meta["lang"]`` on every document under a locale
    directory (see :mod:`pyssg.plugins.i18n`). Summarizer plugins
    (rss/taxonomy/collections) read it to partition their generated pages per
    locale. A site without i18n leaves the tag unset, so this returns ``""`` and
    callers collapse to single-locale behaviour.
    """
    if doc is None:
        return ""
    lang = doc.meta.get("lang")
    return lang if isinstance(lang, str) else ""


def locale_root(locale: str, sample_url: str) -> str:
    """URL root under which a locale's generated pages live.

    Returns ``"/{locale}/"`` when that locale's pages are URL-prefixed -- every
    non-default locale is, per the i18n routing rule -- and ``"/"`` otherwise:
    the default locale is served at the site root, as is a site with no i18n. The
    decision is read straight from a representative member URL (``sample_url``),
    so it needs neither knowledge of which locale is the default nor any ordering
    against the i18n plugin's own pass.
    """
    if locale and sample_url.startswith(f"/{locale}/"):
        return f"/{locale}/"
    return "/"


def localize_route(route: str, root: str) -> str:
    """Re-root an absolute ``route`` (``"/"``, ``"/blog/"``) under a locale ``root``.

    ``root`` is a value returned by :func:`locale_root`. For the default root
    (``"/"``) the route is returned unchanged; for ``"/en/"`` the locale segment
    is prepended (``"/blog/"`` -> ``"/en/blog/"``, ``"/"`` -> ``"/en/"``).
    """
    if root == "/":
        return route
    return root.rstrip("/") + route


def _breadcrumbs(build: Build, page: Page) -> list[Crumb]:
    titles = _url_titles(build)
    crumbs: list[Crumb] = [{"title": titles.get("/", "Home"), "url": "/"}]
    acc = ""
    for segment in (s for s in page.url.split("/") if s):
        acc += "/" + segment
        url = acc + "/"
        crumbs.append({"title": titles.get(url, segment), "url": url})
    # Drop the final crumb if it duplicates the current page's own entry.
    return crumbs


def _backlinks(build: Build, doc: Document | None) -> list[Crumb]:
    if doc is None:
        return []
    out: list[Crumb] = []
    seen: set[str] = set()
    for conn in build.graph.in_edges(doc.id, ConnectionKind.LINK):
        if conn.src in seen:
            continue
        seen.add(conn.src)
        src = build.graph.get(conn.src)
        if src is None:
            continue
        title = src.meta.get("title")
        url = page_url_of(build, conn.src) or "#"
        out.append({"title": str(title) if title else conn.src, "url": url})
    return sorted(out, key=lambda b: b["url"])


def _prev_next(build: Build, page: Page) -> tuple[Crumb | None, Crumb | None]:
    ordered = build.site_data.get("ordered_pages")
    if not isinstance(ordered, list):
        return None, None
    items = [item for item in ordered if isinstance(item, dict)]
    urls = [str(item.get("url")) for item in items]
    if page.url not in urls:
        return None, None
    i = urls.index(page.url)
    # Keep prev/next within the current page's locale (ordered_pages is grouped by
    # locale), so navigation never jumps from one language into another.
    locale = items[i].get("locale")
    prev = items[i - 1] if i > 0 and items[i - 1].get("locale") == locale else None
    nxt = items[i + 1] if i + 1 < len(items) and items[i + 1].get("locale") == locale else None
    return _crumb(prev), _crumb(nxt)


def _crumb(item: object) -> Crumb | None:
    if isinstance(item, dict):
        return {"title": str(item.get("title", "")), "url": str(item.get("url", ""))}
    return None


def build_page_context(build: Build, page: Page) -> dict[str, object]:
    """Assemble the full template context for ``page``."""
    config = build.builder.config
    doc = build.graph.get(page.generated_from[0]) if page.generated_from else None

    # A page either renders a source document or is virtual (term/index page),
    # in which case its own meta carries the data the template needs.
    source: dict[str, object] = doc.meta if isinstance(doc, Document) else page.meta
    meta = _public_meta(source)
    content_html = ""
    raw_html = source.get("content_html")
    if isinstance(raw_html, str):
        content_html = raw_html
    # The render cache key folds content via this digest instead of the large
    # html string. A document page reuses the doc's precomputed aspect hash; a
    # virtual page (sitemap/rss/collection index) carries its payload inline in
    # ``content_html`` with no source doc, so hash that directly -- otherwise a
    # summarizer whose body changes but whose other context is unchanged would
    # be served a stale render from cache.
    content_digest = (
        doc.hashes.get("content_html", "")
        if isinstance(doc, Document)
        else digest("inline_content_html", content_html)
    )

    site: dict[str, object] = {}
    if config is not None:
        site = {**config.site, "base_url": config.base_url}

    # Effective theme options: the active layout's declared defaults overlaid by
    # the site's per-key overrides (``Config.theme``). Resolved here, alongside
    # ``site``, so every template sees a single ``theme`` mapping; the layout
    # only declares defaults and the engine owns the merge.
    theme: dict[str, object] = {}
    layout = build.builder.layout
    if layout is not None:
        theme.update(layout.options)
    if config is not None:
        theme.update(config.theme)

    prev, nxt = _prev_next(build, page)
    doc_typed = doc if isinstance(doc, Document) else None
    lang, translations = _page_i18n(build, page)
    return {
        "page": {**meta, "url": page.url},
        "site": site,
        "theme": theme,
        "lang": lang,
        "translations": translations,
        "languages": _languages(build),
        "default_locale": _default_locale(build),
        "content_html": content_html,
        "__content_digest__": content_digest,
        "collections": {},
        "menu": build.site_data.get("menu", []),
        "all_tags": build.site_data.get("all_tags", []),
        "breadcrumbs": _breadcrumbs(build, page),
        "backlinks": _backlinks(build, doc_typed),
        "toc": meta.get("toc", []),
        "tags": _as_str_list(meta.get("tags")),
        "reading_time": meta.get("reading_time"),
        "excerpt": meta.get("excerpt"),
        "prev": prev,
        "next": nxt,
    }
