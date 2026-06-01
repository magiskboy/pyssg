"""Unit tests for the pure ignore-matching helper."""

from __future__ import annotations

import unittest

from pyssg.watch import is_ignored
from pyssg.watch.ignore import ALWAYS_IGNORE


class IgnoreMatchingTest(unittest.TestCase):
    def test_always_ignored_noise(self) -> None:
        for path in [
            "draft.swp",
            "content/post.md.swp",
            "notes.md~",
            ".DS_Store",
            "content/.DS_Store",
            ".obsidian/workspace.json",
            "vault/.obsidian/app.json",
            ".git/HEAD",
            "node_modules/pkg/index.js",
        ]:
            with self.subTest(path=path):
                self.assertTrue(is_ignored(path, []))

    def test_normal_files_not_ignored(self) -> None:
        for path in [
            "content/post.md",
            "layout/base.html",
            "pyssg.config.py",
            "vault/notes/idea.md",
        ]:
            with self.subTest(path=path):
                self.assertFalse(is_ignored(path, []))

    def test_config_glob_by_extension(self) -> None:
        self.assertTrue(is_ignored("build/scratch.tmp", ["*.tmp"]))
        self.assertFalse(is_ignored("build/scratch.md", ["*.tmp"]))

    def test_config_directory_glob(self) -> None:
        self.assertTrue(is_ignored("output/index.html", ["output/"]))
        self.assertTrue(is_ignored("a/output/nested/index.html", ["output/"]))
        self.assertFalse(is_ignored("content/output.md", ["output/"]))

    def test_config_path_glob_with_separator(self) -> None:
        self.assertTrue(is_ignored("content/private/secret.md", ["content/private/*"]))
        self.assertFalse(is_ignored("content/public/page.md", ["content/private/*"]))

    def test_windows_separators_normalized(self) -> None:
        self.assertTrue(is_ignored("vault\\.obsidian\\app.json", []))
        self.assertTrue(is_ignored("build\\scratch.tmp", ["*.tmp"]))

    def test_matching_is_case_sensitive(self) -> None:
        self.assertFalse(is_ignored("FILE.SWP", []))
        self.assertTrue(is_ignored("file.swp", []))

    def test_always_ignore_constant_shape(self) -> None:
        # Directory entries end with a slash; file/glob entries do not.
        self.assertIn(".obsidian/", ALWAYS_IGNORE)
        self.assertIn("*.swp", ALWAYS_IGNORE)
