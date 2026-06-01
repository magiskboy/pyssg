"""Unit tests for site configuration loading."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pyssg.config import Config, load_config
from pyssg.core.errors import ConfigError


def _write_config(site_dir: Path, body: str) -> None:
    (site_dir / "pyssg.config.py").write_text(body, encoding="utf-8")


class ConfigTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_path = Path(self.enterContext(tempfile.TemporaryDirectory()))

    def test_config_defaults(self) -> None:
        config = Config()
        self.assertEqual(config.content_dir, "content")
        self.assertEqual(config.output_dir, "dist")
        self.assertIsNone(config.layout)
        self.assertEqual(config.base_url, "")
        self.assertEqual(config.plugins, [])
        self.assertEqual(config.site, {})

    def test_config_independent_mutable_defaults(self) -> None:
        """Each Config gets its own plugins list / site dict (no shared state)."""
        a = Config()
        b = Config()
        a.plugins.append(object())  # type: ignore[arg-type]
        a.site["title"] = "A"
        self.assertEqual(b.plugins, [])
        self.assertEqual(b.site, {})

    def test_load_config_returns_exported_config(self) -> None:
        _write_config(
            self.tmp_path,
            "from pyssg.config import Config\n"
            'config = Config(content_dir="c", base_url="https://x")\n',
        )
        config = load_config(self.tmp_path)
        self.assertIsInstance(config, Config)
        self.assertEqual(config.content_dir, "c")
        self.assertEqual(config.base_url, "https://x")
        # Untouched fields keep their declared defaults.
        self.assertEqual(config.output_dir, "dist")
        self.assertIsNone(config.layout)

    def test_load_config_missing_file(self) -> None:
        with self.assertRaisesRegex(ConfigError, r"no pyssg\.config\.py"):
            load_config(self.tmp_path)

    def test_load_config_without_config_variable(self) -> None:
        _write_config(self.tmp_path, "x = 1\n")
        with self.assertRaisesRegex(ConfigError, "must define a module-level 'config'"):
            load_config(self.tmp_path)

    def test_load_config_wrong_type(self) -> None:
        _write_config(self.tmp_path, "config = 42\n")
        with self.assertRaisesRegex(ConfigError, "must be a Config instance"):
            load_config(self.tmp_path)

    def test_load_config_is_deterministic(self) -> None:
        """Repeated loads of the same file yield equal configs (purity)."""
        _write_config(
            self.tmp_path,
            "from pyssg.config import Config\n"
            'config = Config(content_dir="docs", output_dir="out")\n',
        )
        first = load_config(self.tmp_path)
        second = load_config(self.tmp_path)
        self.assertEqual(first, second)
