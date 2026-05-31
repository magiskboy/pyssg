
# Rules

- Follow Python 3.13 conventions
- Enforce strict Python type checking
- Simple first; favor performance and clean code
- No emoji; write self-explanatory code instead of over-commenting
- In code (comments, docstrings, identifiers, log/error strings) use English only
- When replying to the user, use Vietnamese only

# Architecture

- Three layered packages in one wheel: `pyssg` (kernel) <- `pyssg_plugins` <- `pyssg_cli`; the boundary is enforced by tests
- The `pyssg` kernel uses the standard library only, with no third-party dependencies
- Third-party libraries belong to plugins: declare them as optional extras in pyproject and import them lazily

# Development

- Use uv as the Python package manager
- Always use the virtualenv via: source .venv/bin/activate
- Limit third-party libraries (dev tools such as coverage do not count as runtime dependencies)
- Brainstorm new features / designs before implementing them
- Before pushing, run the same checks as CI: `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy`

# Testing

- Always add unit tests for code you write
- Use only the standard library `unittest` module
- Run tests: `uv run python -m unittest discover -s tests`
- Follow regression testing
- CI measures branch coverage and fails below 85% (the `fail_under` threshold in pyproject)
