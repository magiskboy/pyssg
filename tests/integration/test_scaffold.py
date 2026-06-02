"""Integration tests for ``pyssg init`` / ``pyssg eject-layout`` scaffolding."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pyssg.cli import build_site, main
from pyssg.cli.scaffold import eject_layout, init_site
from pyssg.config import CONFIG_FILENAME, load_config
from pyssg.core.errors import ConfigError, LayoutError


class InitSiteTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(self.enterContext(tempfile.TemporaryDirectory()))

    def test_init_docs_then_build(self) -> None:
        site = self.tmp / "docs_site"
        created = init_site(site, preset="docs")
        self.assertIn(site / CONFIG_FILENAME, created)
        # The scaffold loads as a valid config and builds to real pages.
        load_config(site)
        build_site(site)
        self.assertTrue((site / "dist" / "index.html").is_file())
        self.assertTrue((site / "dist" / "guide" / "getting-started" / "index.html").is_file())

    def test_init_blog_then_build(self) -> None:
        site = self.tmp / "blog_site"
        init_site(site, preset="blog")
        build_site(site)
        # Home is the paginated post list; the sample post is rendered.
        self.assertTrue((site / "dist" / "index.html").is_file())
        self.assertTrue((site / "dist" / "posts" / "hello-world" / "index.html").is_file())

    def test_init_obsidian_then_build(self) -> None:
        site = self.tmp / "vault_site"
        init_site(site, preset="obsidian")
        load_config(site)
        build_site(site)
        # Both scaffold notes are marked publish: true, so both render; the
        # wikilink from the home page resolves to the getting-started note.
        self.assertTrue((site / "dist" / "index.html").is_file())
        self.assertTrue((site / "dist" / "Getting Started" / "index.html").is_file())
        home = (site / "dist" / "index.html").read_text(encoding="utf-8")
        self.assertIn('href="/Getting Started/"', home)

    def test_init_is_deterministic(self) -> None:
        a = self.tmp / "a"
        b = self.tmp / "b"
        init_site(a, preset="blog")
        init_site(b, preset="blog")
        self.assertEqual(
            (a / CONFIG_FILENAME).read_text(encoding="utf-8"),
            (b / CONFIG_FILENAME).read_text(encoding="utf-8"),
        )

    def test_unknown_preset_raises(self) -> None:
        with self.assertRaises(ConfigError):
            init_site(self.tmp / "x", preset="nope")

    def test_refuses_to_clobber_existing_config(self) -> None:
        site = self.tmp / "site"
        init_site(site, preset="docs")
        with self.assertRaises(ConfigError):
            init_site(site, preset="blog")

    def test_force_overwrites_config(self) -> None:
        site = self.tmp / "site"
        init_site(site, preset="docs")
        init_site(site, preset="blog", force=True)
        text = (site / CONFIG_FILENAME).read_text(encoding="utf-8")
        self.assertIn("from pyssg.presets import blog", text)

    def test_cli_init_entrypoint(self) -> None:
        site = self.tmp / "cli_site"
        rc = main(["--site", str(site), "init", "--preset", "docs"])
        self.assertEqual(rc, 0)
        self.assertTrue((site / CONFIG_FILENAME).is_file())


class EjectLayoutTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(self.enterContext(tempfile.TemporaryDirectory()))

    def test_eject_copies_theme(self) -> None:
        site = self.tmp / "site"
        site.mkdir()
        dest = eject_layout(site, theme="docs", dest="layouts/docs")
        self.assertTrue((dest / "layout.toml").is_file())
        self.assertTrue((dest / "templates" / "page.html.j2").is_file())

    def test_ejected_layout_is_usable(self) -> None:
        site = self.tmp / "site"
        init_site(site, preset="docs")
        eject_layout(site, theme="docs", dest="layouts/docs")
        # Repoint the config at the ejected copy and rebuild.
        (site / CONFIG_FILENAME).write_text(
            "from __future__ import annotations\n"
            "from pyssg.presets import docs\n"
            'config = docs(site={"title": "T"}, layout="layouts/docs")\n',
            encoding="utf-8",
        )
        build_site(site)
        self.assertTrue((site / "dist" / "index.html").is_file())

    def test_unknown_theme_raises(self) -> None:
        with self.assertRaises(LayoutError):
            eject_layout(self.tmp, theme="nope", dest="x")

    def test_refuses_existing_destination(self) -> None:
        site = self.tmp / "site"
        site.mkdir()
        eject_layout(site, theme="docs", dest="layouts/docs")
        with self.assertRaises(ConfigError):
            eject_layout(site, theme="docs", dest="layouts/docs")


if __name__ == "__main__":
    unittest.main()
