# CLAUDE.md - Working conventions for pyssg

**The source of truth is the current code plus this file.** The design spec
(`technical-spec-v0.1.0.md`) is now only **design history** (reference, NOT
binding) - the code has diverged from the spec in several places. When the spec
conflicts with the code/conventions, **follow the code**; do not block on
"spec drift".

## Language & style
- **Code is 100% English** - identifiers, comments, docstrings, log/exception
  messages, test names. No non-English text in the code.
- **No emoji** in code, comments, commit messages, or file names.
- **Standard open-source style:** clear names, just-enough comments (explain
  *why*, not *what*), follow PEP 8 + `ruff`; write it like a public library that
  a stranger will read.
- **Discussion/replies and auxiliary files** (e.g. `TRACK.md`, notes, PR/issue
  descriptions) may use the maintainer's working language. Code stays English.

## Conventions
- **Changing a settled convention => propose, wait for approval, then update this
  file.** The spec is reference only and does not need to be kept in sync.
- **Read the relevant code/conventions before writing.** Do not invent API
  signatures; when unsure, ask.
- **Python 3.13**, `from __future__ import annotations`, full typing on every
  public API. `mypy --strict` (or pyright strict) with **zero errors** is a
  merge condition.
- Follow the existing directory layout in the code; **do not create new
  modules/directory trees** without asking first.
- **Do not add new dependencies** without approval (locked in `uv.lock`).
- **Every change ships with tests.** Only report "done" when the full check
  suite (below) is green.

## Cross-cutting rules (apply to all code, not tied to any feature)
- `pyssg/core/` is **stdlib only** - no third-party imports (those live at the
  periphery).
- Every processing unit is **pure** with respect to its declared inputs: no
  global mutable state, no direct `datetime.now()`/`time`/`random`. Building
  twice must be byte-identical.
- Incremental results **must be byte-identical to a full rebuild** - never break
  this test.
- **Plugins declare facts only; the engine owns the algorithms** - plugins do not
  propagate dirtiness or manage the cache themselves.
- **Presets (`pyssg/presets/`) are pure factories returning a `Config`** - they
  only declare a plugin list + theme, they do not own algorithms.
- **Community plugins (`pyssg/contrib/<name>.py`)**: third-party imports are OK
  (periphery, not part of `core`) but MUST ship tests + `mypy --strict` zero
  errors + be pure. Not auto re-exported into `pyssg.plugins`.
- **Built-in themes live in `pyssg/themes/<name>/`**; `Config.layout` accepts a
  `str` (relative to the site) or an absolute `Path` (theme).

## Environment & package management
- **`uv` is the project's sole Python + package manager.** Do not use
  `pip`/`pipenv`/`poetry` directly; add dependencies via `uv add` (runtime) /
  `uv add --dev` (dev), locked in `uv.lock`.
- **Always use the project virtualenv at `.venv`** (Python 3.13). Run every
  command through `uv run ...` (which uses `.venv`); never call the system
  Python.

## Process (semi-supervised)
- Work **by milestone**: implement + test -> run checks -> **STOP, summarize,
  wait for approval**.
- **Do not skip** milestones; **do not** bundle one giant PR - split into small
  parts, each with tests.

## Check commands (before reporting "done")
```bash
uv run mypy --strict pyssg
uv run ruff check pyssg
uv run python -m unittest discover -s tests -t .   # full test suite (stdlib unittest), including the invariant tests (boundary, incremental==full, determinism)
```

## End-of-task checklist
- [ ] Adheres to the settled conventions (this file + code); no new
      unapproved conventions introduced.
- [ ] The cross-cutting rules above still hold.
- [ ] New/sufficient tests exist; `mypy --strict` zero errors; the full check
      suite is green.
- [ ] Summarize the changes against the milestone acceptance criteria, then
      **STOP and wait for approval**.
