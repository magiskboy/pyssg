---
title: Contributing
order: 5
---

# Contributing

Thanks for your interest in improving pyssg. This page is a short orientation;
the authoritative checklist lives in
[`CONTRIBUTING.md`](https://github.com/magiskboy/pyssg/blob/main/CONTRIBUTING.md)
in the repository.

## Development setup

pyssg uses [uv](https://docs.astral.sh/uv/) and targets Python 3.13.

```bash
git clone https://github.com/magiskboy/pyssg.git
cd pyssg
uv sync --all-extras      # runtime extras + dev tools (ruff, mypy, types)
source .venv/bin/activate
```

`--all-extras` pulls every optional dependency (markdown, jinja2, pyyaml,
pygments, watchdog) so the full test suite and type checks run.

## Checks

All four must pass before a pull request is merged; CI runs the same commands on
Linux, macOS and Windows.

```bash
ruff check .              # lint
ruff format --check .     # formatting
mypy                      # strict type checking
python -m unittest discover -s tests
```

## Conventions

- **Python 3.13** with strict typing. `mypy` runs in `strict` mode.
- **English only in code** - identifiers, comments, docstrings, log and error
  strings.
- **Keep the kernel dependency-free.** Third-party dependencies belong in plugins
  under `pyssg_plugins`, declared as optional extras and imported lazily.
- **Prefer simplicity over cleverness.** Favour clear code over comments that
  restate it.
- **Every change ships with tests** using the stdlib `unittest` module. Guard
  against regressions.
- For new features or design changes, open an issue to discuss the approach
  first.

## Pull requests

1. Branch off `dev`.
2. Make your change with tests and passing checks.
3. Open a PR against `dev` and fill in the template checklist.

To understand the codebase before diving in, read the
[Architecture](/architecture/) section - it walks through the kernel, the
lifecycle and the hook system that every plugin builds on.
