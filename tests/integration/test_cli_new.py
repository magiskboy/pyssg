"""Tests for the ``pyssg new`` scaffolding group and its hidden aliases.

Covers the pure scaffolders (``scaffold_post`` / ``scaffold_plugin`` and
``slugify``) and the CLI surface via ``main``: ``new site|post|theme|plugin``,
plus the back-compat aliases ``init`` / ``eject-layout``. A generated plugin is
imported and wired into a real build to prove the template is correct and usable.
"""

from __future__ import annotations

import importlib.util
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any

from pyssg.cli import build_site, main
from pyssg.cli.scaffold import scaffold_plugin, scaffold_post, slugify
from pyssg.config import CONFIG_FILENAME
from pyssg.core.errors import ConfigError


class SlugifyTest(unittest.TestCase):
    def test_basic_and_deterministic(self) -> None:
        self.assertEqual(slugify("My First Post"), "my-first-post")
        self.assertEqual(slugify("My First Post"), slugify("My First Post"))

    def test_strips_accents_and_punctuation(self) -> None:
        self.assertEqual(slugify("Café & Crème!!"), "cafe-creme")
        self.assertEqual(slugify("  --Hello, World--  "), "hello-world")


class ScaffoldPostTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(self.enterContext(tempfile.TemporaryDirectory()))

    def test_writes_post_with_frontmatter(self) -> None:
        path = scaffold_post(self.tmp, title="Hello There", date="2024-01-02", tags=["a", "b"])
        self.assertEqual(path, self.tmp / "content" / "posts" / "hello-there.md")
        body = path.read_text(encoding="utf-8")
        self.assertIn('title: "Hello There"', body)
        self.assertIn('date: "2024-01-02"', body)
        self.assertIn("tags: [a, b]", body)
        self.assertIn("# Hello There", body)

    def test_omits_tags_line_when_empty(self) -> None:
        body = scaffold_post(self.tmp, title="T", date="2024-01-02").read_text(encoding="utf-8")
        self.assertNotIn("tags:", body)

    def test_is_deterministic(self) -> None:
        a = scaffold_post(self.tmp / "a", title="Same", date="2024-01-02", tags=["x"])
        b = scaffold_post(self.tmp / "b", title="Same", date="2024-01-02", tags=["x"])
        self.assertEqual(a.read_text(encoding="utf-8"), b.read_text(encoding="utf-8"))

    def test_explicit_slug_overrides_title(self) -> None:
        path = scaffold_post(self.tmp, title="Long Title", date="2024-01-02", slug="short")
        self.assertEqual(path.name, "short.md")

    def test_refuses_to_clobber(self) -> None:
        scaffold_post(self.tmp, title="Dup", date="2024-01-02")
        with self.assertRaises(ConfigError):
            scaffold_post(self.tmp, title="Dup", date="2024-01-02")
        # force overwrites.
        scaffold_post(self.tmp, title="Dup", date="2024-01-03", force=True)

    def test_untitled_slug_is_rejected(self) -> None:
        with self.assertRaises(ConfigError):
            scaffold_post(self.tmp, title="!!!", date="2024-01-02")


class ScaffoldPluginTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(self.enterContext(tempfile.TemporaryDirectory()))

    def test_rejects_non_identifier(self) -> None:
        with self.assertRaises(ConfigError):
            scaffold_plugin(self.tmp, name="not-valid")

    def test_writes_class_and_factory(self) -> None:
        path = scaffold_plugin(self.tmp, name="my_plugin")
        self.assertEqual(path, self.tmp / "plugins" / "my_plugin.py")
        body = path.read_text(encoding="utf-8")
        self.assertIn("class MyPluginPlugin:", body)
        self.assertIn("def my_plugin(", body)
        self.assertIn('name = "my_plugin"', body)

    def test_generated_plugin_imports_and_factory_works(self) -> None:
        path = scaffold_plugin(self.tmp, name="demo_plugin")
        module = self._import_module(path, "demo_plugin")
        plugin: Any = module.demo_plugin()
        self.assertEqual(plugin.name, "demo_plugin")
        self.assertTrue(hasattr(plugin, "cache_version"))
        self.assertTrue(callable(plugin.apply))
        # transform is an identity rewrite by default (pure, byte-identical).
        self.assertEqual(plugin.transform("<p>x</p>", None), "<p>x</p>")

    def test_generated_plugin_builds(self) -> None:
        """A generated plugin wired into config.plugins produces a working build."""
        site = self.tmp / "site"
        with redirect_stdout(io.StringIO()):
            main(["--site", str(site), "new", "site", "--preset", "docs"])
        scaffold_plugin(site, name="noop_plugin")
        (site / CONFIG_FILENAME).write_text(
            "from __future__ import annotations\n"
            "from pyssg.presets import docs\n"
            "from plugins.noop_plugin import noop_plugin\n"
            'config = docs(site={"title": "T"})\n'
            "config.plugins.append(noop_plugin())\n",
            encoding="utf-8",
        )
        sys.path.insert(0, str(site))
        try:
            build_site(site)
        finally:
            sys.path.remove(str(site))
            sys.modules.pop("plugins.noop_plugin", None)
            sys.modules.pop("plugins", None)
        self.assertTrue((site / "dist" / "index.html").is_file())

    @staticmethod
    def _import_module(path: Path, name: str) -> Any:
        spec = importlib.util.spec_from_file_location(name, path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


class NewCliTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(self.enterContext(tempfile.TemporaryDirectory()))

    def _run(self, argv: list[str]) -> int:
        with redirect_stdout(io.StringIO()):
            return main(argv)

    def test_new_site(self) -> None:
        site = self.tmp / "s"
        rc = self._run(["--site", str(site), "new", "site", "--preset", "blog"])
        self.assertEqual(rc, 0)
        self.assertTrue((site / CONFIG_FILENAME).is_file())

    def test_new_post(self) -> None:
        site = self.tmp / "s"
        self._run(["--site", str(site), "new", "site", "--preset", "blog"])
        rc = self._run(["--site", str(site), "new", "post", "--title", "Fresh Ideas"])
        self.assertEqual(rc, 0)
        self.assertTrue((site / "content" / "posts" / "fresh-ideas.md").is_file())

    def test_new_theme(self) -> None:
        site = self.tmp / "s"
        site.mkdir()
        rc = self._run(["--site", str(site), "new", "theme", "--name", "docs", "--to", "layouts/x"])
        self.assertEqual(rc, 0)
        self.assertTrue((site / "layouts" / "x" / "layout.toml").is_file())

    def test_new_plugin(self) -> None:
        site = self.tmp / "s"
        site.mkdir()
        rc = self._run(["--site", str(site), "new", "plugin", "my_plugin"])
        self.assertEqual(rc, 0)
        self.assertTrue((site / "plugins" / "my_plugin.py").is_file())

    def test_eject_layout_alias_matches_new_theme(self) -> None:
        site = self.tmp / "s"
        site.mkdir()
        argv = ["--site", str(site), "eject-layout", "--theme", "docs", "--to", "layouts/y"]
        rc = self._run(argv)
        self.assertEqual(rc, 0)
        self.assertTrue((site / "layouts" / "y" / "layout.toml").is_file())

    def test_unknown_preset_is_usage_error(self) -> None:
        with self.assertRaises(SystemExit), redirect_stdout(io.StringIO()):
            main(["--site", str(self.tmp / "s"), "new", "site", "--preset", "nope"])


class CliWrapperTest(unittest.TestCase):
    """The main() exit-code contract: usage errors raise, app outcomes return."""

    def test_unknown_command_raises_systemexit(self) -> None:
        with self.assertRaises(SystemExit), redirect_stdout(io.StringIO()):
            main(["frobnicate"])

    def test_bad_option_raises_systemexit(self) -> None:
        with self.assertRaises(SystemExit), redirect_stdout(io.StringIO()):
            main(["build", "--definitely-not-a-flag"])


if __name__ == "__main__":
    unittest.main()
