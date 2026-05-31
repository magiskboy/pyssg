"""Configuration for the pyssg documentation site - built by pyssg itself."""

from pathlib import Path

from pyssg.config import Config
from pyssg_cli.presets import docs
from pyssg_plugins import Fingerprint, Highlight, Statistics


def config() -> Config:
    plugins = docs(
        markdown_extensions=("fenced_code", "tables", "toc"),
        sitemap=True,
        minify=True,
        markdown_pages=True,
    )
    # Syntax highlighting: post-processes fenced code blocks with Pygments and
    # inlines the matching stylesheet via the highlight_css() template global.
    plugins.append(Highlight(style="default", dark_style="github-dark"))
    # Fingerprint owns the assets dir (replaces StaticFiles): style.css ->
    # style.<hash>.css, with the /assets/style.css reference rewritten in HTML.
    plugins.append(Fingerprint(directory="assets", dest="assets"))
    plugins.append(Statistics())
    return Config(
        src=Path("content"),
        out=Path("public"),
        options={
            "title": "pyssg",
            "tagline": "A tiny-kernel, plugin-driven static site generator",
            "repo_url": "https://github.com/magiskboy/pyssg",
            "base_url": "https://pyssg.example.com",
        },
        plugins=plugins,
    )
