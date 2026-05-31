"""Unit tests for the BrokenLinks plugin."""

from __future__ import annotations

import contextlib
import io
import unittest
from pathlib import Path

from pyssg.build import Build
from pyssg.config import Config
from pyssg.errors import BuildError
from pyssg_plugins.broken_links import BrokenLinks
from pyssg_plugins.link_resolver import BROKEN_LINKS, BrokenLink


def make_build(broken: list[BrokenLink] | None = None) -> Build:
    build = Build(config=Config(src=Path("content"), out=Path("public")))
    if broken is not None:
        build.meta[BROKEN_LINKS] = broken
    return build


def report(build: Build, *, strict: bool = False) -> str:
    """Run the plugin's report tap, capturing anything written to stderr."""

    stderr = io.StringIO()
    with contextlib.redirect_stderr(stderr):
        BrokenLinks(strict=strict)._report(build)
    return stderr.getvalue()


class WarnTest(unittest.TestCase):
    def test_no_meta_is_noop(self) -> None:
        self.assertEqual(report(make_build()), "")

    def test_empty_list_is_noop(self) -> None:
        self.assertEqual(report(make_build([])), "")

    def test_each_broken_link_is_warned(self) -> None:
        build = make_build([BrokenLink("a.md", "x.md"), BrokenLink("b.md", "y.md")])
        out = report(build)
        self.assertIn("broken internal link in a.md: x.md", out)
        self.assertIn("broken internal link in b.md: y.md", out)

    def test_duplicates_are_deduped(self) -> None:
        build = make_build([BrokenLink("a.md", "x.md"), BrokenLink("a.md", "x.md")])
        out = report(build, strict=False)
        self.assertEqual(out.count("broken internal link in a.md: x.md"), 1)


class StrictTest(unittest.TestCase):
    def test_strict_raises_on_broken_links(self) -> None:
        build = make_build([BrokenLink("a.md", "x.md")])
        with self.assertRaises(BuildError) as ctx:
            report(build, strict=True)
        self.assertIn("1 broken internal link", str(ctx.exception))
        self.assertIn("a.md -> x.md", str(ctx.exception))

    def test_strict_counts_unique_links(self) -> None:
        build = make_build([BrokenLink("a.md", "x.md"), BrokenLink("a.md", "x.md")])
        with self.assertRaises(BuildError) as ctx:
            report(build, strict=True)
        self.assertIn("1 broken internal link", str(ctx.exception))

    def test_strict_is_noop_when_clean(self) -> None:
        # No broken links: a strict build must not raise.
        self.assertEqual(report(make_build([]), strict=True), "")


class HookTest(unittest.TestCase):
    def test_taps_optimize(self) -> None:
        from pyssg.builder import Builder

        builder = Builder(Config(src=Path("c"), out=Path("o"), plugins=[BrokenLinks()]))
        self.assertTrue(builder.hooks.optimize.has_taps)


if __name__ == "__main__":
    unittest.main()
