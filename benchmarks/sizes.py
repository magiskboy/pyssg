"""Declarative definitions of the three benchmark site sizes.

Each :class:`SiteSize` is a pure description: how many documents to generate and
how many incremental iterations to run per scenario. Generating large reference
rebuilds for the byte-identical check is expensive at 10k documents, so the
``verify`` flag lets the orchestrator turn that correctness check off for the
largest size by default (it can be forced back on from the CLI).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SiteSize:
    """One benchmark size: a document count plus its iteration budget."""

    name: str
    n_docs: int
    docs_per_section: int
    iterations: int
    verify_default: bool


SMALL = SiteSize(name="small", n_docs=100, docs_per_section=10, iterations=20, verify_default=True)
MEDIUM = SiteSize(
    name="medium", n_docs=1000, docs_per_section=25, iterations=10, verify_default=True
)
LARGE = SiteSize(
    name="large", n_docs=10000, docs_per_section=50, iterations=5, verify_default=False
)

ALL_SIZES: tuple[SiteSize, ...] = (SMALL, MEDIUM, LARGE)
QUICK_SIZES: tuple[SiteSize, ...] = (SMALL, MEDIUM)


def by_name(name: str) -> SiteSize:
    """Look up a size by its ``name`` (used by CLI selection)."""
    for size in ALL_SIZES:
        if size.name == name:
            return size
    valid = ", ".join(s.name for s in ALL_SIZES)
    raise KeyError(f"unknown size {name!r}; expected one of: {valid}")
