from __future__ import annotations

from pygments.formatters import HtmlFormatter

from pyssg.contrib.apidoc import apidoc
from pyssg.contrib.external_links import external_links
from pyssg.contrib.graph import graph
from pyssg.contrib.llms import llms
from pyssg.plugins import i18n
from pyssg.presets import docs

# The pyssg documentation site is itself built with pyssg (dogfooding). It uses
# the `docs` preset and adds three plugins:
#
#   * apidoc         - statically extracts docstrings from the `pyssg` package
#                      and publishes them as a "References" section.
#   * external_links - opens off-site links in a new tab with rel="noopener".
#   * i18n           - directory-based locales: content/en (default, served at the
#                      root) and content/vi (served under /vi/).
#   * llms           - emits /llms.txt, /llms-full.txt and (markdown_pages) a raw
#                      <page>.md per page for AI/IDE agents. The `vi` section is
#                      excluded so the index stays a focused English mirror of the
#                      docs (the localized pages would just duplicate content for
#                      an LLM consumer).
#
# `package="../pyssg"` is resolved against this site directory (docs/), so it
# points at the project's `pyssg/` package one level up. The apidoc route lives
# under the default locale (`/en/references/`) so the i18n router keeps it (it
# strips the `/en/` prefix, serving the shared, code-derived References at
# `/references/`); content outside a locale directory would otherwise be dropped.

# Dark-mode code highlighting. The `highlight` plugin already provides the light
# stylesheet as site["highlight_css"]; here we generate a dark one (Nord, to match
# the theme's dark palette), scoped to `[data-theme="dark"] .highlight` so it only
# applies once the theme switcher (or the no-flash script) selects dark mode.
_DARK_HIGHLIGHT_CSS = HtmlFormatter(style="nord").get_style_defs('[data-theme="dark"] .highlight')

config = docs(
    site={
        "title": "pyssg",
        "description": "A fast, incremental static site generator for Markdown.",
        "highlight_css_dark": _DARK_HIGHLIGHT_CSS,
        # Explicit sidebar section order (by content directory; "" is the home
        # page). The nav plugin emits sections alphabetically, so the theme
        # reorders them using this list; sections not listed fall back to the end.
        "menu_order": [
            "",
            "tutorial",
            "how-to",
            "integrations",
            "reference",
            "explanation",
            "references",
        ],
    },
    base_url="https://pyssg.nkthanh.dev",
    # Custom layout converted from the Hugo "Book" theme (docs/layouts/book).
    layout="layouts/book",
    extra_plugins=[
        apidoc(package="../pyssg", route="/en/references/"),
        external_links(),
        i18n(default_locale="en", locales=["en", "vi"]),
        llms(exclude=("vi",), markdown_pages=True),
        # Interactive document graph: a full-page view at /graph/. Like llms it
        # mirrors the English docs only (the localized `vi` tree would just
        # duplicate the structure) and groups nodes by top-level section for
        # colour. `drop_orphans` hides the many auto-generated API reference pages
        # that carry no cross-links, keeping the map focused on the hand-written,
        # interlinked prose docs. `local=True` renders each page's neighbourhood
        # into the book theme's right sidebar, which provides the
        # `<!-- pyssg:local-graph -->` placeholder.
        graph(exclude=("vi/*",), group_by="folder", drop_orphans=True, local=True),
    ],
)
