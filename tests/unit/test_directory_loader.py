"""Unit tests for the ``directory_loader`` include/exclude filters."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pyssg.cli import build_site
from pyssg.plugins.directory_loader import _matches_any, directory_loader

_CONTENT = {
    "index.md": "---\ntitle: Home\n---\nHome.\n",
    "about.md": "---\ntitle: About\n---\nAbout.\n",
    "guide/intro.md": "---\ntitle: Intro\n---\nIntro.\n",
    "drafts/secret.md": "---\ntitle: Secret\n---\nSecret.\n",
    "templates/daily.md": "---\ntitle: Daily\n---\nDaily.\n",
    ".obsidian/app.json": "{}\n",
}

_CONFIG = """\
from __future__ import annotations

from pyssg import Config
from pyssg.plugins import directory_loader, frontmatter, markdown, permalink, render

config = Config(
    plugins=[
        directory_loader({filter_args}),
        frontmatter(),
        markdown(),
        permalink(),
        render(),
    ],
)
"""


def _matches(rel: str, *patterns: str) -> bool:
    return _matches_any(Path(rel), tuple(patterns))


class MatchesAnyTest(unittest.TestCase):
    def test_directory_name_matches_exactly(self) -> None:
        self.assertTrue(_matches(".obsidian", ".obsidian"))
        self.assertFalse(_matches(".obsidian/app.json", ".obsidian"))

    def test_double_star_spans_segments(self) -> None:
        self.assertTrue(_matches("a/b/c.tmp", "**/*.tmp"))
        self.assertTrue(_matches("c.tmp", "**/*.tmp"))

    def test_no_patterns_never_matches(self) -> None:
        self.assertFalse(_matches("anything.md"))


class DirectoryLoaderFilterBuildTest(unittest.TestCase):
    """End-to-end: filters change which pages are emitted to ``dist``."""

    def setUp(self) -> None:
        self.tmp_path = Path(self.enterContext(tempfile.TemporaryDirectory()))

    def _build(self, name: str, filter_args: str) -> set[str]:
        # ``name`` is a filesystem-safe directory; ``filter_args`` may contain
        # glob metacharacters that are illegal in paths (notably on Windows).
        site = self.tmp_path / name
        for rel, body in _CONTENT.items():
            path = site / "content" / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(body, encoding="utf-8")
        (site / "pyssg.config.py").write_text(
            _CONFIG.format(filter_args=filter_args), encoding="utf-8"
        )
        build_site(site)
        dist = site / "dist"
        return {p.relative_to(dist).as_posix() for p in dist.rglob("*.html") if p.is_file()}

    def test_no_filter_loads_every_markdown_file(self) -> None:
        pages = self._build("no-filter", "")
        self.assertIn("index.html", pages)
        self.assertIn("about/index.html", pages)
        self.assertIn("guide/intro/index.html", pages)
        self.assertIn("drafts/secret/index.html", pages)
        self.assertIn("templates/daily/index.html", pages)

    def test_exclude_prunes_directory_subtrees(self) -> None:
        pages = self._build("exclude", 'exclude=["drafts", "templates"]')
        self.assertIn("index.html", pages)
        self.assertIn("guide/intro/index.html", pages)
        self.assertNotIn("drafts/secret/index.html", pages)
        self.assertNotIn("templates/daily/index.html", pages)

    def test_include_restricts_to_allowlisted_files(self) -> None:
        pages = self._build("include", 'include=["index.md", "guide/**"]')
        self.assertIn("index.html", pages)
        self.assertIn("guide/intro/index.html", pages)
        self.assertNotIn("about/index.html", pages)
        self.assertNotIn("drafts/secret/index.html", pages)

    def test_exclude_wins_over_include(self) -> None:
        pages = self._build("exclude-wins", 'include=["**/*.md"], exclude=["drafts"]')
        self.assertIn("about/index.html", pages)
        self.assertNotIn("drafts/secret/index.html", pages)


class DirectoryLoaderFactoryTest(unittest.TestCase):
    def test_cache_version_reflects_filters(self) -> None:
        plain = directory_loader()
        filtered = directory_loader(exclude=["drafts"])
        self.assertNotEqual(plain.cache_version, filtered.cache_version)

    def test_cache_version_is_order_independent(self) -> None:
        a = directory_loader(exclude=["a", "b"])
        b = directory_loader(exclude=["b", "a"])
        self.assertEqual(a.cache_version, b.cache_version)


if __name__ == "__main__":
    unittest.main()
