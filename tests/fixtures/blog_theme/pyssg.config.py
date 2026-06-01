from __future__ import annotations

from pyssg.presets import docs
from pyssg.themes import theme_path

# U2: exercise the built-in `blog` theme with the existing plugin set. The blog
# preset (date-sorted, paginated post collection) arrives in U3 with M6.
config = docs(
    site={"title": "My Blog"},
    base_url="https://example.com",
    layout=theme_path("blog"),
)
