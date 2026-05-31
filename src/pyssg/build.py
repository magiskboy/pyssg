"""State of a single build run.

Corresponds to webpack's ``Compilation``: created fresh on each run, holding all
sources, outputs and errors of that run.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pyssg.config import Config
from pyssg.models import Output, Source


@dataclass(slots=True)
class Build:
    config: Config
    sources: list[Source] = field(default_factory=list)
    outputs: list[Output] = field(default_factory=list)
    errors: list[Exception] = field(default_factory=list)
    # Site-wide context bag. The ``collect`` pass fills it (collections,
    # navigation, site config); ``render``/``generate`` read from it.
    meta: dict[str, object] = field(default_factory=dict)
