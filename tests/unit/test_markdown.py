"""Unit tests for the ``markdown`` plugin (Python-Markdown engine)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pyssg.config import Config
from pyssg.core.build import Build
from pyssg.core.builder import Builder
from pyssg.core.node import Document
from pyssg.core.types import NodeKind
from pyssg.plugins.markdown import MarkdownPlugin, markdown


def _build(tmp_path: Path, plugin: MarkdownPlugin | None = None) -> Build:
    builder = Builder(config=Config(output_dir="dist"), site_dir=tmp_path)
    build = builder.create_build()
    (plugin or markdown()).apply(builder)
    builder.hooks.this_compilation.call(build)
    return build


def _parse(build: Build, raw: str, *, doc_id: str = "doc.md") -> Document:
    node = Document(id=doc_id, kind=NodeKind.MARKDOWN, source_path=doc_id)
    node.meta["__raw__"] = raw
    build.hooks.parse.call(node)
    return node


class MarkdownPluginTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_path = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.build = _build(self.tmp_path)

    def test_plugin_exposes_name_and_factory(self) -> None:
        plugin = markdown()
        self.assertIsInstance(plugin, MarkdownPlugin)
        self.assertEqual(plugin.name, "markdown")

    def test_renders_paragraph_and_sets_both_html_keys(self) -> None:
        node = _parse(self.build, "# Title\n\nHello world.")
        self.assertIn("<p>Hello world.</p>", str(node.meta["content_html"]))
        # The verbatim pre-link copy is seeded identically for the link resolver.
        self.assertEqual(node.meta["content_html"], node.meta["__content_html_raw__"])

    def test_fenced_code_uses_language_class(self) -> None:
        # The highlight/mermaid plugins depend on this exact markup.
        node = _parse(self.build, "```python\nx = 1\n```")
        self.assertIn('<pre><code class="language-python">', str(node.meta["content_html"]))

    def test_tables_extension_enabled(self) -> None:
        node = _parse(self.build, "| A | B |\n|---|---|\n| 1 | 2 |")
        html = str(node.meta["content_html"])
        self.assertIn("<table>", html)
        self.assertIn("<th>A</th>", html)

    def test_headings_get_ids_via_project_slugify(self) -> None:
        # The toc extension is wired to the project slugify, so Unicode survives.
        node = _parse(self.build, "## Giới thiệu")
        self.assertIn('id="giới-thiệu"', str(node.meta["content_html"]))

    def test_ast_holds_toc_token_tree(self) -> None:
        node = _parse(self.build, "# A\n\n## B")
        ast = node.ast
        assert isinstance(ast, list)
        self.assertEqual(ast[0]["name"], "A")
        self.assertEqual(ast[0]["children"][0]["name"], "B")

    def test_title_from_first_heading(self) -> None:
        node = _parse(self.build, "# The First Heading\n\nbody")
        self.assertEqual(node.meta["title"], "The First Heading")

    def test_frontmatter_title_wins_over_heading(self) -> None:
        node = Document(id="d.md", kind=NodeKind.MARKDOWN, source_path="d.md")
        node.meta["__raw__"] = "# Heading"
        node.meta["title"] = "Explicit"
        self.build.hooks.parse.call(node)
        self.assertEqual(node.meta["title"], "Explicit")

    def test_reads_body_when_frontmatter_split_it(self) -> None:
        node = Document(id="d.md", kind=NodeKind.MARKDOWN, source_path="d.md")
        node.meta["__raw__"] = "---\ntitle: X\n---\n# Body heading"
        node.meta["__body__"] = "# Body heading"
        self.build.hooks.parse.call(node)
        self.assertIn("Body heading", str(node.meta["content_html"]))

    def test_parser_reset_keeps_documents_independent(self) -> None:
        # A reused parser must not leak one document's headings into the next.
        first = _parse(self.build, "# One", doc_id="one.md")
        second = _parse(self.build, "Just prose, no heading.", doc_id="two.md")
        self.assertEqual(first.meta["title"], "One")
        self.assertEqual(second.ast, [])

    def test_ignores_non_markdown_node(self) -> None:
        node = Document(id="d.dat", kind=NodeKind.DATA, source_path="d.dat")
        node.meta["__raw__"] = "# Heading"
        self.build.hooks.parse.call(node)
        self.assertNotIn("content_html", node.meta)

    def test_load_hook_reads_markdown_files_only(self) -> None:
        md_file = self.tmp_path / "page.md"
        md_file.write_text("# Hi", encoding="utf-8")
        loaded = self.build.hooks.load_node.call(str(md_file))
        assert isinstance(loaded, Document)
        self.assertEqual(loaded.kind, NodeKind.MARKDOWN)
        self.assertEqual(loaded.meta["__raw__"], "# Hi")
        self.assertIsNone(self.build.hooks.load_node.call(str(self.tmp_path / "data.json")))


class MarkdownConfigurationTest(unittest.TestCase):
    """Extra extensions / extension_configs can be supplied without subclassing."""

    def setUp(self) -> None:
        self.tmp_path = Path(self.enterContext(tempfile.TemporaryDirectory()))

    def test_extra_extension_is_applied(self) -> None:
        # ``nl2br`` (ships with Python-Markdown) turns single newlines into <br>.
        build = _build(self.tmp_path, markdown(extensions=["nl2br"]))
        node = _parse(build, "line one\nline two")
        self.assertIn("<br", str(node.meta["content_html"]))

    def test_default_engine_does_not_break_single_newlines(self) -> None:
        # Guard the contrast: without nl2br a soft break stays a space, not <br>.
        build = _build(self.tmp_path, markdown())
        node = _parse(build, "line one\nline two")
        self.assertNotIn("<br", str(node.meta["content_html"]))

    def test_extension_configs_forwarded_to_toc(self) -> None:
        build = _build(self.tmp_path, markdown(extension_configs={"toc": {"permalink": True}}))
        node = _parse(build, "## Section")
        self.assertIn("headerlink", str(node.meta["content_html"]))

    def test_toc_slugify_survives_caller_toc_config(self) -> None:
        # Supplying a toc config must not drop the project slugify default.
        build = _build(self.tmp_path, markdown(extension_configs={"toc": {"permalink": True}}))
        node = _parse(build, "## Giới thiệu")
        self.assertIn('id="giới-thiệu"', str(node.meta["content_html"]))

    def test_cache_version_changes_with_configuration(self) -> None:
        default = markdown().cache_version
        self.assertEqual(default, "2.0.0")
        with_ext = markdown(extensions=["nl2br"]).cache_version
        with_cfg = markdown(extension_configs={"toc": {"permalink": True}}).cache_version
        self.assertNotEqual(default, with_ext)
        self.assertNotEqual(default, with_cfg)
        self.assertNotEqual(with_ext, with_cfg)

    def test_cache_version_is_deterministic(self) -> None:
        first = markdown(extensions=["nl2br"], extension_configs={"toc": {"permalink": True}})
        second = markdown(extensions=["nl2br"], extension_configs={"toc": {"permalink": True}})
        self.assertEqual(first.cache_version, second.cache_version)


class MarkdownSubclassTest(unittest.TestCase):
    """Subclasses can customise the engine via the documented override points."""

    def setUp(self) -> None:
        self.tmp_path = Path(self.enterContext(tempfile.TemporaryDirectory()))

    def test_subclass_can_extend_default_extensions(self) -> None:
        class NlToBrMarkdown(MarkdownPlugin):
            default_extensions = (*MarkdownPlugin.default_extensions, "nl2br")

        build = _build(self.tmp_path, NlToBrMarkdown())
        node = _parse(build, "line one\nline two")
        self.assertIn("<br", str(node.meta["content_html"]))

    def test_subclass_can_override_extension_configs(self) -> None:
        class PermalinkMarkdown(MarkdownPlugin):
            def resolve_extension_configs(self) -> dict[str, object]:
                configs = super().resolve_extension_configs()
                configs["toc"] = {**configs["toc"], "permalink": True}
                return configs

        build = _build(self.tmp_path, PermalinkMarkdown())
        node = _parse(build, "## Section")
        self.assertIn("headerlink", str(node.meta["content_html"]))
