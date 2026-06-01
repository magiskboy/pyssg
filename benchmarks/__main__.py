"""CLI entry point: run the incremental benchmarks and render the report.

    uv run python -m benchmarks                 # all three sizes + charts
    uv run python -m benchmarks --quick         # small + medium only
    uv run python -m benchmarks --sizes small   # an explicit subset
    uv run python -m benchmarks --no-charts     # skip matplotlib (JSON only)

Per-size JSON is written to ``benchmarks/results/``; with charts enabled the run
also writes ``scaling.png``, ``speedup.png``, ``outputs.png`` and ``REPORT.md``
there. All of ``results/`` is gitignored.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from benchmarks.runner import run_size
from benchmarks.sizes import ALL_SIZES, QUICK_SIZES, SiteSize, by_name

PACKAGE_DIR = Path(__file__).resolve().parent
DEFAULT_RESULTS = PACKAGE_DIR / "results"
WORK_DIR = PACKAGE_DIR / ".bench-work"


def _rel(path: Path) -> str:
    """Path relative to the current directory when possible, else absolute."""
    try:
        return str(path.relative_to(Path.cwd()))
    except ValueError:
        return str(path)


def _select_sizes(args: argparse.Namespace) -> tuple[SiteSize, ...]:
    if args.sizes:
        names = [n.strip() for n in args.sizes.split(",") if n.strip()]
        return tuple(by_name(n) for n in names)
    if args.quick:
        return QUICK_SIZES
    return ALL_SIZES


def _verify_for(size: SiteSize, args: argparse.Namespace) -> bool:
    if args.no_verify:
        return False
    if args.verify_all:
        return True
    return size.verify_default


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m benchmarks", description=__doc__)
    parser.add_argument("--quick", action="store_true", help="run small + medium only")
    parser.add_argument("--sizes", default="", help="comma-separated subset, e.g. 'small,large'")
    parser.add_argument("--results", default=str(DEFAULT_RESULTS), help="output directory")
    parser.add_argument("--no-charts", action="store_true", help="skip matplotlib charts + report")
    parser.add_argument("--verify-all", action="store_true", help="byte-identical check, all sizes")
    parser.add_argument("--no-verify", action="store_true", help="skip the byte-identical check")
    args = parser.parse_args(argv)

    sizes = _select_sizes(args)
    results_dir = Path(args.results).resolve()
    results_dir.mkdir(parents=True, exist_ok=True)

    if WORK_DIR.exists():
        shutil.rmtree(WORK_DIR)
    WORK_DIR.mkdir(parents=True)

    try:
        for size in sizes:
            verify = _verify_for(size, args)
            print(
                f"[benchmarks] {size.name}: {size.n_docs} docs, "
                f"{size.iterations} iterations/scenario, verify={verify}"
            )
            report = run_size(size, WORK_DIR, verify=verify)
            out = report.write_json(results_dir)
            print(
                f"[benchmarks] {size.name}: cold build {report.cold_incremental_ms:.0f} ms "
                f"({report.cold_outputs} outputs) -> {_rel(out)}"
            )
    finally:
        shutil.rmtree(WORK_DIR, ignore_errors=True)

    if not args.no_charts:
        from benchmarks.visualize import visualize

        report_md = visualize(results_dir)
        print(f"[benchmarks] report -> {_rel(report_md)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
