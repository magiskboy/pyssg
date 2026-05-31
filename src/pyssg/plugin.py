"""Plugin protocol.

A plugin only needs an ``apply`` method to tap into the builder's hooks. This
is the entire contract between the kernel and its extensions.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from pyssg.builder import Builder


@runtime_checkable
class Plugin(Protocol):
    def apply(self, builder: Builder) -> None: ...
