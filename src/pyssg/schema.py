"""Frontmatter schema: a small registry of field specs plus a validator.

Frontmatter is open-ended, so a single plugin must not own a fixed schema. Each
plugin instead *declares* the fields it actually reads -- their expected type,
whether they are required, and how to report a problem -- by calling
``builder.schema.declare()`` in its ``apply``. The Frontmatter plugin runs the
validator once during ``parse``, after every plugin has declared, so mistakes
surface early with a ``file:line`` pointer to the frontmatter block.

Validation is *lenient but helpful*: unambiguous values are coerced to a
normalised type (an ISO date string, ``true``/``false`` text to a real bool, a
scalar to a single-item list), while genuinely wrong values raise a friendly
:class:`BuildError`. Unknown keys are never rejected -- templates use arbitrary
keys, so only declared fields are checked.

Kernel module: dependency-free. Coercion of an already-parsed mapping needs no
YAML library, which keeps this testable without the optional ``frontmatter``
extra.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from pyssg.errors import BuildError, SourceLocation, warn
from pyssg.models import Source

FIELD_TYPES = ("str", "int", "bool", "date", "list", "mapping")
SEVERITIES = ("error", "warn")

# Sentinel: "the value is valid as-is, do not write anything back".
_UNCHANGED: object = object()

_TRUE_WORDS = frozenset({"true", "yes", "on", "1"})
_FALSE_WORDS = frozenset({"false", "no", "off", "0"})


@dataclass(frozen=True, slots=True)
class FieldSpec:
    """A declaration of one frontmatter field a plugin reads.

    ``type`` is one of :data:`FIELD_TYPES`. ``coerce`` enables normalising
    compatible values (e.g. a date object to an ISO string). ``severity`` of
    ``"warn"`` reports a problem to stderr instead of failing the build.
    ``example`` is appended to the message to show the intended shape.
    """

    name: str
    type: str = "str"
    required: bool = False
    coerce: bool = True
    severity: str = "error"
    example: str | None = None

    def __post_init__(self) -> None:
        if self.type not in FIELD_TYPES:
            raise ValueError(f"Unknown field type '{self.type}' for '{self.name}'")
        if self.severity not in SEVERITIES:
            raise ValueError(f"Unknown severity '{self.severity}' for '{self.name}'")


class FrontmatterSchema:
    """Registry of :class:`FieldSpec` declarations, keyed by field name."""

    __slots__ = ("_specs",)

    def __init__(self) -> None:
        self._specs: dict[str, FieldSpec] = {}

    def declare(self, spec: FieldSpec) -> None:
        """Register a field spec; the first declaration of a name wins.

        Two plugins declaring the same field with the same type is normal
        (e.g. Collections and Rss both read ``date``). Declaring it with
        conflicting types is a plugin authoring bug and raises immediately.
        """

        existing = self._specs.get(spec.name)
        if existing is None:
            self._specs[spec.name] = spec
            return
        if existing.type != spec.type:
            raise BuildError(
                f"Conflicting frontmatter schema for '{spec.name}': "
                f"declared as both '{existing.type}' and '{spec.type}'.",
                stage="config",
            )

    def specs(self) -> list[FieldSpec]:
        return list(self._specs.values())

    def validate(self, source: Source, *, block_line: int | None = None) -> None:
        """Check (and coerce in place) ``source.frontmatter`` against the specs."""

        frontmatter = source.frontmatter
        for spec in self._specs.values():
            if spec.name not in frontmatter:
                if spec.required:
                    self._report(
                        spec,
                        f"missing required frontmatter '{spec.name}'",
                        source,
                        block_line,
                    )
                continue
            ok, coerced, problem = _check(spec, frontmatter[spec.name])
            if not ok:
                self._report(spec, problem, source, block_line)
            elif coerced is not _UNCHANGED:
                frontmatter[spec.name] = coerced

    def _report(
        self, spec: FieldSpec, message: str, source: Source, block_line: int | None
    ) -> None:
        if spec.example is not None:
            message = f"{message} (example: {spec.example})"
        if spec.severity == "warn":
            warn(f"{source.path}: {message}")
            return
        raise BuildError(
            message, location=SourceLocation(file=source.path, line=block_line)
        )


def _check(spec: FieldSpec, value: object) -> tuple[bool, object, str]:
    """Return ``(ok, coerced_or_UNCHANGED, problem_message)`` for a value."""

    match spec.type:
        case "str":
            return _check_str(spec, value)
        case "int":
            return _check_int(spec, value)
        case "bool":
            return _check_bool(spec, value)
        case "date":
            return _check_date(spec, value)
        case "list":
            return _check_list(spec, value)
        case "mapping":
            if isinstance(value, dict):
                return True, _UNCHANGED, ""
            return False, _UNCHANGED, f"'{spec.name}' must be a mapping of key: value"
    return True, _UNCHANGED, ""


def _check_str(spec: FieldSpec, value: object) -> tuple[bool, object, str]:
    if isinstance(value, str):
        return True, _UNCHANGED, ""
    if (
        spec.coerce
        and isinstance(value, (int, float, date))
        and not isinstance(value, bool)
    ):
        return True, str(value), ""
    return False, _UNCHANGED, f"'{spec.name}' must be text, got {_typename(value)}"


def _check_int(spec: FieldSpec, value: object) -> tuple[bool, object, str]:
    # bool is a subclass of int; a boolean where a number is expected is a mistake.
    if isinstance(value, bool):
        return False, _UNCHANGED, f"'{spec.name}' must be a whole number, got a boolean"
    if isinstance(value, int):
        return True, _UNCHANGED, ""
    if spec.coerce and isinstance(value, str) and _looks_int(value):
        return True, int(value), ""
    if spec.coerce and isinstance(value, float) and value.is_integer():
        return True, int(value), ""
    return (
        False,
        _UNCHANGED,
        f"'{spec.name}' must be a whole number, got {_typename(value)}",
    )


def _check_bool(spec: FieldSpec, value: object) -> tuple[bool, object, str]:
    if isinstance(value, bool):
        return True, _UNCHANGED, ""
    if spec.coerce:
        coerced = _to_bool(value)
        if coerced is not None:
            return True, coerced, ""
    return (
        False,
        _UNCHANGED,
        f"'{spec.name}' must be true or false, got {_typename(value)}",
    )


def _check_date(spec: FieldSpec, value: object) -> tuple[bool, object, str]:
    iso = _to_iso_date(value)
    if iso is None:
        return (
            False,
            _UNCHANGED,
            f"'{spec.name}' must be a date like 2026-01-31, got {value!r}",
        )
    if isinstance(value, str) and value == iso:
        return True, _UNCHANGED, ""
    return True, iso, ""


def _check_list(spec: FieldSpec, value: object) -> tuple[bool, object, str]:
    if isinstance(value, list):
        return True, _UNCHANGED, ""
    # A mapping is never a meaningful single-item list; reject it explicitly.
    if isinstance(value, dict):
        return False, _UNCHANGED, f"'{spec.name}' must be a list, e.g. [a, b]"
    if spec.coerce:
        # Wrap a lone scalar so consumers always see a list; an empty value
        # (``tags:`` with nothing after it) becomes an empty list.
        return True, ([] if value is None else [value]), ""
    return False, _UNCHANGED, f"'{spec.name}' must be a list, e.g. [a, b]"


def _typename(value: object) -> str:
    return type(value).__name__


def _looks_int(text: str) -> bool:
    return text.strip().lstrip("+-").isdigit()


def _to_bool(value: object) -> bool | None:
    if isinstance(value, str):
        word = value.strip().lower()
        if word in _TRUE_WORDS:
            return True
        if word in _FALSE_WORDS:
            return False
    return None


def _to_iso_date(value: object) -> str | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        head = text.replace("T", " ").split(" ", 1)[0]
        try:
            return date.fromisoformat(head).isoformat()
        except ValueError:
            return None
    return None
