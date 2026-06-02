from __future__ import annotations

from pyssg.presets import blog

# Drive the gallery `blog-technical` theme through the blog preset (paginated
# post collection). The theme is not packaged with pyssg (it lives in the
# repo-root `themes/` gallery, not `pyssg/themes/`), so the test vendors it into
# this site under `theme/` and we point `layout` at that relative path -- the
# same way a user would adopt a gallery theme into their project.
#
# `theme=` overrides exercise the theme configuration API (#53): the layout.toml
# [options] defaults are layered under these site-level values.
config = blog(
    site={"title": "My Blog"},
    base_url="https://example.com",
    posts_per_page=2,
    layout="theme",
)
config.theme = {"default_theme": "dark", "toc_open": True}
