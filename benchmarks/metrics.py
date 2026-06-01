"""Measurement records and JSON serialization for benchmark results.

Every iteration measures the same content state two ways: the **naive** path (a
full rebuild from scratch with the cache disabled, i.e. what a non-incremental
generator does on each save) and the **incremental** path (an
``IncrementalSession.apply`` reusing the persistent cache). Recording both lets
the report state the incremental speedup directly, and comparing their output
doubles as the byte-identical correctness check.
"""

from __future__ import annotations

import json
import statistics
from dataclasses import dataclass
from pathlib import Path

from pyssg.core.build import BuildStats
from pyssg.core.types import Phase


@dataclass(frozen=True, slots=True)
class IterationMetric:
    """One rebuild measured both naively and incrementally."""

    iteration: int
    files_changed: int
    naive_ms: float
    incremental_ms: float
    docs_parsed: int
    cache_hits: int
    outputs_changed: int
    identical: bool

    def to_dict(self) -> dict[str, float | int | bool]:
        return {
            "iteration": self.iteration,
            "files_changed": self.files_changed,
            "naive_ms": self.naive_ms,
            "incremental_ms": self.incremental_ms,
            "docs_parsed": self.docs_parsed,
            "cache_hits": self.cache_hits,
            "outputs_changed": self.outputs_changed,
            "identical": self.identical,
        }


def make_iteration(
    iteration: int,
    files_changed: int,
    naive_ms: float,
    incremental_ms: float,
    stats: BuildStats,
    identical: bool,
) -> IterationMetric:
    """Build an :class:`IterationMetric` from raw timings and incremental stats."""
    return IterationMetric(
        iteration=iteration,
        files_changed=files_changed,
        naive_ms=naive_ms,
        incremental_ms=incremental_ms,
        docs_parsed=stats.touched_per_phase.get(Phase.PARSE, 0),
        cache_hits=stats.cache_hits,
        outputs_changed=len(stats.changed_outputs),
        identical=identical,
    )


def _summary(values: list[float]) -> dict[str, float]:
    """min / median / mean / max of a list (empty -> all zeros)."""
    if not values:
        return {"min": 0.0, "median": 0.0, "mean": 0.0, "max": 0.0}
    return {
        "min": min(values),
        "median": statistics.median(values),
        "mean": statistics.fmean(values),
        "max": max(values),
    }


@dataclass(frozen=True, slots=True)
class ScenarioMetric:
    """All iterations of one scenario, plus naive-vs-incremental aggregates."""

    name: str
    description: str
    batch_size: int
    iterations: list[IterationMetric]

    def naive_ms(self) -> dict[str, float]:
        return _summary([it.naive_ms for it in self.iterations])

    def incremental_ms(self) -> dict[str, float]:
        return _summary([it.incremental_ms for it in self.iterations])

    def speedup(self) -> float:
        """Naive median ms divided by incremental median ms."""
        inc = self.incremental_ms()["median"]
        return self.naive_ms()["median"] / inc if inc > 0 else 0.0

    def all_identical(self) -> bool:
        return all(it.identical for it in self.iterations)

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "description": self.description,
            "batch_size": self.batch_size,
            "all_identical": self.all_identical(),
            "naive_ms": self.naive_ms(),
            "incremental_ms": self.incremental_ms(),
            "speedup": self.speedup(),
            "iterations": [it.to_dict() for it in self.iterations],
        }


@dataclass(frozen=True, slots=True)
class SizeReport:
    """The full result for one site size."""

    size: str
    n_docs: int
    cold_incremental_ms: float
    cold_outputs: int
    scenarios: list[ScenarioMetric]

    def to_dict(self) -> dict[str, object]:
        return {
            "size": self.size,
            "n_docs": self.n_docs,
            "cold_incremental_ms": self.cold_incremental_ms,
            "cold_outputs": self.cold_outputs,
            "scenarios": [s.to_dict() for s in self.scenarios],
        }

    def write_json(self, results_dir: Path) -> Path:
        """Write ``bench-<size>.json`` into ``results_dir`` and return its path."""
        results_dir.mkdir(parents=True, exist_ok=True)
        out = results_dir / f"bench-{self.size}.json"
        out.write_text(json.dumps(self.to_dict(), indent=2) + "\n", encoding="utf-8")
        return out


def load_size_report(path: Path) -> dict[str, object]:
    """Read one ``bench-<size>.json`` back into a plain dict."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return data
