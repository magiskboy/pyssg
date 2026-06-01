"""M6 critical invariant: incremental == full with collections + pagination.

Drives the ``blog`` preset (collections plugin, date-sorted paginated ``posts``)
through add/delete/modify/move sequences. Each operation changes the post set,
which can change the number of paginated index pages -- exercising the
collection page-set diff. For every sequence the incremental output must stay
byte-identical to a full rebuild of the final content.
"""

from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path

from pyssg.cli import build_site, make_builder
from pyssg.core.phases import IncrementalSession
from pyssg.watch import FsEvent, coalesce

CONFIG_TEXT = """\
from __future__ import annotations

from pyssg.presets import blog

config = blog(
    site={"title": "Inc Blog"},
    base_url="https://example.com",
    posts_per_page=2,
)
"""


def _post(title: str, date: str, body: str, tags: list[str] | None = None) -> str:
    fm = [f"title: {title}", f'date: "{date}"']
    if tags is not None:
        fm.append("tags: [" + ", ".join(tags) + "]")
    return "---\n" + "\n".join(fm) + "\n---\n" + body + "\n"


def _write_site(site: Path, content: dict[str, str]) -> None:
    site.mkdir(parents=True, exist_ok=True)
    (site / "pyssg.config.py").write_text(CONFIG_TEXT, encoding="utf-8")
    for rel, text in content.items():
        path = site / "content" / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


def _files(root: Path) -> dict[str, str]:
    return {
        p.relative_to(root).as_posix(): p.read_text(encoding="utf-8")
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


def _apply_op(
    site: Path, content_root: Path, state: dict[str, str], op: tuple[str, ...]
) -> list[FsEvent]:
    kind = op[0]
    if kind in {"modify", "add"}:
        rel, text = op[1], op[2]
        path = site / "content" / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        existed = rel in state
        path.write_text(text, encoding="utf-8")
        state[rel] = text
        return [FsEvent("modify" if existed else "add", str(content_root / rel))]
    if kind == "delete":
        (site / "content" / op[1]).unlink()
        state.pop(op[1], None)
        return [FsEvent("delete", str(content_root / op[1]))]
    if kind == "move":
        src, dst = op[1], op[2]
        (site / "content" / dst).parent.mkdir(parents=True, exist_ok=True)
        (site / "content" / src).rename(site / "content" / dst)
        state[dst] = state.pop(src)
        return [FsEvent("move", str(content_root / src), str(content_root / dst))]
    raise AssertionError(kind)


def _assert_eq(tmp: Path, initial: dict[str, str], ops: list[tuple[str, ...]]) -> None:
    inc = tmp / "inc"
    _write_site(inc, initial)
    session = IncrementalSession(make_builder(inc))
    asyncio.run(session.initial_build())
    content_root = (inc / "content").resolve()
    state = dict(initial)
    for op in ops:
        session.apply(coalesce(_apply_op(inc, content_root, state, op)))
    inc_out = _files(inc / "dist")

    ref = tmp / "ref"
    _write_site(ref, state)
    build_site(ref)
    assert inc_out == _files(ref / "dist")


INITIAL = {
    "posts/a.md": _post("Alpha", "2024-01-10", "# Alpha\n\nFirst.", ["intro"]),
    "posts/b.md": _post("Beta", "2024-02-20", "# Beta\n\nSecond.", ["intro", "news"]),
    "posts/c.md": _post("Gamma", "2024-03-30", "# Gamma\n\nThird.", ["news"]),
    "about.md": "---\ntitle: About\n---\n# About\n\nStandalone.\n",
}


class CollectionsIncrementalTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_path = Path(self.enterContext(tempfile.TemporaryDirectory()))

    def test_edit_post_body(self) -> None:
        op = ("modify", "posts/b.md", _post("Beta", "2024-02-20", "# Beta\n\nv2.", ["news"]))
        _assert_eq(self.tmp_path, INITIAL, [op])

    def test_add_post_grows_pagination(self) -> None:
        # 3 -> 4 posts: page 2 gains a member; index pages must stay consistent.
        op = ("add", "posts/d.md", _post("Delta", "2024-04-10", "# Delta\n\nNew.", ["intro"]))
        _assert_eq(self.tmp_path, INITIAL, [op])

    def test_delete_post_shrinks_pagination(self) -> None:
        # 3 -> 2 posts: /page/2/ must disappear (collection page-set diff).
        _assert_eq(self.tmp_path, INITIAL, [("delete", "posts/a.md")])

    def test_change_date_reorders(self) -> None:
        # Make the oldest the newest: ordering across pages must flip.
        op = ("modify", "posts/a.md", _post("Alpha", "2024-12-31", "# Alpha\n\nFirst.", ["intro"]))
        _assert_eq(self.tmp_path, INITIAL, [op])

    def test_move_post_keeps_it_a_post(self) -> None:
        _assert_eq(self.tmp_path, INITIAL, [("move", "posts/c.md", "posts/gamma.md")])

    def test_move_post_out_of_section_drops_it(self) -> None:
        # Moving out of posts/ removes it from the collection entirely.
        _assert_eq(self.tmp_path, INITIAL, [("move", "posts/c.md", "archive/c.md")])

    def test_mixed_sequence(self) -> None:
        ops: list[tuple[str, ...]] = [
            ("add", "posts/d.md", _post("Delta", "2024-04-10", "# Delta\n\nx.", ["news"])),
            ("delete", "posts/a.md"),
            ("modify", "posts/b.md", _post("Beta", "2024-05-05", "# Beta\n\nbumped.", ["intro"])),
            ("move", "posts/c.md", "posts/gamma.md"),
            ("add", "posts/e.md", _post("Epsilon", "2024-06-06", "# Eps\n\ny.", [])),
        ]
        _assert_eq(self.tmp_path, INITIAL, ops)
