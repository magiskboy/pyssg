# Contributing to pyssg

Thanks for your interest in contributing! This document explains how to set up a
development environment and the conventions the project follows.

## Development setup

pyssg uses [uv](https://docs.astral.sh/uv/) as its package manager and targets
Python 3.13.

```bash
git clone https://github.com/magiskboy/pyssg.git
cd pyssg
uv sync --all-extras          # runtime extras + dev tools (ruff, mypy, types)
source .venv/bin/activate
```

`--all-extras` installs every optional dependency (markdown, jinja2, pyyaml,
pygments, watchdog) so the full test suite and type checks run.

Optionally, install the git hooks so ruff and mypy run automatically before each
commit:

```bash
uv run pre-commit install
```

## Checks

All four checks must pass before a pull request is merged; CI runs the same
commands on Linux, macOS, and Windows.

```bash
ruff check .                  # lint
ruff format --check .         # formatting (run `ruff format .` to apply)
mypy                          # strict type checking
python -m unittest discover -s tests
```

## Conventions

- **Python 3.13** with strict typing. `mypy` runs in `strict` mode; do not add
  `# type: ignore` without a clear reason.
- **English only in code** — identifiers, comments, docstrings, and log/error
  strings. (Issues and discussions may be in any language.)
- **Keep the kernel dependency-free.** The `pyssg` package uses only the standard
  library. Third-party dependencies belong in plugins under `pyssg_plugins` and
  must be declared as optional extras in `pyproject.toml` and imported lazily.
- **Prefer simplicity over cleverness.** Favor clear, well-structured code over
  comments that restate it.
- **Every change ships with tests.** Use the stdlib `unittest` module only. Guard
  against regressions — keep existing tests passing.
- For new features or design changes, open an issue to discuss the approach
  before implementing.

## Architecture in one minute

pyssg is a small lifecycle-hook kernel (inspired by webpack's Tapable) plus
plugins that tap into phases (`discover -> load -> parse -> collect -> transform
-> render -> generate -> optimize -> emit`). Three layered packages ship in one
wheel:

- `pyssg` — the kernel (stdlib only)
- `pyssg_plugins` — built-in plugins (depend on `pyssg`)
- `pyssg_cli` — the CLI, presets, and scaffolding (depend on the above)

The layering is enforced by `tests/test_package_layers.py`. See the
[README](README.md) and [`docs/`](docs/) for the full picture.

## Pull requests

1. Branch off `dev`.
2. Make your change with tests and passing checks.
3. Open a PR against `dev`; fill in the template checklist.

By contributing, you agree that your contributions are licensed under the
[MIT License](LICENSE).
