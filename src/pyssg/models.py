"""Kernel data models.

The kernel knows nothing about markdown or HTML; it only provides neutral data
bags that plugins fill in at each lifecycle stage.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class Source:
    """A source file discovered in the input directory.

    Fields are populated gradually through the lifecycle:
    ``load`` -> ``raw``; ``parse`` -> ``frontmatter`` + ``body``;
    ``transform`` -> ``content``; ``render`` -> emits an ``Output``.
    """

    path: Path
    relpath: Path
    raw: str = ""
    body: str = ""
    content: str = ""
    frontmatter: dict[str, object] = field(default_factory=dict)
    meta: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class Output:
    """A result file to be written to the output directory.

    ``path`` is relative to the ``out`` directory.
    """

    path: Path
    content: str
    source: Source | None = None
