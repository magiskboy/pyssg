"""Unit tests for the ``publish_gate`` contrib plugin."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pyssg.contrib.publish_gate import publish_gate, should_publish


class ShouldPublishTest(unittest.TestCase):
    def test_allowlist_requires_truthy_flag(self) -> None:
        self.assertTrue(should_publish({"publish": True}, key="publish", publish_required=True))
        self.assertFalse(should_publish({"publish": False}, key="publish", publish_required=True))
        self.assertFalse(should_publish({}, key="publish", publish_required=True))

    def test_denylist_publishes_unless_explicit_false(self) -> None:
        self.assertTrue(should_publish({}, key="publish", publish_required=False))
        self.assertTrue(should_publish({"publish": True}, key="publish", publish_required=False))
        self.assertFalse(should_publish({"publish": False}, key="publish", publish_required=False))

    def test_custom_key(self) -> None:
        self.assertTrue(should_publish({"share": True}, key="share", publish_required=True))
        self.assertFalse(should_publish({"publish": True}, key="share", publish_required=True))


class PublishGateFactoryTest(unittest.TestCase):
    def test_named_plugin(self) -> None:
        plugin = publish_gate()
        self.assertEqual(plugin.name, "publish_gate")
        self.assertTrue(plugin.cache_version)

    def test_mode_changes_cache_version(self) -> None:
        allow = publish_gate(publish_required=True)
        deny = publish_gate(publish_required=False)
        self.assertNotEqual(allow.cache_version, deny.cache_version)


_CONTENT = {
    "index.md": "---\ntitle: Home\npublish: true\n---\nHome.\n",
    "public.md": "---\ntitle: Public\npublish: true\n---\nPublic.\n",
    "private.md": "---\ntitle: Private\n---\nPrivate note.\n",
    "explicit-off.md": "---\ntitle: Off\npublish: false\n---\nOff.\n",
}

_CONFIG = """\
from __future__ import annotations

from pyssg import Config
from pyssg.plugins import directory_loader, frontmatter, markdown, permalink, render
from pyssg.contrib.publish_gate import publish_gate

config = Config(
    plugins=[
        directory_loader(),
        frontmatter(),
        markdown(),
        publish_gate({gate_args}),
        permalink(),
        render(),
    ],
)
"""


class PublishGateBuildTest(unittest.TestCase):
    """End-to-end: only selected documents emit pages."""

    def setUp(self) -> None:
        self.tmp_path = Path(self.enterContext(tempfile.TemporaryDirectory()))

    def _build(self, gate_args: str, name: str) -> set[str]:
        from pyssg.cli import build_site

        site = self.tmp_path / name
        for rel, body in _CONTENT.items():
            path = site / "content" / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(body, encoding="utf-8")
        (site / "pyssg.config.py").write_text(_CONFIG.format(gate_args=gate_args), encoding="utf-8")
        build_site(site)
        dist = site / "dist"
        return {p.relative_to(dist).as_posix() for p in dist.rglob("*.html") if p.is_file()}

    def test_allowlist_emits_only_published(self) -> None:
        pages = self._build("", "allow")
        self.assertIn("index.html", pages)
        self.assertIn("public/index.html", pages)
        self.assertNotIn("private/index.html", pages)
        self.assertNotIn("explicit-off/index.html", pages)

    def test_denylist_emits_all_but_explicit_off(self) -> None:
        pages = self._build("publish_required=False", "deny")
        self.assertIn("index.html", pages)
        self.assertIn("public/index.html", pages)
        self.assertIn("private/index.html", pages)
        self.assertNotIn("explicit-off/index.html", pages)


if __name__ == "__main__":
    unittest.main()
