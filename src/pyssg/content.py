"""Shared content model for tier-2 plugins.

This is NOT part of the kernel. Tier-2 plugins (Collections, Permalink,
Listing, Navigation) all read and write the same structures so a template only
ever learns one model: ``site`` / ``page`` / ``collections`` / ``menus``.
Keeping these definitions in one place is what prevents fragmentation -- there
is a single notion of "a grouped, ordered set of pages" (Collection) and a
single notion of "a named navigation tree" (NavNode), reused across every use
case (docs, blog, company site).

Conventions stored on ``build.meta``:

    build.meta["site"]        -> dict (site-wide config: title, base_url, ...)
    build.meta["collections"] -> dict[str, Collection]
    build.meta["menus"]       -> dict[str, list[NavNode]]

Conventions stored on ``source.meta`` (set by tier-2 plugins):

    source.meta["url"]         -> str  (pretty URL, e.g. "/blog/hello/")
    source.meta["output_path"] -> str  (path relative to the out dir)
    source.meta["generated"]   -> bool (True for synthetic pages)
    source.meta["prev"/"next"] -> Source (sequential nav, used by docs)
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pyssg.build import Build
from pyssg.models import Source

# build.meta keys
SITE = "site"
COLLECTIONS = "collections"
MENUS = "menus"

# source.meta keys
URL = "url"
OUTPUT_PATH = "output_path"
GENERATED = "generated"
PREV = "prev"
NEXT = "next"

# Collection kinds
KIND_TAG = "tag"
KIND_FOLDER = "folder"
KIND_CUSTOM = "custom"


@dataclass(slots=True)
class Collection:
    """An ordered group of pages.

    Tags, folder sections, blog posts and custom "featured" sets are all just
    collections differing in their ``kind`` and how they were assembled.
    """

    name: str
    kind: str
    pages: list[Source] = field(default_factory=list)
    meta: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class NavNode:
    """A node in a named navigation tree (menu, sidebar, footer)."""

    title: str
    url: str
    order: int = 0
    children: list[NavNode] = field(default_factory=list)
    source: Source | None = None


def site(build: Build) -> dict[str, object]:
    """Return the site-wide context, seeding it from ``config.options`` once."""

    value = build.meta.get(SITE)
    if isinstance(value, dict):
        return value
    seeded: dict[str, object] = dict(build.config.options)
    build.meta[SITE] = seeded
    return seeded


def collections(build: Build) -> dict[str, Collection]:
    """Return the collections registry, creating it on first access."""

    value = build.meta.get(COLLECTIONS)
    if isinstance(value, dict):
        return value
    fresh: dict[str, Collection] = {}
    build.meta[COLLECTIONS] = fresh
    return fresh


def menus(build: Build) -> dict[str, list[NavNode]]:
    """Return the menus registry, creating it on first access."""

    value = build.meta.get(MENUS)
    if isinstance(value, dict):
        return value
    fresh: dict[str, list[NavNode]] = {}
    build.meta[MENUS] = fresh
    return fresh


def is_generated(source: Source) -> bool:
    return bool(source.meta.get(GENERATED, False))


def is_draft(source: Source) -> bool:
    return bool(source.frontmatter.get("draft", False))


def url_to_output_path(url: str) -> str:
    """Map a public URL to its output file path (relative to the out dir)."""

    path = url.lstrip("/")
    if path == "" or path.endswith("/"):
        return path + "index.html"
    return path


def absolute_url(base_url: str, url: str) -> str:
    """Join a site base URL with a root-relative page URL.

    ``absolute_url("https://x.com/", "/blog/")`` -> ``"https://x.com/blog/"``.
    With an empty base URL the page URL is returned unchanged.
    """

    if not base_url:
        return url
    return base_url.rstrip("/") + "/" + url.lstrip("/")


def public_pages(build: Build) -> list[Source]:
    """Sources that produce a public HTML page: have a URL and are not drafts."""

    return [
        source
        for source in build.sources
        if source.meta.get(URL) and not is_draft(source)
    ]


def page_ref(source: Source) -> dict[str, object]:
    """A lightweight view of a page for use in list templates.

    Exposes ``url`` and the frontmatter (title, date, ...) as plain dict keys so
    templates can write ``item.url`` / ``item.title`` regardless of where the
    underlying data lives on the Source.
    """

    return {
        **source.frontmatter,
        URL: source.meta.get(URL, ""),
        "relpath": source.relpath.as_posix(),
    }
