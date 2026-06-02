"""Presets: one-call factories that return a ready-to-use :class:`~pyssg.Config`.

Each preset bundles a curated set of built-in plugins (in the correct apply
order) plus a default theme, so the basic user can stand up a site with a single
line in ``pyssg.config.py``::

    from pyssg.presets import docs
    config = docs(site={"title": "My Docs"})

Presets only declare facts (plugin list + theme); the engine owns all
algorithms. Build a :class:`Config` by hand for full control.
"""

from __future__ import annotations

from pyssg.presets.blog import blog
from pyssg.presets.docs import docs
from pyssg.presets.obsidian import obsidian

__all__ = ["blog", "docs", "obsidian"]
