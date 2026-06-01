"""Core exception hierarchy (stdlib only).

Errors raised by the engine are explicit configuration / contract violations, so
plugin authors get a clear message instead of silent incorrectness.
"""

from __future__ import annotations


class PyssgError(Exception):
    """Base class for all pyssg errors."""


class HookOrderError(PyssgError):
    """A hook's tap ordering constraints (before/after) form a cycle."""


class ConfigError(PyssgError):
    """The site configuration is invalid or could not be loaded."""


class LayoutError(PyssgError):
    """A layout package is missing required pieces or is malformed."""
