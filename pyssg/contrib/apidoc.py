"""Contrib plugin: API reference from Python docstrings.

Extracts docstrings from a Python package *statically* (via :mod:`ast`, so the
user's code is never imported or executed) and turns each module into a virtual
Markdown document under a ``/references/`` route. The synthetic Markdown is fed
through the normal pipeline (markdown -> permalink -> nav -> render), so the
output is ordinary HTML and the modules automatically form a "References"
section in the sidebar (the nav plugin groups pages by their first URL segment).

It never touches the user's source Markdown: the generated documents live only
in the build graph (``meta["__raw__"]``); nothing is written back to ``content``.

Docstrings written in Google, NumPy or reStructuredText style are parsed into
structured parameter/return/raises tables; any other prose is kept verbatim.
Tables are emitted as raw HTML because the engine renders Markdown with the
CommonMark preset, which has no GFM table syntax (raw HTML passes through).

Purity / incremental notes:

- Extraction is a pure function of the ``.py`` files on disk: modules and
  members are emitted in source order, nothing reads the clock or environment,
  so two builds are byte-identical and an incremental rebuild equals a full one.
- The virtual documents are created during ``make`` (once per session). A full
  build -- and every ``serve`` startup -- reflects the current ``.py`` files.
  Live hot-reload when a ``.py`` file changes mid-``serve`` is intentionally out
  of scope for now (it would require the engine to watch and seed non-Markdown
  source files); restart ``serve`` or run ``build`` to pick up code changes.

Third-party imports are allowed here (this is periphery, not ``pyssg.core``),
but this plugin needs none: it is pure standard library.
"""

from __future__ import annotations

import ast
import html
import re
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from pyssg.core.node import Document
from pyssg.core.types import NodeKind

if TYPE_CHECKING:
    from pyssg.core.build import Build
    from pyssg.core.builder import Builder

__all__ = ["ApiDocPlugin", "Param", "ParsedDocstring", "apidoc", "extract_package"]


# --------------------------------------------------------------------------- #
# Structured docstring model + parsing
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class Param:
    """One named field of a docstring (a parameter, a return, or a raise).

    ``name`` is the parameter / exception name (empty for an anonymous return),
    ``type`` the declared type (may be empty), ``description`` the free text.
    """

    name: str
    type: str
    description: str


@dataclass(frozen=True, slots=True)
class ParsedDocstring:
    """A docstring split into a summary, typed fields, and verbatim sections."""

    summary: str
    params: tuple[Param, ...]
    returns: tuple[Param, ...]
    raises: tuple[Param, ...]
    sections: tuple[tuple[str, str], ...]


_EMPTY = ParsedDocstring("", (), (), (), ())

# Style detection. reST field lists win first (most unambiguous), then a NumPy
# "Header\n------" underline, then a Google "Header:" line.
_REST_FIELD = re.compile(
    r"^\s*:(param|parameter|arg|argument|key|keyword|type|returns?|rtype|raises?|except"
    r"|exception)\b",
    re.IGNORECASE | re.MULTILINE,
)
_NUMPY_HEADER = re.compile(r"^[ \t]*[A-Za-z][A-Za-z ]*\n[ \t]*-{3,}[ \t]*$", re.MULTILINE)
_GOOGLE_HEADER = re.compile(
    r"^(Args|Arguments|Parameters|Returns?|Yields?|Raises|Attributes|Notes?|Examples?"
    r"|Warnings?|See Also|References)\s*:\s*$",
    re.IGNORECASE | re.MULTILINE,
)


def _canon(name: str) -> str:
    """Canonical bucket for a section title: params / returns / raises / other."""
    norm = name.strip().lower().rstrip(":")
    if norm in {"args", "arguments", "parameters", "keyword args", "keyword arguments"}:
        return "params"
    if norm in {"returns", "return", "yields", "yield"}:
        return "returns"
    if norm in {"raises", "raise", "except", "exceptions"}:
        return "raises"
    return "other"


def parse_docstring(text: str) -> ParsedDocstring:
    """Parse a (cleaned) docstring into a :class:`ParsedDocstring`.

    The style is auto-detected; an unrecognised docstring becomes an all-summary
    result so nothing is ever dropped.
    """
    text = text.strip("\n")
    if not text.strip():
        return _EMPTY
    if _REST_FIELD.search(text):
        return _parse_rest(text)
    if _NUMPY_HEADER.search(text):
        return _parse_numpy(text)
    if _GOOGLE_HEADER.search(text):
        return _parse_google(text)
    return ParsedDocstring(text.strip(), (), (), (), ())


# -- Google ----------------------------------------------------------------- #

_GOOGLE_SECTION = re.compile(r"^([A-Za-z][A-Za-z ]*):\s*$")
_GOOGLE_PARAM = re.compile(
    r"^(?P<name>\*{0,2}[A-Za-z_]\w*)\s*(?:\((?P<type>[^)]*)\))?\s*:\s*(?P<desc>.*)$"
)


def _parse_google(text: str) -> ParsedDocstring:
    lines = text.split("\n")
    summary: list[str] = []
    groups: list[tuple[str, list[str]]] = []
    current: list[str] | None = None
    for line in lines:
        match = _GOOGLE_SECTION.match(line)
        if match and not line[:1].isspace():
            current = []
            groups.append((match.group(1), current))
        elif current is not None:
            current.append(line)
        else:
            summary.append(line)

    params: tuple[Param, ...] = ()
    returns: tuple[Param, ...] = ()
    raises: tuple[Param, ...] = ()
    sections: list[tuple[str, str]] = []
    for title, body in groups:
        bucket = _canon(title)
        if bucket == "params":
            params = _google_params(body)
        elif bucket == "returns":
            returns = _parse_returns(body)
        elif bucket == "raises":
            raises = _google_raises(body)
        else:
            sections.append((title.strip(), textwrap.dedent("\n".join(body)).strip()))
    return ParsedDocstring("\n".join(summary).strip(), params, returns, raises, tuple(sections))


def _google_params(body: list[str]) -> tuple[Param, ...]:
    text = textwrap.dedent("\n".join(body))
    items: list[list[str]] = []
    descs: list[list[str]] = []
    for line in text.split("\n"):
        if not line.strip():
            continue
        match = _GOOGLE_PARAM.match(line)
        if match and not line[0].isspace():
            items.append([match.group("name"), match.group("type") or ""])
            descs.append([match.group("desc").strip()])
        elif items:
            descs[-1].append(line.strip())
    return tuple(
        Param(item[0], item[1], " ".join(p for p in desc if p).strip())
        for item, desc in zip(items, descs, strict=True)
    )


def _google_raises(body: list[str]) -> tuple[Param, ...]:
    text = textwrap.dedent("\n".join(body))
    names: list[str] = []
    descs: list[list[str]] = []
    for line in text.split("\n"):
        if not line.strip():
            continue
        match = re.match(r"^(?P<name>[\w.]+)\s*:\s*(?P<desc>.*)$", line)
        if match and not line[0].isspace():
            names.append(match.group("name"))
            descs.append([match.group("desc").strip()])
        elif names:
            descs[-1].append(line.strip())
    return tuple(
        Param(name, "", " ".join(p for p in desc if p).strip())
        for name, desc in zip(names, descs, strict=True)
    )


def _parse_returns(body: list[str]) -> tuple[Param, ...]:
    """Parse a Returns/Yields block: an optional ``type:`` lead, then prose."""
    text = textwrap.dedent("\n".join(body)).strip()
    if not text:
        return ()
    rows = [line.strip() for line in text.split("\n") if line.strip()]
    match = re.match(r"^(?P<type>[A-Za-z_][\w\[\], .|]*):\s*(?P<desc>.+)$", rows[0])
    if match:
        type_ = match.group("type")
        desc = [match.group("desc")]
    else:
        type_ = ""
        desc = [rows[0]]
    desc.extend(rows[1:])
    return (Param("", type_, " ".join(desc).strip()),)


# -- NumPy ------------------------------------------------------------------- #


def _parse_numpy(text: str) -> ParsedDocstring:
    lines = text.split("\n")
    heads: list[int] = [
        i
        for i in range(len(lines) - 1)
        if re.match(r"^[A-Za-z][A-Za-z ]*$", lines[i].strip())
        and re.match(r"^-{3,}$", lines[i + 1].strip())
    ]
    summary = "\n".join(lines[: heads[0]]).strip() if heads else text.strip()

    params: tuple[Param, ...] = ()
    returns: tuple[Param, ...] = ()
    raises: tuple[Param, ...] = ()
    sections: list[tuple[str, str]] = []
    for idx, start in enumerate(heads):
        title = lines[start].strip()
        end = heads[idx + 1] if idx + 1 < len(heads) else len(lines)
        body = lines[start + 2 : end]
        bucket = _canon(title)
        if bucket == "params":
            params = _numpy_fields(body, has_names=True)
        elif bucket == "returns":
            returns = _numpy_fields(body, has_names=False)
        elif bucket == "raises":
            raises = _numpy_fields(body, has_names=False)
        else:
            sections.append((title, textwrap.dedent("\n".join(body)).strip()))
    return ParsedDocstring(summary, params, returns, raises, tuple(sections))


def _numpy_entries(body: list[str]) -> list[tuple[str, str]]:
    """Split a NumPy section body into ``(headline, description)`` pairs."""
    text = textwrap.dedent("\n".join(body))
    heads: list[str] = []
    descs: list[list[str]] = []
    for line in text.split("\n"):
        if not line.strip():
            continue
        if not line[0].isspace():
            heads.append(line.strip())
            descs.append([])
        elif heads:
            descs[-1].append(line.strip())
    return [(head, " ".join(desc).strip()) for head, desc in zip(heads, descs, strict=True)]


def _numpy_fields(body: list[str], *, has_names: bool) -> tuple[Param, ...]:
    result: list[Param] = []
    for head, desc in _numpy_entries(body):
        name, _, type_part = head.partition(":")
        if has_names:
            result.append(Param(name.strip(), type_part.strip(), desc))
        elif type_part.strip():  # "name : type" form for an anonymous return
            result.append(Param("", type_part.strip(), desc))
        else:  # bare "type" headline
            result.append(Param("", name.strip(), desc))
    return tuple(result)


# -- reStructuredText -------------------------------------------------------- #

_REST_LINE = re.compile(r"^:(?P<key>\w+(?:\s+[^:]+)?):\s?(?P<rest>.*)$")


def _parse_rest(text: str) -> ParsedDocstring:
    summary: list[str] = []
    fields: list[tuple[str, list[str]]] = []
    seen_field = False
    for line in text.split("\n"):
        match = _REST_LINE.match(line)
        if match:
            seen_field = True
            fields.append((match.group("key"), [match.group("rest")]))
        elif seen_field and line[:1].isspace() and line.strip():
            fields[-1][1].append(line.strip())
        elif not seen_field:
            summary.append(line)

    param_order: list[str] = []
    param_desc: dict[str, str] = {}
    param_type: dict[str, str] = {}
    returns_desc = ""
    rtype = ""
    raises: list[Param] = []
    for key, body_lines in fields:
        tokens = key.split()
        kind = tokens[0].lower()
        body = " ".join(part for part in body_lines if part).strip()
        if kind in {"param", "parameter", "arg", "argument", "key", "keyword"}:
            name = tokens[-1]
            if name not in param_desc:
                param_order.append(name)
            param_desc[name] = body
        elif kind == "type":
            param_type[tokens[-1]] = body
        elif kind in {"returns", "return"}:
            returns_desc = body
        elif kind == "rtype":
            rtype = body
        elif kind in {"raises", "raise", "except", "exception"}:
            raises.append(Param(tokens[1] if len(tokens) > 1 else "", "", body))

    params = tuple(Param(n, param_type.get(n, ""), param_desc.get(n, "")) for n in param_order)
    returns = (Param("", rtype, returns_desc),) if (returns_desc or rtype) else ()
    return ParsedDocstring("\n".join(summary).strip(), params, returns, tuple(raises), ())


# --------------------------------------------------------------------------- #
# Rendering a parsed docstring to Markdown (with raw-HTML tables)
# --------------------------------------------------------------------------- #


def _text(value: str) -> str:
    """Escape and collapse whitespace so a value is safe inside a table cell."""
    return html.escape(" ".join(value.split()))


def _code(value: str) -> str:
    return f"<code>{html.escape(value.strip())}</code>" if value.strip() else ""


def _table(headers: tuple[str, ...], rows: list[tuple[str, ...]]) -> str:
    """A single-block HTML table; cells are already-rendered HTML fragments.

    Emitted with no internal blank lines so the CommonMark renderer treats the
    whole thing as one raw-HTML block and passes it through untouched.
    """
    head = "".join(f"<th>{html.escape(h)}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>" for row in rows)
    return f"<table>\n<thead><tr>{head}</tr></thead>\n<tbody>{body}</tbody>\n</table>"


def render_docstring_markdown(doc: ParsedDocstring) -> str:
    """Render a parsed docstring back to Markdown (summary + HTML tables)."""
    blocks: list[str] = []
    if doc.summary.strip():
        blocks.append(doc.summary.strip())
    if doc.params:
        blocks.append("**Parameters**")
        blocks.append(
            _table(
                ("Name", "Type", "Description"),
                [(_code(p.name), _code(p.type), _text(p.description)) for p in doc.params],
            )
        )
    if doc.returns:
        blocks.append("**Returns**")
        blocks.append(
            _table(
                ("Type", "Description"),
                [(_code(p.type), _text(p.description)) for p in doc.returns],
            )
        )
    if doc.raises:
        blocks.append("**Raises**")
        blocks.append(
            _table(
                ("Type", "Description"),
                [(_code(p.name), _text(p.description)) for p in doc.raises],
            )
        )
    for title, body in doc.sections:
        blocks.append(f"**{title}**")
        if body.strip():
            blocks.append(body.strip())
    return "\n\n".join(blocks)


# --------------------------------------------------------------------------- #
# Static extraction of a package's modules into Markdown
# --------------------------------------------------------------------------- #

type _FuncDef = ast.FunctionDef | ast.AsyncFunctionDef


def _visible(name: str, *, include_private: bool, include_dunder: bool) -> bool:
    """Membership rule: ``__init__`` always shown; flags gate the rest."""
    if name == "__init__":
        return True
    if name.startswith("__") and name.endswith("__"):
        return include_dunder
    if name.startswith("_"):
        return include_private
    return True


def _annotation(arg: ast.arg) -> str:
    return f": {ast.unparse(arg.annotation)}" if arg.annotation is not None else ""


def _format_signature(node: _FuncDef) -> str:
    """Render a function's parameter list and return annotation from its AST."""
    args = node.args
    positional = args.posonlyargs + args.args
    offset = len(positional) - len(args.defaults)
    parts: list[str] = []
    for i, arg in enumerate(positional):
        rendered = arg.arg + _annotation(arg)
        default_index = i - offset
        if default_index >= 0:
            sep = " = " if arg.annotation is not None else "="
            rendered += f"{sep}{ast.unparse(args.defaults[default_index])}"
        parts.append(rendered)
        if args.posonlyargs and i == len(args.posonlyargs) - 1:
            parts.append("/")
    if args.vararg is not None:
        parts.append("*" + args.vararg.arg + _annotation(args.vararg))
    elif args.kwonlyargs:
        parts.append("*")
    for arg, default in zip(args.kwonlyargs, args.kw_defaults, strict=True):
        rendered = arg.arg + _annotation(arg)
        if default is not None:
            sep = " = " if arg.annotation is not None else "="
            rendered += f"{sep}{ast.unparse(default)}"
        parts.append(rendered)
    if args.kwarg is not None:
        parts.append("**" + args.kwarg.arg + _annotation(args.kwarg))
    returns = f" -> {ast.unparse(node.returns)}" if node.returns is not None else ""
    return f"({', '.join(parts)}){returns}"


def _func_header(node: _FuncDef, qualifier: str = "") -> str:
    prefix = "async " if isinstance(node, ast.AsyncFunctionDef) else ""
    return f"{prefix}{qualifier}{node.name}{_format_signature(node)}"


def _class_header(node: ast.ClassDef) -> str:
    bases = [ast.unparse(base) for base in node.bases]
    bases += [f"{kw.arg}={ast.unparse(kw.value)}" for kw in node.keywords if kw.arg]
    suffix = f"({', '.join(bases)})" if bases else ""
    return f"class {node.name}{suffix}"


def _rendered_docstring(node: ast.Module | ast.ClassDef | _FuncDef) -> str | None:
    raw = ast.get_docstring(node, clean=True)
    if raw is None:
        return None
    return render_docstring_markdown(parse_docstring(raw))


def module_markdown(
    dotted: str, tree: ast.Module, *, include_private: bool, include_dunder: bool
) -> str:
    """Render one module's docstrings to a Markdown document (source order)."""

    def visible(name: str) -> bool:
        return _visible(name, include_private=include_private, include_dunder=include_dunder)

    blocks: list[str] = [f"# `{dotted}`"]
    module_doc = _rendered_docstring(tree)
    if module_doc:
        blocks.append(module_doc)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            if not visible(node.name):
                continue
            blocks.append(f"## `{_func_header(node)}`")
            body = _rendered_docstring(node)
            if body:
                blocks.append(body)
        elif isinstance(node, ast.ClassDef):
            if not visible(node.name):
                continue
            blocks.append(f"## `{_class_header(node)}`")
            body = _rendered_docstring(node)
            if body:
                blocks.append(body)
            for member in node.body:
                if not isinstance(member, ast.FunctionDef | ast.AsyncFunctionDef):
                    continue
                if not visible(member.name):
                    continue
                blocks.append(f"### `{_func_header(member, qualifier=node.name + '.')}`")
                member_body = _rendered_docstring(member)
                if member_body:
                    blocks.append(member_body)
    return "\n\n".join(block for block in blocks if block) + "\n"


def _dotted_name(package: str, rel: Path) -> str:
    parts = list(rel.with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts.pop()
    return ".".join([package, *parts]) if parts else package


def _module_visible(dotted: str, *, include_private: bool) -> bool:
    last = dotted.rsplit(".", 1)[-1]
    return not (last.startswith("_") and not include_private)


def extract_package(
    root: Path, *, include_private: bool = False, include_dunder: bool = False
) -> list[tuple[str, str]]:
    """Extract ``(dotted_name, markdown)`` for every module under ``root``.

    ``root`` may be a package directory or a single ``.py`` file. Results are
    sorted by dotted name (deterministic). Files that fail to parse are skipped.
    """
    if root.is_file():
        files = [root]
        package = root.stem
        base = root.parent
    elif root.is_dir():
        files = sorted(root.rglob("*.py"))
        package = root.name
        base = root
    else:
        return []

    results: list[tuple[str, str]] = []
    for path in files:
        rel = path.relative_to(base) if root.is_dir() else Path(path.name)
        dotted = _dotted_name(package, rel) if root.is_dir() else package
        if not _module_visible(dotted, include_private=include_private):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        markdown = module_markdown(
            dotted, tree, include_private=include_private, include_dunder=include_dunder
        )
        results.append((dotted, markdown))
    results.sort(key=lambda item: item[0])
    return results


# --------------------------------------------------------------------------- #
# Plugin
# --------------------------------------------------------------------------- #


class ApiDocPlugin:
    """Generates a References section from a package's docstrings."""

    name = "apidoc"
    cache_version = "1.0.0"

    def __init__(
        self,
        *,
        package: str | Path,
        route: str = "/references/",
        include_private: bool = False,
        include_dunder: bool = False,
    ) -> None:
        self._package = package
        # Normalise the route to a leading+trailing-slash URL prefix.
        self._route = "/" + route.strip("/") + "/" if route.strip("/") else "/"
        self._include_private = include_private
        self._include_dunder = include_dunder

    def apply(self, builder: Builder) -> None:
        @builder.hooks.make.tap(self.name)
        async def _make(build: Build) -> None:
            self._inject(build)

    def _root(self, build: Build) -> Path | None:
        package = Path(self._package)
        root = package if package.is_absolute() else build.builder.site_dir / package
        return root if root.exists() else None

    def _inject(self, build: Build) -> None:
        root = self._root(build)
        if root is None:
            return
        prefix = self._route.strip("/")
        for dotted, markdown in extract_package(
            root, include_private=self._include_private, include_dunder=self._include_dunder
        ):
            path = dotted.replace(".", "/")
            node = Document(
                id=f"apidoc:{dotted}",
                kind=NodeKind.MARKDOWN,
                source_path=f"{prefix}/{path}.md",
            )
            node.meta["__raw__"] = markdown
            node.meta["permalink"] = f"{self._route}{path}/"
            build.graph.add_node(node)


def apidoc(
    *,
    package: str | Path,
    route: str = "/references/",
    include_private: bool = False,
    include_dunder: bool = False,
) -> ApiDocPlugin:
    """Factory used in ``pyssg.config.py``.

    Args:
        package: Path to the package directory (or a single module file),
            relative to the site root or absolute.
        route: URL prefix for the generated reference pages.
        include_private: Include ``_name`` members and modules.
        include_dunder: Include ``__dunder__`` members (``__init__`` is always
            shown regardless).
    """
    return ApiDocPlugin(
        package=package,
        route=route,
        include_private=include_private,
        include_dunder=include_dunder,
    )
