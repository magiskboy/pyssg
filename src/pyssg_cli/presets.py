"""Presets: ready-made plugin stacks for the three target use cases.

A preset is just a function returning a list of plugin instances in the right
order, so beginners write one line while power users keep the freedom to
assemble plugins by hand:

    from pyssg_cli.presets import docs
    plugins = docs()

- ``docs()`` -- technical documentation: folder-based sidebar with prev/next.
- ``blog()`` -- personal blog: paginated index, tag pages, top menu, RSS.
- ``site()`` -- company/organisation site: flat top menu, standalone pages.

All presets accept ``sitemap``, ``minify``, ``robots`` and ``markdown_pages``
flags to enable the matching tier-3 plugin, ``seo`` (on by default) for
SEO/social head tags and ``highlight`` to syntax-highlight fenced code blocks
with Pygments; ``blog()`` also generates an RSS feed by default.
"""

from __future__ import annotations

from collections.abc import Sequence

from pyssg.plugin import Plugin
from pyssg_plugins.collections import Collections
from pyssg_plugins.frontmatter import Frontmatter
from pyssg_plugins.highlight import Highlight
from pyssg_plugins.listing import Listing
from pyssg_plugins.markdown import Markdown
from pyssg_plugins.markdown_page import MarkdownPage
from pyssg_plugins.minify import Minify
from pyssg_plugins.navigation import Navigation
from pyssg_plugins.permalink import Permalink
from pyssg_plugins.read_file import ReadFile
from pyssg_plugins.robots import Robots
from pyssg_plugins.rss import Rss
from pyssg_plugins.seo import Seo
from pyssg_plugins.sitemap import Sitemap
from pyssg_plugins.template import Template
from pyssg_plugins.write_file import WriteFile


def _head(markdown_extensions: Sequence[str], highlight: bool) -> list[Plugin]:
    head: list[Plugin] = [
        ReadFile(),
        Frontmatter(),
        Markdown(extensions=markdown_extensions),
    ]
    if highlight:
        head.append(Highlight(dark_style="github-dark"))
    return head


def _extras(
    *, sitemap: bool, minify: bool, robots: bool, markdown_pages: bool
) -> list[Plugin]:
    extras: list[Plugin] = []
    if sitemap:
        extras.append(Sitemap())
    if robots:
        extras.append(Robots())
    if markdown_pages:
        extras.append(MarkdownPage())
    if minify:
        extras.append(Minify())
    return extras


def _tail(template_dir: str, clean: bool) -> list[Plugin]:
    return [Template(directory=template_dir), WriteFile(clean=clean)]


def docs(
    *,
    markdown_extensions: Sequence[str] = (),
    template_dir: str = "layouts",
    clean: bool = True,
    sitemap: bool = False,
    minify: bool = False,
    robots: bool = False,
    markdown_pages: bool = False,
    seo: bool = True,
    highlight: bool = False,
) -> list[Plugin]:
    return [
        *_head(markdown_extensions, highlight),
        Permalink(),
        Collections(by_tag=False, by_folder=True),
        Navigation(mode="folder", sequential=True),
        *_extras(
            sitemap=sitemap,
            minify=minify,
            robots=robots,
            markdown_pages=markdown_pages,
        ),
        *([Seo(schema_type="Article")] if seo else []),
        *_tail(template_dir, clean),
    ]


def blog(
    *,
    page_size: int = 10,
    markdown_extensions: Sequence[str] = (),
    template_dir: str = "layouts",
    clean: bool = True,
    rss: bool = True,
    sitemap: bool = False,
    minify: bool = False,
    robots: bool = False,
    markdown_pages: bool = False,
    seo: bool = True,
    highlight: bool = False,
) -> list[Plugin]:
    plugins: list[Plugin] = [
        *_head(markdown_extensions, highlight),
        Permalink(),
        Collections(by_tag=True, by_folder=True),
        Listing(
            collection="blog", base_url="/blog/", title="Blog", page_size=page_size
        ),
        Listing(kind="tag", base_url="/tags/:name/", title=":name"),
        Navigation(mode="frontmatter"),
    ]
    if rss:
        plugins.append(Rss(collection="blog"))
    plugins.extend(
        _extras(
            sitemap=sitemap,
            minify=minify,
            robots=robots,
            markdown_pages=markdown_pages,
        )
    )
    if seo:
        plugins.append(Seo(schema_type="BlogPosting"))
    plugins.extend(_tail(template_dir, clean))
    return plugins


def site(
    *,
    markdown_extensions: Sequence[str] = (),
    template_dir: str = "layouts",
    clean: bool = True,
    sitemap: bool = False,
    minify: bool = False,
    robots: bool = False,
    markdown_pages: bool = False,
    seo: bool = True,
    highlight: bool = False,
) -> list[Plugin]:
    return [
        *_head(markdown_extensions, highlight),
        Permalink(),
        Navigation(mode="frontmatter"),
        *_extras(
            sitemap=sitemap,
            minify=minify,
            robots=robots,
            markdown_pages=markdown_pages,
        ),
        *([Seo(schema_type="Article")] if seo else []),
        *_tail(template_dir, clean),
    ]
