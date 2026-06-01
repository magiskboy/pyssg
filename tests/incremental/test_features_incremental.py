"""M6 critical invariant: incremental == full with the FULL feature plugin set.

Extends the property test to a site running nav, content_meta,
link_resolver and the tags taxonomy. It stresses the incremental paths that
these add: tag membership changes (term pages appear/disappear), cross-document
links + backlinks, and the nav fan-out. For every operation sequence the
incremental output must stay byte-identical to a full rebuild.
"""
# ruff: noqa: E501 - this module is mostly inline Jinja template / markdown literals.

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
    asset_copy,
    content_meta,
    directory_loader,
    frontmatter,
    highlight,
    link_resolver,
    markdown,
    mermaid,
    nav,
    permalink,
    render,
    rss,
    sitemap,
    taxonomy,
    transclude,
    wikilink,
)

config = Config(
    content_dir="content",
    output_dir="dist",
    layout="layout",
    base_url="https://example.com",
    site={"title": "Feat"},
    plugins=[
        directory_loader(), frontmatter(), markdown(), mermaid(), highlight(),
        content_meta(), permalink(), wikilink(), link_resolver(), transclude(),
        nav(), taxonomy(), sitemap(), rss(), asset_copy(), render(),
    ],
)
"""

BASE = """\
<!doctype html><html><head><title>{{ page.title }} | {{ site.title }}</title></head><body>
<aside>{% for sec in menu %}<div>{{ sec.section }}<ul>{% for i in sec['items'] %}\
<li><a href="{{ i.url }}">{{ i.title }}</a></li>{% endfor %}</ul></div>{% endfor %}</aside>
<main>{% block content %}{% endblock %}</main></body></html>
"""

PAGE = """\
{% extends "base.html.j2" %}{% block content %}
<nav>{% for c in breadcrumbs %}<a href="{{ c.url }}">{{ c.title }}</a>{% endfor %}</nav>
<h1>{{ page.title }}</h1><p>{{ reading_time }}m</p>
{% if toc %}<ul class="toc">{% for h in toc %}<li><a href="#{{ h.slug }}">{{ h.text }}</a></li>{% endfor %}</ul>{% endif %}
{{ content_html }}
{% if tags %}<p>{% for t in tags %}<a href="/tags/{{ t }}/">#{{ t }}</a>{% endfor %}</p>{% endif %}
{% if prev %}<a href="{{ prev.url }}">{{ prev.title }}</a>{% endif %}
{% if next %}<a href="{{ next.url }}">{{ next.title }}</a>{% endif %}
{% if backlinks %}<aside class="bl">{% for b in backlinks %}<a href="{{ b.url }}">{{ b.title }}</a>{% endfor %}</aside>{% endif %}
{% endblock %}
"""

TERM = """\
{% extends "base.html.j2" %}{% block content %}<h1>{{ page.title }}</h1>
<ul>{% for m in page.members %}<li><a href="{{ m.url }}">{{ m.title }}</a></li>{% endfor %}</ul>{% endblock %}
"""

TERMS = """\
{% extends "base.html.j2" %}{% block content %}<h1>{{ page.title }}</h1>
<ul>{% for t in page.terms %}<li><a href="{{ t.url }}">{{ t.term }} {{ t.count }}</a></li>{% endfor %}</ul>{% endblock %}
"""


def _doc(title: str, body: str, tags: list[str] | None = None) -> str:
    fm = [f"title: {title}"]
    if tags is not None:
        fm.append("tags: [" + ", ".join(tags) + "]")
    return "---\n" + "\n".join(fm) + "\n---\n" + body + "\n"


def _write_site(site: Path, content: dict[str, str]) -> None:
    site.mkdir(parents=True, exist_ok=True)
    (site / "pyssg.config.py").write_text(CONFIG_TEXT, encoding="utf-8")
    tpl = site / "layout" / "templates"
    tpl.mkdir(parents=True, exist_ok=True)
    (site / "layout" / "layout.toml").write_text(
        'name="f"\nversion="0"\ndefault_template="page.html.j2"\n', encoding="utf-8"
    )
    (tpl / "base.html.j2").write_text(BASE, encoding="utf-8")
    (tpl / "page.html.j2").write_text(PAGE, encoding="utf-8")
    (tpl / "term.html.j2").write_text(TERM, encoding="utf-8")
    (tpl / "terms.html.j2").write_text(TERMS, encoding="utf-8")
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
    "index.md": _doc(
        "Home",
        "Welcome. See [guide](./guide/intro.md) and [[Advanced]].\n\n"
        "```python\nprint('hi')\n```\n\n![[About]]",
        ["intro"],
    ),
    "guide/intro.md": _doc(
        "Intro",
        "# Intro\n\nBack to [home](../index.md). Also [[Home]].\n\n"
        "```mermaid\ngraph TD; A-->B\n```",
        ["python", "intro"],
    ),
    "guide/advanced.md": _doc("Advanced", "# Advanced\n\nDeep dive.", ["python"]),
    "about.md": _doc("About", "# About\n\nNo tags here."),
}


def _gen_ops(seed: int, initial: dict[str, str], steps: int) -> list[tuple[str, ...]]:
    rng = random.Random(seed)
    files = set(initial)
    pool = ["python", "intro", "blog", "newtag", "web"]
    counter = 0
    ops: list[tuple[str, ...]] = []
    for _ in range(steps):
        choices = ["add"] + (["modify", "retag", "delete", "move"] if files else [])
        choice = rng.choice(choices)
        if choice == "add":
            counter += 1
            rel = f"gen/n{counter}.md"
            files.add(rel)
            tags = rng.sample(pool, rng.randint(0, 2))
            ops.append(("add", rel, _doc(f"Gen {counter}", f"# Gen {counter}\n\nbody.", tags)))
        elif choice in {"modify", "retag"}:
            rel = rng.choice(sorted(files))
            tags = rng.sample(pool, rng.randint(0, 2))
            ops.append(("modify", rel, _doc("T", f"# H\n\nbody {rng.randint(0, 99)}.", tags)))
        elif choice == "delete":
            rel = rng.choice(sorted(files))
            files.discard(rel)
            ops.append(("delete", rel))
        else:
            rel = rng.choice(sorted(files))
            files.discard(rel)
            counter += 1
            dst = f"moved/m{counter}.md"
            files.add(dst)
            ops.append(("move", rel, dst))
    return ops


class FeaturesIncrementalTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_path = Path(self.enterContext(tempfile.TemporaryDirectory()))

    def test_edit_body(self) -> None:
        op = ("modify", "about.md", _doc("About", "# About\n\nEdited body."))
        _assert_eq(self.tmp_path, INITIAL, [op])

    def test_add_tag_creates_term_page(self) -> None:
        op = ("modify", "about.md", _doc("About", "# About\n\nx.", ["newtag"]))
        _assert_eq(self.tmp_path, INITIAL, [op])

    def test_remove_tag_drops_term_page(self) -> None:
        op = ("modify", "guide/advanced.md", _doc("Advanced", "# Advanced\n\nd.", []))
        _assert_eq(self.tmp_path, INITIAL, [op])

    def test_change_link_target_title_updates_backlink(self) -> None:
        # index links to guide/intro; intro links back to home. Retitle home.
        body = "Welcome. See [guide](./guide/intro.md)."
        op = ("modify", "index.md", _doc("HomeRenamed", body, ["intro"]))
        _assert_eq(self.tmp_path, INITIAL, [op])

    def test_add_tagged_doc(self) -> None:
        op = ("add", "guide/extra.md", _doc("Extra", "# Extra\n\nx.", ["python", "newtag"]))
        _assert_eq(self.tmp_path, INITIAL, [op])

    def test_delete_tagged_doc(self) -> None:
        _assert_eq(self.tmp_path, INITIAL, [("delete", "guide/advanced.md")])

    def test_move_doc(self) -> None:
        _assert_eq(self.tmp_path, INITIAL, [("move", "about.md", "company/about.md")])

    def test_mixed_sequence(self) -> None:
        ops: list[tuple[str, ...]] = [
            ("add", "blog/p1.md", _doc("P1", "# P1\n\nFirst.", ["blog"])),
            ("modify", "guide/advanced.md", _doc("Advanced", "# A\n\nv2.", ["python", "blog"])),
            ("delete", "guide/intro.md"),
            ("move", "blog/p1.md", "blog/p1-renamed.md"),
            ("modify", "about.md", _doc("About", "# About\n\nnow tagged.", ["intro"])),
        ]
        _assert_eq(self.tmp_path, INITIAL, ops)

    def test_random_full_feature_sequences(self) -> None:
        for seed in [1, 3, 5, 8, 21]:
            # Use a fresh directory per seed so leftover files from one
            # sequence cannot pollute the next (each parametrize case
            # previously got its own tmp_path).
            with self.subTest(seed=seed), tempfile.TemporaryDirectory() as case_dir:
                _assert_eq(Path(case_dir), INITIAL, _gen_ops(seed, INITIAL, steps=10))
