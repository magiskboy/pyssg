"""Unit tests for the Robots plugin."""

from __future__ import annotations

import unittest
from pathlib import Path

from pyssg.build import Build
from pyssg.config import Config
from pyssg_plugins.robots import Robots


def run(plugin: Robots, options: dict[str, object] | None = None) -> str:
    build = Build(
        config=Config(src=Path("content"), out=Path("public"), options=options or {})
    )
    plugin._generate(build)
    return build.outputs[0].content


class OutputTest(unittest.TestCase):
    def test_emits_robots_output(self) -> None:
        build = Build(config=Config(src=Path("c"), out=Path("p")))
        Robots()._generate(build)
        self.assertEqual(build.outputs[0].path, Path("robots.txt"))

    def test_custom_path(self) -> None:
        build = Build(config=Config(src=Path("c"), out=Path("p")))
        Robots(path="bots.txt")._generate(build)
        self.assertEqual(build.outputs[0].path, Path("bots.txt"))

    def test_trailing_newline(self) -> None:
        self.assertTrue(run(Robots()).endswith("\n"))


class DefaultRulesTest(unittest.TestCase):
    def test_allows_everything_by_default(self) -> None:
        text = run(Robots())
        self.assertIn("User-agent: *", text)
        self.assertIn("Disallow:\n", text)

    def test_disallow_paths(self) -> None:
        text = run(Robots(disallow=["/private/", "/drafts/"]))
        self.assertIn("Disallow: /private/", text)
        self.assertIn("Disallow: /drafts/", text)
        self.assertNotIn("Disallow:\n", text)

    def test_allow_paths(self) -> None:
        text = run(Robots(allow=["/public/"], disallow=["/"]))
        self.assertIn("Allow: /public/", text)
        self.assertIn("Disallow: /", text)


class SitemapDirectiveTest(unittest.TestCase):
    def test_absolute_sitemap_with_base_url(self) -> None:
        text = run(Robots(), {"base_url": "https://x.com"})
        self.assertIn("Sitemap: https://x.com/sitemap.xml", text)

    def test_no_sitemap_without_base_url(self) -> None:
        self.assertNotIn("Sitemap:", run(Robots()))

    def test_sitemap_can_be_disabled(self) -> None:
        text = run(Robots(sitemap=False), {"base_url": "https://x.com"})
        self.assertNotIn("Sitemap:", text)

    def test_custom_sitemap_path(self) -> None:
        text = run(
            Robots(sitemap_path="sitemap_index.xml"), {"base_url": "https://x.com"}
        )
        self.assertIn("Sitemap: https://x.com/sitemap_index.xml", text)


class PrivateGuardTest(unittest.TestCase):
    def test_private_disallows_everything(self) -> None:
        text = run(Robots(), {"private": True, "base_url": "https://x.com"})
        self.assertIn("User-agent: *", text)
        self.assertIn("Disallow: /", text)

    def test_private_suppresses_sitemap(self) -> None:
        text = run(Robots(), {"private": True, "base_url": "https://x.com"})
        self.assertNotIn("Sitemap:", text)

    def test_private_overrides_custom_rules(self) -> None:
        text = run(Robots(allow=["/public/"]), {"private": True})
        self.assertNotIn("Allow:", text)


class GroupsTest(unittest.TestCase):
    def test_per_agent_groups(self) -> None:
        text = run(
            Robots(
                groups=[
                    {"user_agent": "Googlebot", "disallow": ["/no-google/"]},
                    {"user_agent": "*", "disallow": []},
                ]
            )
        )
        self.assertIn("User-agent: Googlebot", text)
        self.assertIn("Disallow: /no-google/", text)
        self.assertIn("User-agent: *", text)

    def test_multiple_user_agents_in_one_group(self) -> None:
        text = run(Robots(groups=[{"user_agent": ["A", "B"], "disallow": ["/x/"]}]))
        self.assertIn("User-agent: A", text)
        self.assertIn("User-agent: B", text)

    def test_group_without_disallow_gets_empty_rule(self) -> None:
        text = run(Robots(groups=[{"user_agent": "*"}]))
        self.assertIn("Disallow:\n", text)

    def test_groups_separated_by_blank_line(self) -> None:
        text = run(
            Robots(
                groups=[
                    {"user_agent": "A", "disallow": ["/a/"]},
                    {"user_agent": "B", "disallow": ["/b/"]},
                ],
            )
        )
        self.assertIn("Disallow: /a/\n\nUser-agent: B", text)


if __name__ == "__main__":
    unittest.main()
