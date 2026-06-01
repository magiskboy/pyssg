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
    site={"title": "Docs Min"},
    plugins=[
        directory_loader(),
        frontmatter(),
        markdown(),
        permalink(),
        render(),
    ],
)
