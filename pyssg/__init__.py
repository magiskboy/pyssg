"""pyssg - incremental static site generator.

Architecture: three separated planes.

- Data plane: a single dependency graph of ``Node`` + ``Connection``.
- Control plane: hooks scoped to ``Builder`` (long-lived) and ``Build`` (per build).
- Plugins: composition roots that only *declare facts*; the engine owns the
  incremental/cache/scheduling algorithms.

Hard boundary: ``pyssg.core`` imports stdlib only; every third-party dependency
lives in a peripheral adapter (built-in plugin or ``pyssg.watch``). This boundary
is enforced by an automated test.
"""

from __future__ import annotations

from pyssg.config import Config

__version__ = "0.1.0"

__all__ = ["Config", "__version__"]
