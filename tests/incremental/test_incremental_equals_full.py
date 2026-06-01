"""M5 critical invariant: incremental == full rebuild, byte-identical.

For any sequence of FS operations (modify / add / delete / move), driving the
incremental engine produces exactly the same ``dist`` as building the final
content from scratch. This is the most important test in the project; it is
written as a property test over generated operation sequences plus targeted
cases for each operation kind and for early-cutoff.
"""

from __future__ import annotations

import asyncio
import random
import tempfile
import unittest
from pathlib import Path

from pyssg.cli import build_site, make_builder
from pyssg.core.phases import IncrementalSession
from pyssg.watch import FsEvent, coalesce

CONFIG_TEXT = """\
from __future__ import annotations

from pyssg import Config
from pyssg.plugins import (
    directory_loader,
    frontmatter,
    markdown,
    permalink,
    render,
)

config = Config(
    content_dir="content",
    output_dir="dist",
    layout="layouts/page",
    base_url="https://example.com",
    site={"title": "Prop"},
    plugins=[
        directory_loader(),
        frontmatter(),
        markdown(),
        permalink(),
        render(),
    ],
)
"""

TEMPLATE_TEXT = """\
<!doctype html>
<title>{{ page.title }} | {{ site.title }}</title>
<main>
{{ content_html }}</main>
"""


def _doc(title: str, body: str) -> str:
    return f"---\ntitle: {title}\n---\n{body}\n"


def _write_site(site: Path, content: dict[str, str]) -> None:
    site.mkdir(parents=True, exist_ok=True)
    (site / "pyssg.config.py").write_text(CONFIG_TEXT, encoding="utf-8")
    layout = site / "layouts" / "page"
    (layout / "templates").mkdir(parents=True, exist_ok=True)
    (layout / "layout.toml").write_text(
        'name = "page"\nversion = "0.1.0"\ndefault_template = "page.html.j2"\n',
        encoding="utf-8",
    )
    (layout / "templates" / "page.html.j2").write_text(TEMPLATE_TEXT, encoding="utf-8")
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
    """Mutate the content tree on disk and return the matching FS events."""
    kind = op[0]
    if kind in {"modify", "add"}:
        rel, text = op[1], op[2]
        path = site / "content" / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        existed = rel in state
        path.write_text(text, encoding="utf-8")
        state[rel] = text
        if existed:
            return [FsEvent("modify", str(content_root / rel))]
        return [FsEvent("add", str(content_root / rel))]
    if kind == "delete":
        rel = op[1]
        (site / "content" / rel).unlink()
        state.pop(rel, None)
        return [FsEvent("delete", str(content_root / rel))]
    if kind == "move":
        src, dst = op[1], op[2]
        src_path = site / "content" / src
        dst_path = site / "content" / dst
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        src_path.rename(dst_path)
        state[dst] = state.pop(src)
        return [FsEvent("move", str(content_root / src), str(content_root / dst))]
    raise AssertionError(f"unknown op {kind}")


def _run_incremental(
    tmp: Path, initial: dict[str, str], ops: list[tuple[str, ...]]
) -> tuple[dict[str, str], dict[str, str]]:
    site = tmp / "inc"
    _write_site(site, initial)
    builder = make_builder(site)
    session = IncrementalSession(builder)
    asyncio.run(session.initial_build())
    content_root = (site / "content").resolve()
    state = dict(initial)
    for op in ops:
        events = _apply_op(site, content_root, state, op)
        session.apply(coalesce(events))
    return _files(site / "dist"), state


def _full_snapshot(tmp: Path, content: dict[str, str]) -> dict[str, str]:
    site = tmp / "ref"
    _write_site(site, content)
    build_site(site)
    return _files(site / "dist")


def _assert_incremental_equals_full(
    tmp: Path, initial: dict[str, str], ops: list[tuple[str, ...]]
) -> None:
    inc_out, final_state = _run_incremental(tmp, initial, ops)
    ref_out = _full_snapshot(tmp, final_state)
    assert inc_out == ref_out


INITIAL = {
    "index.md": _doc("Home", "Welcome home."),
    "about.md": _doc("About", "About us."),
    "guide/intro.md": _doc("Intro", "The intro."),
}


def _gen_ops(seed: int, initial: dict[str, str], steps: int) -> list[tuple[str, ...]]:
    rng = random.Random(seed)
    files = set(initial)
    counter = 0
    ops: list[tuple[str, ...]] = []
    for _ in range(steps):
        choices = ["add"]
        if files:
            choices += ["modify", "modify_title", "delete", "move"]
        choice = rng.choice(choices)
        if choice == "add":
            counter += 1
            rel = f"gen/n{counter}.md"
            files.add(rel)
            ops.append(("add", rel, _doc(f"Gen {counter}", f"Body {counter}.")))
        elif choice == "modify":
            rel = rng.choice(sorted(files))
            ops.append(("modify", rel, _doc("Same", f"Body {rng.randint(0, 999)}.")))
        elif choice == "modify_title":
            rel = rng.choice(sorted(files))
            ops.append(("modify", rel, _doc(f"Title {rng.randint(0, 99)}", "Body.")))
        elif choice == "delete":
            rel = rng.choice(sorted(files))
            files.discard(rel)
            ops.append(("delete", rel))
        else:  # move
            rel = rng.choice(sorted(files))
            files.discard(rel)
            counter += 1
            dst = f"moved/m{counter}.md"
            files.add(dst)
            ops.append(("move", rel, dst))
    return ops


class IncrementalEqualsFullTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_path = Path(self.enterContext(tempfile.TemporaryDirectory()))

    def test_modify_body(self) -> None:
        _assert_incremental_equals_full(
            self.tmp_path,
            INITIAL,
            [("modify", "about.md", _doc("About", "Changed body."))],
        )

    def test_modify_title(self) -> None:
        _assert_incremental_equals_full(
            self.tmp_path,
            INITIAL,
            [("modify", "index.md", _doc("New Home", "Welcome home."))],
        )

    def test_add_file(self) -> None:
        _assert_incremental_equals_full(
            self.tmp_path,
            INITIAL,
            [("add", "guide/extra.md", _doc("Extra", "Extra page."))],
        )

    def test_delete_file(self) -> None:
        _assert_incremental_equals_full(self.tmp_path, INITIAL, [("delete", "about.md")])

    def test_move_file(self) -> None:
        _assert_incremental_equals_full(
            self.tmp_path,
            INITIAL,
            [("move", "guide/intro.md", "guide/getting-started.md")],
        )

    def test_noop_modify_is_safe(self) -> None:
        # Rewriting identical bytes must not corrupt anything (raw-hash short-circuit).
        _assert_incremental_equals_full(
            self.tmp_path, INITIAL, [("modify", "index.md", INITIAL["index.md"])]
        )

    def test_sequence_of_mixed_ops(self) -> None:
        ops: list[tuple[str, ...]] = [
            ("add", "blog/a.md", _doc("A", "Post A.")),
            ("modify", "about.md", _doc("About", "Edited.")),
            ("move", "blog/a.md", "blog/a-renamed.md"),
            ("delete", "guide/intro.md"),
            ("add", "guide/intro.md", _doc("Intro2", "New intro.")),
            ("modify", "blog/a-renamed.md", _doc("A2", "Post A v2.")),
        ]
        _assert_incremental_equals_full(self.tmp_path, INITIAL, ops)

    def test_random_sequences_incremental_equals_full(self) -> None:
        for seed in [1, 2, 7, 13, 42, 99]:
            # Use a fresh directory per seed so leftover files from one
            # sequence cannot pollute the next (each parametrize case
            # previously got its own tmp_path).
            with self.subTest(seed=seed), tempfile.TemporaryDirectory() as case_dir:
                ops = _gen_ops(seed, INITIAL, steps=12)
                _assert_incremental_equals_full(Path(case_dir), INITIAL, ops)

    def test_early_cutoff_touches_only_expected_page(self) -> None:
        """Editing one file re-emits only its page; a no-op edit emits nothing."""
        site = self.tmp_path / "inc"
        _write_site(site, INITIAL)
        session = IncrementalSession(make_builder(site))
        asyncio.run(session.initial_build())
        content_root = (site / "content").resolve()
        state = dict(INITIAL)

        edited = _apply_op(
            site,
            content_root,
            state,
            ("modify", "about.md", _doc("About", "New body.")),
        )
        self.assertEqual(session.apply(coalesce(edited)).changed_outputs, {"/about/"})

        # Rewriting the identical bytes changes nothing: raw-hash short-circuit.
        noop = _apply_op(
            site,
            content_root,
            state,
            ("modify", "about.md", _doc("About", "New body.")),
        )
        self.assertEqual(session.apply(coalesce(noop)).changed_outputs, set())
