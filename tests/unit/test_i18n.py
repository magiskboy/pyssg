"""Unit tests for the i18n plugin (M1: locale model + routing).

Covers the pure helpers (locale detection, translation key, routed URL) and an
end-to-end build asserting the directory-based routing rule: the default locale
is served at the root, other locales keep their prefix, and content outside any
locale directory produces no output.
"""

from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path

from pyssg.cli import build_site, make_builder
from pyssg.core.errors import ConfigError
from pyssg.core.incremental.cache import FsCache
from pyssg.core.phases import IncrementalSession
from pyssg.plugins._context import make_translator
from pyssg.plugins.i18n import i18n, load_strings, locale_of, route_url, translation_key
from pyssg.watch import FsEvent, coalesce

_LOCALES = frozenset({"en", "vi"})

CONFIG_TEXT = """\
from __future__ import annotations

from pyssg import Config
from pyssg.plugins import (
    directory_loader,
    frontmatter,
    i18n,
    markdown,
    permalink,
    render,
)

config = Config(
    content_dir="content",
    output_dir="dist",
    layout="layout",
    base_url="https://example.com",
    site={"title": "I18n"},
    plugins=[
        directory_loader(),
        frontmatter(),
        markdown(),
        i18n(default_locale="en", locales=["en", "vi"]),
        permalink(),
        render(),
    ],
)
"""

# A template that echoes the page's locale and a language switcher built from the
# i18n context (`lang`, `translations`, `languages`) so build tests can assert it.
PAGE_TEMPLATE = (
    "<!doctype html><title>{{ page.title }}</title>"
    '<p data-lang="{{ lang }}" data-langs="{{ languages|join(",") }}">{{ content_html }}</p>'
    '<nav class="i18n">'
    "{% for t in translations %}"
    '<a hreflang="{{ t.lang }}" href="{{ t.url }}">{{ t.title }}</a>'
    "{% endfor %}</nav>\n"
)


def _doc(title: str) -> str:
    return f"---\ntitle: {title}\n---\nbody of {title}\n"


def _write_site(site: Path, content: dict[str, str]) -> None:
    site.mkdir(parents=True, exist_ok=True)
    (site / "pyssg.config.py").write_text(CONFIG_TEXT, encoding="utf-8")
    tpl = site / "layout" / "templates"
    tpl.mkdir(parents=True, exist_ok=True)
    (site / "layout" / "layout.toml").write_text(
        'name="i18n"\nversion="0"\ndefault_template="page.html.j2"\n', encoding="utf-8"
    )
    (tpl / "page.html.j2").write_text(PAGE_TEMPLATE, encoding="utf-8")
    for rel, text in content.items():
        path = site / "content" / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


def _outputs(root: Path) -> set[str]:
    return {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}


class LocaleHelpersTest(unittest.TestCase):
    def test_locale_of_matches_first_segment(self) -> None:
        self.assertEqual(locale_of("en/guide/intro.md", _LOCALES), "en")
        self.assertEqual(locale_of("vi/guide/intro.md", _LOCALES), "vi")

    def test_locale_of_returns_none_outside_locale_dir(self) -> None:
        self.assertIsNone(locale_of("about.md", _LOCALES))
        self.assertIsNone(locale_of("blog/post.md", _LOCALES))
        # A file literally named like a locale is not a locale directory.
        self.assertIsNone(locale_of("en.md", _LOCALES))

    def test_translation_key_strips_locale_segment(self) -> None:
        self.assertEqual(translation_key("en/guide/intro.md", _LOCALES), "guide/intro.md")
        self.assertEqual(translation_key("vi/guide/intro.md", _LOCALES), "guide/intro.md")

    def test_translation_key_keeps_non_locale_path(self) -> None:
        self.assertEqual(translation_key("about.md", _LOCALES), "about.md")

    def test_route_strips_default_prefix(self) -> None:
        self.assertEqual(
            route_url("/en/guide/intro/", "en/guide/intro.md", _LOCALES, "en"), "/guide/intro/"
        )

    def test_route_default_index_maps_to_root(self) -> None:
        self.assertEqual(route_url("/en/", "en/index.md", _LOCALES, "en"), "/")

    def test_route_keeps_non_default_prefix(self) -> None:
        self.assertEqual(
            route_url("/vi/guide/intro/", "vi/guide/intro.md", _LOCALES, "en"), "/vi/guide/intro/"
        )

    def test_route_suppresses_outside_locale_dir(self) -> None:
        self.assertEqual(route_url("/about/", "about.md", _LOCALES, "en"), "")


class I18nFactoryTest(unittest.TestCase):
    def test_default_must_be_in_locales(self) -> None:
        with self.assertRaises(ConfigError):
            i18n(default_locale="fr", locales=["en", "vi"])

    def test_cache_version_folds_in_config(self) -> None:
        a = i18n(default_locale="en", locales=["en", "vi"])
        b = i18n(default_locale="en", locales=["en", "vi", "fr"])
        c = i18n(default_locale="vi", locales=["en", "vi"])
        self.assertNotEqual(a.cache_version, b.cache_version)
        self.assertNotEqual(a.cache_version, c.cache_version)
        # Order-insensitive: same locale set yields the same key.
        self.assertEqual(
            a.cache_version, i18n(default_locale="en", locales=["vi", "en"]).cache_version
        )


class I18nBuildTest(unittest.TestCase):
    def test_routing_and_suppression(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            site = Path(tmp) / "site"
            _write_site(
                site,
                {
                    "en/guide/intro.md": _doc("Intro EN"),
                    "vi/guide/intro.md": _doc("Intro VI"),
                    "en/index.md": _doc("Home EN"),
                    "about.md": _doc("About"),  # outside any locale dir
                    "blog/post.md": _doc("Post"),  # non-locale folder
                },
            )
            build_site(site)
            outputs = _outputs(site / "dist")

        # Default locale served at the root; other locale keeps its prefix.
        self.assertIn("guide/intro/index.html", outputs)
        self.assertIn("vi/guide/intro/index.html", outputs)
        self.assertIn("index.html", outputs)  # en/index.md -> /
        # Content outside any locale directory produces no page.
        self.assertNotIn("about/index.html", outputs)
        self.assertNotIn("blog/post/index.html", outputs)

    def test_lang_exposed_to_template(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            site = Path(tmp) / "site"
            _write_site(
                site,
                {
                    "en/guide/intro.md": _doc("Intro EN"),
                    "vi/guide/intro.md": _doc("Intro VI"),
                },
            )
            build_site(site)
            en = (site / "dist" / "guide" / "intro" / "index.html").read_text(encoding="utf-8")
            vi = (site / "dist" / "vi" / "guide" / "intro" / "index.html").read_text(
                encoding="utf-8"
            )

        self.assertIn('data-lang="en"', en)
        self.assertIn('data-lang="vi"', vi)

    def test_translations_cross_link(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            site = Path(tmp) / "site"
            _write_site(
                site,
                {
                    "en/guide/intro.md": _doc("Intro EN"),
                    "vi/guide/intro.md": _doc("Intro VI"),
                    "en/only.md": _doc("Only EN"),  # no vi translation
                },
            )
            build_site(site)
            en = (site / "dist" / "guide" / "intro" / "index.html").read_text(encoding="utf-8")
            vi = (site / "dist" / "vi" / "guide" / "intro" / "index.html").read_text(
                encoding="utf-8"
            )
            only = (site / "dist" / "only" / "index.html").read_text(encoding="utf-8")

        # Each localised page links to its sibling translation, not to itself.
        self.assertIn('href="/vi/guide/intro/"', en)
        self.assertNotIn('href="/guide/intro/"', en)
        self.assertIn('href="/guide/intro/"', vi)
        # `languages` lists every configured locale on every page.
        self.assertIn('data-langs="en,vi"', en)
        # An untranslated page has an empty switcher (no fake links).
        self.assertIn('<nav class="i18n"></nav>', only)

    def test_context_defensive_without_plugin(self) -> None:
        # A site without the i18n plugin still renders: lang empty, no switcher.
        config_no_i18n = CONFIG_TEXT.replace(
            '        i18n(default_locale="en", locales=["en", "vi"]),\n', ""
        ).replace("    i18n,\n", "")
        with tempfile.TemporaryDirectory() as tmp:
            site = Path(tmp) / "site"
            _write_site(site, {"guide/intro.md": _doc("Intro")})
            (site / "pyssg.config.py").write_text(config_no_i18n, encoding="utf-8")
            build_site(site)
            html = (site / "dist" / "guide" / "intro" / "index.html").read_text(encoding="utf-8")

        self.assertIn('data-lang=""', html)
        self.assertIn('data-langs=""', html)
        self.assertIn('<nav class="i18n"></nav>', html)


def _files(root: Path) -> dict[str, str]:
    return {
        p.relative_to(root).as_posix(): p.read_text(encoding="utf-8")
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


class I18nIncrementalTest(unittest.TestCase):
    """Adding a translation must keep incremental output byte-identical to full.

    The new ``vi`` page changes the existing ``en`` page's switcher, so the
    render sweep must re-emit the ``en`` page; the result must match a full
    rebuild of the final tree exactly (the engine's core invariant).
    """

    def test_adding_translation_equals_full(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inc = Path(tmp) / "inc"
            _write_site(inc, {"en/guide/intro.md": _doc("Intro EN")})
            session = IncrementalSession(make_builder(inc, cache=None))
            asyncio.run(session.initial_build())

            content_root = (inc / "content").resolve()
            vi_path = inc / "content" / "vi" / "guide" / "intro.md"
            vi_path.parent.mkdir(parents=True, exist_ok=True)
            vi_path.write_text(_doc("Intro VI"), encoding="utf-8")
            session.apply(coalesce([FsEvent("add", str(content_root / "vi/guide/intro.md"))]))
            incremental = _files(inc / "dist")

            ref = Path(tmp) / "ref"
            _write_site(
                ref,
                {
                    "en/guide/intro.md": _doc("Intro EN"),
                    "vi/guide/intro.md": _doc("Intro VI"),
                },
            )
            build_site(ref)
            full = _files(ref / "dist")

        self.assertEqual(incremental, full)
        # Sanity: the en page really did gain the vi switcher link.
        self.assertIn('href="/vi/guide/intro/"', incremental["guide/intro/index.html"])


PRESET_CONFIG = """\
from __future__ import annotations

from pyssg.presets import docs
from pyssg.plugins import i18n

config = docs(
    site={"title": "Themed"},
    base_url="https://example.com",
    extra_plugins=[i18n(default_locale="en", locales=["en", "vi"])],
)
"""


class I18nThemeTest(unittest.TestCase):
    """The built-in docs theme renders <html lang>, hreflang alternates and a
    language switcher when i18n is enabled -- and is byte-identical otherwise
    (covered by the existing golden preset tests)."""

    def test_docs_theme_renders_i18n_markup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            site = Path(tmp) / "site"
            (site / "content" / "en").mkdir(parents=True)
            (site / "content" / "vi").mkdir(parents=True)
            (site / "pyssg.config.py").write_text(PRESET_CONFIG, encoding="utf-8")
            (site / "content" / "en" / "index.md").write_text(_doc("Home EN"), encoding="utf-8")
            (site / "content" / "vi" / "index.md").write_text(_doc("Home VI"), encoding="utf-8")
            build_site(site)
            en = (site / "dist" / "index.html").read_text(encoding="utf-8")
            vi = (site / "dist" / "vi" / "index.html").read_text(encoding="utf-8")

        # Localised <html lang> attribute.
        self.assertIn('<html lang="en">', en)
        self.assertIn('<html lang="vi">', vi)
        # hreflang alternate pointing at the sibling translation.
        self.assertIn('<link rel="alternate" hreflang="vi" href="/vi/">', en)
        self.assertIn('<link rel="alternate" hreflang="en" href="/">', vi)
        # Header language switcher links to the other locale.
        self.assertIn('href="/vi/"', en)
        self.assertIn(">VI</a>", en)

    def test_docs_theme_localises_ui_strings(self) -> None:
        # The shipped docs theme tables (en.toml/vi.toml) localise UI labels via
        # t(): the English page shows English nav, the Vietnamese page Vietnamese.
        with tempfile.TemporaryDirectory() as tmp:
            site = Path(tmp) / "site"
            (site / "content" / "en").mkdir(parents=True)
            (site / "content" / "vi").mkdir(parents=True)
            (site / "pyssg.config.py").write_text(PRESET_CONFIG, encoding="utf-8")
            (site / "content" / "en" / "index.md").write_text(_doc("Home EN"), encoding="utf-8")
            (site / "content" / "vi" / "index.md").write_text(_doc("Home VI"), encoding="utf-8")
            build_site(site)
            en = (site / "dist" / "index.html").read_text(encoding="utf-8")
            vi = (site / "dist" / "vi" / "index.html").read_text(encoding="utf-8")

        self.assertIn('<a href="/tags/">Tags</a>', en)
        self.assertIn('<a href="/categories/">Categories</a>', en)
        self.assertIn('<a href="/tags/">Thẻ</a>', vi)  # "The" with diacritics
        self.assertIn('<a href="/categories/">Chuyên mục</a>', vi)


# --- UI-string translation tables + the template `t()` function (engine) ---

# A page template that exercises the translator: a localised string, one with a
# variable, and a deliberately absent key (to assert the key-echo fallback).
T_TEMPLATE = (
    "<!doctype html><title>{{ page.title }}</title>"
    '<p data-lang="{{ lang }}">'
    '<span class="home">{{ t("nav.home") }}</span>'
    '<span class="posted">{{ t("nav.posted_on", date="2026-01-01") }}</span>'
    '<span class="miss">{{ t("nav.missing") }}</span>'
    "</p>\n"
)


def _write_strings_site(
    site: Path,
    content: dict[str, str],
    theme_tables: dict[str, str],
    site_tables: dict[str, str],
    template: str = T_TEMPLATE,
) -> None:
    """A site whose page template calls ``t()``, with theme + site string tables."""
    _write_site(site, content)
    (site / "layout" / "templates" / "page.html.j2").write_text(template, encoding="utf-8")
    for base, tables in ((site / "layout" / "i18n", theme_tables), (site / "i18n", site_tables)):
        for lang, text in tables.items():
            path = base / f"{lang}.toml"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")


class LoadStringsTest(unittest.TestCase):
    def test_flatten_merge_and_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            theme = Path(tmp) / "theme"
            site = Path(tmp) / "site"
            theme.mkdir()
            site.mkdir()
            (theme / "en.toml").write_text(
                '[nav]\nhome = "Home"\ntags = "Tags"\n', encoding="utf-8"
            )
            # The site table overrides one key and adds a top-level flat key; the
            # other theme key (nav.tags) survives the merge. The flat key precedes
            # the [nav] header so it stays top-level (TOML scopes by table).
            (site / "en.toml").write_text(
                'title = "Blog"\n\n[nav]\nhome = "Home (site)"\n', encoding="utf-8"
            )
            strings = load_strings(theme, site, frozenset({"en", "vi"}))

        self.assertEqual(
            strings["en"],
            {"nav.home": "Home (site)", "nav.tags": "Tags", "title": "Blog"},
        )
        # A locale with no table on disk is simply absent (not an empty dict).
        self.assertNotIn("vi", strings)

    def test_missing_dirs_yield_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            absent = Path(tmp) / "nope"
            self.assertEqual(load_strings(None, None, frozenset({"en"})), {})
            self.assertEqual(load_strings(absent, absent, frozenset({"en"})), {})


_TR_STRINGS = {
    "en": {"a": "Apple", "tmpl": "Posted on {date}"},
    "vi": {"a": "Tao"},  # no "tmpl" -> falls back to the default locale
}


class MakeTranslatorTest(unittest.TestCase):
    def test_fallback_lang_then_default_then_key(self) -> None:
        t = make_translator(_TR_STRINGS, "vi", "en")
        self.assertEqual(t("a"), "Tao")  # present in vi
        self.assertEqual(t("tmpl", date="x"), "Posted on x")  # falls back to en
        self.assertEqual(t("missing"), "missing")  # absent everywhere -> the key

    def test_var_interpolation_is_robust(self) -> None:
        t = make_translator(_TR_STRINGS, "en", "en")
        self.assertEqual(t("tmpl", date="2026-01-01"), "Posted on 2026-01-01")
        # A missing variable degrades to the raw template, never raises.
        self.assertEqual(t("tmpl"), "Posted on {date}")

    def test_empty_strings_echo_key(self) -> None:
        # No tables loaded (i18n plugin absent or no files): t echoes the key.
        t = make_translator({}, "", "")
        self.assertEqual(t("nav.home"), "nav.home")


_EN_TABLE = '[nav]\nhome = "Home"\nposted_on = "Posted on {date}"\n'
_VI_THEME_TABLE = '[nav]\nhome = "Trang chu"\n'  # no posted_on -> en fallback
_VI_SITE_TABLE = '[nav]\nhome = "Trang chu site"\n'  # overrides the theme


class TranslationBuildTest(unittest.TestCase):
    def test_t_localises_with_override_and_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            site = Path(tmp) / "site"
            _write_strings_site(
                site,
                {"en/index.md": _doc("Home EN"), "vi/index.md": _doc("Home VI")},
                theme_tables={"en": _EN_TABLE, "vi": _VI_THEME_TABLE},
                site_tables={"vi": _VI_SITE_TABLE},
            )
            build_site(site)
            en = (site / "dist" / "index.html").read_text(encoding="utf-8")
            vi = (site / "dist" / "vi" / "index.html").read_text(encoding="utf-8")

        # English: theme strings, variable interpolated, missing key echoes.
        self.assertIn('<span class="home">Home</span>', en)
        self.assertIn('<span class="posted">Posted on 2026-01-01</span>', en)
        self.assertIn('<span class="miss">nav.missing</span>', en)
        # Vietnamese: site override wins over the theme table...
        self.assertIn('<span class="home">Trang chu site</span>', vi)
        # ...and a key absent in vi falls back to the default locale (en).
        self.assertIn('<span class="posted">Posted on 2026-01-01</span>', vi)
        self.assertIn('<span class="miss">nav.missing</span>', vi)

    def test_t_resolves_without_i18n_plugin(self) -> None:
        # A single-language site (no i18n plugin, no locale dirs) still gets the
        # theme's strings: render loads i18n/*.toml independently of routing, and
        # the translator falls back to the base locale (en).
        config_no_i18n = CONFIG_TEXT.replace(
            '        i18n(default_locale="en", locales=["en", "vi"]),\n', ""
        ).replace("    i18n,\n", "")
        with tempfile.TemporaryDirectory() as tmp:
            site = Path(tmp) / "site"
            _write_strings_site(
                site,
                {"index.md": _doc("Home")},  # top-level content, no locale dir
                theme_tables={"en": _EN_TABLE},
                site_tables={},
            )
            (site / "pyssg.config.py").write_text(config_no_i18n, encoding="utf-8")
            build_site(site)
            html = (site / "dist" / "index.html").read_text(encoding="utf-8")

        self.assertIn('<span class="home">Home</span>', html)
        self.assertIn('<span class="posted">Posted on 2026-01-01</span>', html)
        self.assertIn('<span class="miss">nav.missing</span>', html)

    def test_build_twice_byte_identical(self) -> None:
        # Two independent full builds of the same tree are byte-for-byte equal:
        # string loading and the translator are pure, no clock or randomness.
        with tempfile.TemporaryDirectory() as tmp:
            content = {"en/index.md": _doc("Home EN"), "vi/index.md": _doc("Home VI")}
            tables = ({"en": _EN_TABLE, "vi": _VI_THEME_TABLE}, {"vi": _VI_SITE_TABLE})
            a = Path(tmp) / "a"
            b = Path(tmp) / "b"
            _write_strings_site(a, content, *tables)
            _write_strings_site(b, content, *tables)
            build_site(a)
            build_site(b)
            self.assertEqual(_files(a / "dist"), _files(b / "dist"))

    def test_render_cache_busts_on_table_edit(self) -> None:
        # Editing a translation table must re-render the affected page even when
        # the persistent render cache is reused: the strings digest is folded
        # into the render cache key.
        with tempfile.TemporaryDirectory() as tmp:
            site = Path(tmp) / "site"
            cache_dir = Path(tmp) / "cache"
            _write_strings_site(
                site,
                {"en/index.md": _doc("Home EN"), "vi/index.md": _doc("Home VI")},
                theme_tables={"en": _EN_TABLE, "vi": _VI_THEME_TABLE},
                site_tables={},
            )
            build_site(site, cache=FsCache(cache_dir))
            vi_before = (site / "dist" / "vi" / "index.html").read_text(encoding="utf-8")
            self.assertIn("Trang chu", vi_before)

            (site / "layout" / "i18n" / "vi.toml").write_text(
                '[nav]\nhome = "Da doi"\n', encoding="utf-8"
            )
            build_site(site, cache=FsCache(cache_dir))
            vi_after = (site / "dist" / "vi" / "index.html").read_text(encoding="utf-8")

        self.assertIn("Da doi", vi_after)
        self.assertNotIn("Trang chu", vi_after)


if __name__ == "__main__":
    unittest.main()
