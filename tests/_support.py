"""Shared helpers for the end-to-end test suite.

Every test that builds a real site does so from the single content fixture under
``tests/fixtures/custom`` (a frozen copy of ``examples/custom``: the ``blog``
preset wearing a locally ejected, customized theme). Centralising the two
operations these tests used to copy-paste -- snapshotting an output tree and
staging/building a fixture site -- keeps the suite anchored to one fixture and
one build routine.

A test that needs a different preset, theme, or plugin wiring passes its own
``config`` text (which replaces the fixture's ``pyssg.config.py``) and, for the
source-only gallery themes, a ``vendor_theme`` name to copy into the site under
``theme/``. The content under ``content/`` is the constant across all of them.
"""

from __future__ import annotations

import shutil
from pathlib import Path

#: Root of the on-disk test fixtures (``tests/fixtures``).
FIXTURES = Path(__file__).resolve().parent / "fixtures"

#: Repo-root ``themes/`` gallery (source-only, not shipped in the wheel). Gallery
#: themes are referenced by path because they are not importable via
#: ``pyssg.themes.theme_path``.
THEMES = Path(__file__).resolve().parents[1] / "themes"

#: The single content fixture every end-to-end test builds from.
DEFAULT_FIXTURE = "custom"


def files_under(root: Path) -> dict[str, str]:
    """Snapshot every file under ``root`` as ``{relative posix path: text}``.

    Used to compare a build's ``dist`` against a committed golden tree and to
    assert two builds are byte-identical. Paths are POSIX-normalised so the
    mapping is stable across operating systems; ordering is irrelevant because
    the result is a dict compared by value.
    """
    return {
        p.relative_to(root).as_posix(): p.read_text(encoding="utf-8")
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


def stage_site(
    tmp_path: Path,
    *,
    fixture: str = DEFAULT_FIXTURE,
    config: str | None = None,
    vendor_theme: str | None = None,
    name: str = "site",
) -> Path:
    """Copy a fixture into ``tmp_path`` and return the staged site directory.

    The build's ``dist`` therefore never touches the repository. ``config``, when
    given, replaces the fixture's ``pyssg.config.py`` so one content fixture can
    be driven through any preset/theme/plugin wiring. ``vendor_theme`` copies a
    repo-root gallery theme into the site under ``theme/`` (matching a
    ``layout="theme"`` config), the same way a user adopts a gallery theme.
    ``name`` disambiguates multiple sites staged under the same ``tmp_path``
    (e.g. two builds for a determinism check).
    """
    site = tmp_path / name
    shutil.copytree(FIXTURES / fixture, site)
    if config is not None:
        (site / "pyssg.config.py").write_text(config, encoding="utf-8")
    if vendor_theme is not None:
        shutil.copytree(THEMES / vendor_theme, site / "theme")
    return site


def build_site_from_fixture(
    tmp_path: Path,
    *,
    fixture: str = DEFAULT_FIXTURE,
    config: str | None = None,
    vendor_theme: str | None = None,
    name: str = "site",
) -> Path:
    """Stage a fixture site, build it, and return its ``dist`` directory.

    Thin wrapper over :func:`stage_site` plus :func:`pyssg.cli.build_site`. The
    import is local so importing this module stays cheap and stdlib-only.
    """
    from pyssg.cli import build_site

    site = stage_site(
        tmp_path,
        fixture=fixture,
        config=config,
        vendor_theme=vendor_theme,
        name=name,
    )
    build_site(site)
    return site / "dist"


#: The "assemble the plugins yourself" baseline: a bare ``Config`` with an
#: explicit plugin list (no preset, no theme, no aggregator plugins) and a
#: minimal hand-written layout. Every output is a single cached page render --
#: no feed/sitemap/taxonomy aggregations -- which is exactly what the docs-min
#: golden snapshot and the cache-reuse invariant both need.
MINIMAL_CONFIG = """\
from __future__ import annotations

from pyssg import Config
from pyssg.plugins import (
    directory_loader,
    frontmatter,
    markdown,
    permalink,
    render,
)

config = Config(
    content_dir="content",
    output_dir="dist",
    layout="layouts/page",
    base_url="https://example.com",
    site={"title": "Docs Min"},
    plugins=[
        directory_loader(),
        frontmatter(),
        markdown(),
        permalink(),
        render(),
    ],
)
"""

_MINIMAL_LAYOUT_TOML = 'name = "page"\nversion = "0.1.0"\ndefault_template = "page.html.j2"\n'

_MINIMAL_PAGE_TEMPLATE = """\
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{{ page.title }} | {{ site.title }}</title>
<link rel="canonical" href="{{ site.base_url }}{{ page.url }}">
</head>
<body>
<main>
{{ content_html }}</main>
</body>
</html>
"""


def stage_minimal_site(tmp_path: Path, *, name: str = "site") -> Path:
    """Stage the shared content fixture with the bare :data:`MINIMAL_CONFIG` and
    a minimal hand-written layout, returning the staged site directory.

    Shared by the docs-min golden snapshot (which builds it once) and the
    cache-reuse invariant (which builds it twice in place), so the minimal site
    is defined in exactly one place.
    """
    site = stage_site(tmp_path, config=MINIMAL_CONFIG, name=name)
    layout = site / "layouts" / "page"
    (layout / "templates").mkdir(parents=True)
    (layout / "layout.toml").write_text(_MINIMAL_LAYOUT_TOML, encoding="utf-8")
    (layout / "templates" / "page.html.j2").write_text(_MINIMAL_PAGE_TEMPLATE, encoding="utf-8")
    return site
