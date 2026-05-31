"""Validate the deploy recipe manifests.

These manifests are the contract a future deploy plugin / `pyssg deploy init`
will read, so they must stay well-formed: every target declares the required
fields and every referenced project file exists.
"""

from __future__ import annotations

import tomllib
import unittest
from pathlib import Path

RECIPES_DIR = Path(__file__).resolve().parents[1] / "recipes" / "deploy"
EXPECTED_TARGETS = {"github-pages", "netlify", "cloudflare-pages"}


def manifest_dirs() -> list[Path]:
    return sorted(p.parent for p in RECIPES_DIR.glob("*/deploy.toml"))


class DeployRecipeTest(unittest.TestCase):
    def test_expected_targets_are_present(self) -> None:
        names = {d.name for d in manifest_dirs()}
        self.assertEqual(names, EXPECTED_TARGETS)

    def test_manifests_are_well_formed(self) -> None:
        for folder in manifest_dirs():
            with self.subTest(target=folder.name):
                data = tomllib.loads(
                    (folder / "deploy.toml").read_text(encoding="utf-8")
                )
                target = data["target"]
                # Stable id matches the folder; output dir matches Config.out.
                self.assertEqual(target["name"], folder.name)
                self.assertEqual(target["publish_dir"], "public")
                for key in ("title", "homepage", "root_served_only"):
                    self.assertIn(key, target)

                for entry in data.get("project_files", []):
                    self.assertIn("path", entry)
                    source = folder / entry["source"]
                    self.assertTrue(source.is_file(), f"missing source file: {source}")

                for entry in data.get("output_files", []):
                    self.assertIn("path", entry)
                    self.assertIsInstance(entry["content"], str)


if __name__ == "__main__":
    unittest.main()
