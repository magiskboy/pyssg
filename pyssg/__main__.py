"""Enable ``python -m pyssg`` as a CLI entry point."""

from __future__ import annotations

from pyssg.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
