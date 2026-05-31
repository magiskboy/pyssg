"""pyssg-cli: the command-line interface, presets and scaffolding for pyssg.

This is the "batteries" layer (webpack-cli style): it depends on
``pyssg_plugins`` (the built-in plugins) and on ``pyssg`` (the core kernel),
and provides the ``pyssg`` console script, ready-made preset stacks and the
``pyssg new`` site scaffolder.
"""

from __future__ import annotations
