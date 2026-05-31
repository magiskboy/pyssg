"""Built-in plugins.

Tier 1: ReadFile, Frontmatter, Markdown, Template, WriteFile -- a 1-to-1
markdown-to-HTML build. Markdown and Template require optional third party
libraries (the ``markdown`` / ``template`` extras); the kernel stays
dependency-free.

Tier 2: Permalink, Collections, Listing, Navigation -- flexible structure for
docs, blogs and company sites. They share one content model (see
``pyssg.content``) so a template only ever learns ``site`` / ``page`` /
``collections`` / ``menus``. See ``pyssg_cli.presets`` for ready-made stacks.
"""

from __future__ import annotations

from pyssg_plugins.collections import Collections
from pyssg_plugins.dev_server import DevServer
from pyssg_plugins.fingerprint import Fingerprint
from pyssg_plugins.frontmatter import Frontmatter
from pyssg_plugins.highlight import Highlight
from pyssg_plugins.i18n import I18n
from pyssg_plugins.link_resolver import LinkResolver
from pyssg_plugins.listing import Listing
from pyssg_plugins.markdown import Markdown
from pyssg_plugins.markdown_page import MarkdownPage
from pyssg_plugins.minify import Minify
from pyssg_plugins.navigation import Navigation
from pyssg_plugins.permalink import Permalink
from pyssg_plugins.read_file import ReadFile
from pyssg_plugins.redirects import Redirects
from pyssg_plugins.robots import Robots
from pyssg_plugins.rss import Rss
from pyssg_plugins.seo import Seo
from pyssg_plugins.sitemap import Sitemap
from pyssg_plugins.static_files import StaticFiles
from pyssg_plugins.stats import Statistics
from pyssg_plugins.template import Template
from pyssg_plugins.write_file import WriteFile

__all__ = [
    "Collections",
    "DevServer",
    "Fingerprint",
    "Frontmatter",
    "Highlight",
    "I18n",
    "LinkResolver",
    "Listing",
    "Markdown",
    "MarkdownPage",
    "Minify",
    "Navigation",
    "Permalink",
    "ReadFile",
    "Redirects",
    "Robots",
    "Rss",
    "Seo",
    "Sitemap",
    "StaticFiles",
    "Statistics",
    "Template",
    "WriteFile",
]
