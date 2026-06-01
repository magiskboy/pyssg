"""Plugin API surface.

A plugin is a composition root: it only *declares facts* (units, connections,
aspects, cache versions). The engine owns every incremental algorithm, so as
long as a plugin's declarations are honest (the purity contract) it
cannot break incremental correctness.

This module is peripheral (not ``pyssg.core``), so it MAY import third-party
libs -- but the base protocol here needs none.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from pyssg.core.builder import Builder


@runtime_checkable
class Plugin(Protocol):
    """Structural contract every plugin satisfies.

    ``cache_version`` folds into the cache key of every unit the plugin creates;
    bump it whenever the plugin's behavior changes so stale cached output is
    busted.
    """

    name: str
    cache_version: str

    def apply(self, builder: Builder) -> None: ...


@dataclass(slots=True)
class PluginContext:
    """Convenience handle passed to plugin helpers.

    Thin in M2; gains declaration helpers (``define_aspect`` etc.) as later
    milestones wire the aspect/collection machinery.
    """

    builder: Builder
