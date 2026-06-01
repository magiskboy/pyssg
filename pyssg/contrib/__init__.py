"""Community-contributed plugins.

These live apart from the built-in plugins in :mod:`pyssg.plugins`: they follow
the same ``Plugin`` protocol and the same purity rules, and may use third-party
libraries (they are peripheral adapters, never imported by ``pyssg.core``), but
they are maintained by the community rather than the core.

Conventions for a contrib plugin (one module ``pyssg/contrib/<name>.py``):

- expose a factory function ``<name>()`` returning the plugin instance, exactly
  like the built-ins, so a config can ``from pyssg.contrib.<name> import <name>``;
- declare ``name`` and ``cache_version`` attributes and implement ``apply``;
- be **pure**: derive output only from declared inputs -- no clock, randomness or
  global mutable state -- so two builds stay byte-identical and incremental
  rebuilds equal full rebuilds;
- ship a unit test and pass ``mypy --strict`` + ``ruff``.

Unlike the built-ins, contrib plugins are intentionally **not** re-exported from
this package; import them explicitly by module so each contribution stays opt-in
and independent.
"""

from __future__ import annotations
