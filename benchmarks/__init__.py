"""Performance benchmarks for pyssg's incremental build engine.

This package is peripheral tooling: it imports the public pyssg surface but is
never imported back by ``pyssg`` itself, and it is free to use third-party
libraries (matplotlib) that the core forbids. It measures wall-clock cost and
work-done counters for full builds versus incremental rebuilds across three
synthetic site sizes, then renders charts and a Markdown report.

Run it with ``uv run python -m benchmarks``.
"""

from __future__ import annotations

__all__ = ["__doc__"]
