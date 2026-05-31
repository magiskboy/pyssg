"""End-to-end integration tests running full presets through the Builder."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pyssg.builder import Builder
from pyssg.config import Config
from pyssg_cli.presets import blog, docs


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class BlogIntegrationTest(unittest.TestCase):
    def test_blog_build_produces_posts_index_and_tags(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            content = root / "content"
            layouts = root / "layouts"
            out = root / "public"

            write(
                content / "about.md", "---\ntitle: About\nmenu: main\n---\nAbout us\n"
            )
            write(
                content / "blog" / "first.md",
                "---\ntitle: First\ndate: 2024-01-01\ntags: [python]\n---\nHello\n",
            )
            write(
                content / "blog" / "second.md",
                "---\ntitle: Second\ndate: 2024-02-01\n"
                "tags: [python, web]\n---\nWorld\n",
            )

            write(
                layouts / "default.html",
                "<article>{{ page.title }}|{{ content }}</article>",
            )
            write(
                layouts / "list.html",
                "<ul>{% for item in page.entries %}"
                "<li><a href='{{ item.url }}'>{{ item.title }}</a></li>"
                "{% endfor %}</ul>",
            )

            config = Config(src=content, out=out, plugins=blog())
            Builder(config).run()

            # Standalone page with pretty URL.
            self.assertTrue((out / "about" / "index.html").exists())
            # Individual posts.
            self.assertTrue((out / "blog" / "first" / "index.html").exists())
            # Blog index listing.
            blog_index = (out / "blog" / "index.html").read_text()
            self.assertIn("/blog/first/", blog_index)
            self.assertIn("/blog/second/", blog_index)
            # Tag pages, one per tag.
            self.assertTrue((out / "tags" / "python" / "index.html").exists())
            self.assertTrue((out / "tags" / "web" / "index.html").exists())
            python_page = (out / "tags" / "python" / "index.html").read_text()
            self.assertIn("/blog/first/", python_page)
            self.assertIn("/blog/second/", python_page)

    def test_blog_pagination(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            content = root / "content"
            layouts = root / "layouts"
            out = root / "public"

            for i in range(5):
                write(
                    content / "blog" / f"post{i}.md",
                    f"---\ntitle: Post {i}\ndate: 2024-01-0{i + 1}\n---\nBody {i}\n",
                )
            write(layouts / "default.html", "{{ content }}")
            write(
                layouts / "list.html",
                "p{{ page.paginator.number }}/{{ page.paginator.total_pages }}",
            )

            config = Config(src=content, out=out, plugins=blog(page_size=2))
            Builder(config).run()

            self.assertEqual((out / "blog" / "index.html").read_text(), "p1/3")
            self.assertEqual(
                (out / "blog" / "page" / "2" / "index.html").read_text(), "p2/3"
            )
            self.assertEqual(
                (out / "blog" / "page" / "3" / "index.html").read_text(), "p3/3"
            )


class DocsIntegrationTest(unittest.TestCase):
    def test_docs_build_with_sidebar_and_prev_next(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            content = root / "content"
            layouts = root / "layouts"
            out = root / "public"

            write(content / "index.md", "---\ntitle: Home\n---\nWelcome\n")
            write(
                content / "guide" / "index.md",
                "---\ntitle: Guide\norder: 1\n---\nGuide\n",
            )
            write(
                content / "guide" / "install.md",
                "---\ntitle: Install\norder: 1\n---\nInstall\n",
            )
            write(
                content / "guide" / "usage.md",
                "---\ntitle: Usage\norder: 2\n---\nUsage\n",
            )

            nav = (
                "{% for node in menus.main %}{{ node.title }}"
                "{% for c in node.children %}>{{ c.title }}{% endfor %}{% endfor %}"
            )
            prevnext = "{% if page.prev %}P:{{ page.prev.title }}{% endif %}"
            write(layouts / "default.html", f"NAV[{nav}]{prevnext}|{{{{ content }}}}")

            config = Config(src=content, out=out, plugins=docs())
            Builder(config).run()

            install = (out / "guide" / "install" / "index.html").read_text()
            # Sidebar shows the Guide section with its children.
            self.assertIn("Guide>Install>Usage", install)
            # Usage follows Install in sequential order.
            usage = (out / "guide" / "usage" / "index.html").read_text()
            self.assertIn("P:Install", usage)


if __name__ == "__main__":
    unittest.main()
