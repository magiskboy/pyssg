from __future__ import annotations

from pyssg.presets import blog

# A blog that uses a CUSTOMIZED theme instead of a bundled one.
#
# Two customization mechanisms are demonstrated:
#
# 1. A local layout (``layout/``), ejected from the built-in ``blog`` theme with
#    ``pyssg eject-layout`` and then edited: tweaked templates (an accent header
#    band, a tagline, a footer note) and a rebranded ``assets/style.css``.
#    ``layout="layout"`` is a site-relative path, so it resolves against this
#    directory.
#
# 2. Theme options. The layout declares defaults in ``layout/layout.toml``
#    under ``[options]``; the ``theme={...}`` dict below overrides them per-key
#    (a shallow merge). Templates read both as ``theme.<key>``. Here we override
#    the accent colour and the tagline while leaving ``footer_note`` and
#    ``show_reading_time`` at their layout defaults.
config = blog(
    site={
        "title": "Off the Shelf",
        "description": "A blog wearing a hand-tailored pyssg theme.",
    },
    base_url="https://custom.example.com",
    posts_per_page=3,
    layout="layout",
)
config.theme = {
    "accent": "#7a3cff",
    "tagline": "Same engine, a theme of my own",
}
