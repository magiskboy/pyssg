"""Frontmatter plugin: split a leading ``---`` block and parse it as YAML.

Taps ``parse``. The frontmatter block is parsed with PyYAML (``yaml.safe_load``)
so the full YAML spec is supported and parse errors carry a precise line/column
mark. Install with ``pip install pyssg[frontmatter]``.

On a YAML error the plugin raises a :class:`BuildError` pointing at the exact
``file:line:column`` inside the source file, which the CLI prints cleanly and
the dev server renders as an overlay.
"""

from __future__ import annotations

from pyssg.build import Build
from pyssg.builder import Builder
from pyssg.errors import BuildError, SourceLocation
from pyssg.models import Source
from pyssg.schema import FrontmatterSchema

_DELIMITER = "---"
# The frontmatter block always starts on the line after the opening delimiter
# (file line 1), so a 0-based mark line inside the block maps to file line +2.
_BLOCK_LINE_OFFSET = 2


class Frontmatter:
    def __init__(self) -> None:
        # Replaced with the builder's shared schema in apply(); a private empty
        # one keeps _parse usable in isolation (and tests) before apply runs.
        self._schema = FrontmatterSchema()

    def apply(self, builder: Builder) -> None:
        self._schema = builder.schema
        builder.hooks.parse.tap("Frontmatter", self._parse)

    def _parse(self, source: Source, build: Build) -> None:
        front, body = _split(source.raw)
        source.body = body
        if front is not None:
            source.frontmatter = _parse_yaml(front, source)
        self._schema.validate(source, block_line=_BLOCK_LINE_OFFSET)


def _parse_yaml(text: str, source: Source) -> dict[str, object]:
    import yaml

    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as error:
        raise _yaml_error(error, source) from error

    if data is None:
        return {}
    if not isinstance(data, dict):
        raise BuildError(
            f"Frontmatter must be a mapping of key: value, got {type(data).__name__}",
            location=SourceLocation(file=source.path, line=_BLOCK_LINE_OFFSET),
        )
    return {str(key): value for key, value in data.items()}


def _yaml_error(error: Exception, source: Source) -> BuildError:
    import yaml

    line: int | None = None
    column: int | None = None
    problem = getattr(error, "problem", None)
    message = str(problem) if problem else "invalid YAML frontmatter"
    if isinstance(error, yaml.MarkedYAMLError) and error.problem_mark is not None:
        mark = error.problem_mark
        line = mark.line + _BLOCK_LINE_OFFSET
        column = mark.column + 1
    return BuildError(
        f"Frontmatter YAML error: {message}",
        location=SourceLocation(file=source.path, line=line, column=column),
    )


def _split(raw: str) -> tuple[str | None, str]:
    """Return ``(frontmatter_text, body)``; frontmatter is ``None`` if absent."""

    if not raw.startswith(_DELIMITER):
        return None, raw

    lines = raw.splitlines()
    # First line must be exactly the delimiter.
    if lines[0].strip() != _DELIMITER:
        return None, raw

    for index in range(1, len(lines)):
        if lines[index].strip() == _DELIMITER:
            front = "\n".join(lines[1:index])
            body = "\n".join(lines[index + 1 :])
            return front, body.lstrip("\n")

    # Opening delimiter without a closing one: treat as no frontmatter.
    return None, raw
