"""Template plugin: wrap rendered content in a layout and emit an Output.

Taps ``render``. Uses jinja2, imported lazily so the dependency is only needed
when the plugin is used. Install with ``pip install pyssg[template]``.

Inheritance and includes use Jinja2 natively -- a layout may ``{% extends
"base.html" %}`` and ``{% include "partials/x.html" %}`` with no extra support.

On top of that this plugin adds two Hugo-inspired conveniences:

1. A template *lookup cascade*. Instead of every page declaring ``layout``, the
   template is resolved by trying, in order:

       <frontmatter layout>           (explicit override, highest priority)
       <type>/<kind>.html             e.g. blog/single.html
       <section>/<kind>.html          e.g. <top folder>/list.html
       _default/<kind>.html           e.g. _default/list.html
       <kind>.html                    e.g. list.html
       <default_layout>               final fallback

   ``kind`` is ``list`` for generated listing pages and ``single`` otherwise.
   ``type`` comes from frontmatter ``type``; ``section`` from the top folder of
   the source path.

2. A ``partial(name, context=None)`` global, like Hugo's ``partial``. It renders
   a snippet with an explicit context (auto-merged with ``site``/``menus``/
   ``collections``) and returns safe markup.

Templates receive:

- ``content``: the rendered HTML body
- ``page``: the source frontmatter merged with ``meta``
- every key of ``build.meta`` as a top-level variable (``site``,
  ``collections``, ``menus``); ``site`` falls back to the config options
- ``partial``: the partial render function
- any callable registered in ``build.meta["template_globals"]`` by another
  plugin (e.g. ``seo`` from the Seo plugin)

The output path mirrors the source path with the suffix replaced by ``.html``,
unless a plugin already set ``source.meta["output_path"]`` (e.g. a permalink
plugin), which lets source and target diverge.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from pyssg.build import Build
from pyssg.builder import Builder
from pyssg.content import GENERATED
from pyssg.errors import BuildError, SourceLocation
from pyssg.models import Output, Source

if TYPE_CHECKING:
    from jinja2 import Environment
    from markupsafe import Markup


class Template:
    def __init__(
        self,
        directory: str = "layouts",
        *,
        default_layout: str = "default.html",
        partials_dir: str = "partials",
    ) -> None:
        self._directory = directory
        self._default_layout = default_layout
        self._partials_dir = partials_dir
        self._env: Environment | None = None

    def apply(self, builder: Builder) -> None:
        builder.hooks.render.tap("Template", self._render)

    def _environment(self, build: Build) -> Environment:
        if self._env is None:
            from jinja2 import Environment, FileSystemLoader, select_autoescape

            directory = build.config.src.parent / self._directory
            env = Environment(
                loader=FileSystemLoader(str(directory)),
                autoescape=select_autoescape(["html", "xml"]),
            )
            env.globals["partial"] = self._make_partial(env, build)
            # Other plugins (e.g. Seo) contribute globals through this shared
            # seam so they need no reference to this plugin's environment.
            extra_globals = build.meta.get("template_globals")
            if isinstance(extra_globals, dict):
                for name, fn in extra_globals.items():
                    env.globals[str(name)] = fn
            self._env = env
        return self._env

    def _make_partial(
        self, env: Environment, build: Build
    ) -> Callable[[str, dict[str, object] | None], Markup]:
        from markupsafe import Markup

        def partial(name: str, context: dict[str, object] | None = None) -> Markup:
            merged: dict[str, object] = {"site": dict(build.config.options)}
            merged.update(build.meta)
            if context:
                merged.update(context)
            template = env.get_template(_with_suffix(name))
            return Markup(template.render(**merged))

        return partial

    def _render(self, source: Source, build: Build) -> None:
        from markupsafe import Markup

        # Every key of build.meta becomes a top-level template variable, so
        # tier-2 data is addressed naturally: `site`, `collections`, `menus`.
        # `site` falls back to the config options when no plugin populated it.
        context: dict[str, object] = {"site": dict(build.config.options)}
        context.update(build.meta)

        # The rendered content is trusted HTML (produced by the Markdown
        # plugin), so mark it safe; autoescape still protects frontmatter
        # values interpolated elsewhere in the layout.
        context["page"] = {**source.frontmatter, **source.meta}
        context["content"] = Markup(source.content)

        try:
            env = self._environment(build)
            template = env.select_template(self._candidates(source))
            html = template.render(**context)
        except Exception as error:
            raise self._template_error(error, build) from error

        build.outputs.append(
            Output(path=self._output_path(source), content=html, source=source)
        )

    def _template_error(self, error: Exception, build: Build) -> BuildError:
        """Translate a Jinja2 exception into a located BuildError."""

        from jinja2 import TemplateNotFound, TemplateSyntaxError

        layouts = (build.config.src.parent / self._directory).resolve()

        if isinstance(error, TemplateSyntaxError):
            file = (
                Path(error.filename) if error.filename else layouts / (error.name or "")
            )
            return BuildError(
                f"Template syntax error: {error.message}",
                location=SourceLocation(file=file, line=error.lineno),
            )
        if isinstance(error, TemplateNotFound):
            return BuildError(
                f"Template not found: {error.name}",
                location=SourceLocation(file=layouts),
            )

        # Runtime errors (UndefinedError, etc.): Jinja rewrites the traceback so
        # frames point at the offending template file and line.
        location = _template_frame(error, layouts)
        return BuildError(
            f"Template render error: {type(error).__name__}: {error}",
            location=location,
        )

    def _candidates(self, source: Source) -> list[str]:
        """Ordered list of template names to try for this page."""

        names: list[str] = []

        explicit = source.frontmatter.get("layout")
        if isinstance(explicit, str) and explicit:
            names.append(_with_suffix(explicit))

        kind = "list" if source.meta.get(GENERATED) else "single"
        page_type = source.frontmatter.get("type")
        section = _section(source)

        if isinstance(page_type, str) and page_type:
            names.append(f"{page_type}/{kind}.html")
        if section:
            names.append(f"{section}/{kind}.html")
        names.append(f"_default/{kind}.html")
        names.append(f"{kind}.html")
        names.append(self._default_layout)

        # Deduplicate while preserving order.
        return list(dict.fromkeys(names))

    def _output_path(self, source: Source) -> Path:
        explicit = source.meta.get("output_path")
        if isinstance(explicit, str):
            return Path(explicit)
        if isinstance(explicit, Path):
            return explicit
        return source.relpath.with_suffix(".html")


def _template_frame(error: Exception, layouts: Path) -> SourceLocation | None:
    """Find the deepest traceback frame inside the layouts directory."""

    found: SourceLocation | None = None
    tb = error.__traceback__
    while tb is not None:
        try:
            path = Path(tb.tb_frame.f_code.co_filename).resolve()
        except (OSError, ValueError):
            path = None
        if path is not None and (path == layouts or layouts in path.parents):
            found = SourceLocation(file=path, line=tb.tb_lineno)
        tb = tb.tb_next
    return found


def _with_suffix(name: str) -> str:
    return name if name.endswith((".html", ".xml", ".txt", ".j2")) else f"{name}.html"


def _section(source: Source) -> str:
    parts = source.relpath.parts
    if len(parts) > 1:
        return parts[0]
    return ""
