"""Builder: the lifecycle orchestrator (equivalent to webpack's ``Compiler``).

The builder owns every hook, applies the plugins from the config, then runs the
build lifecycle once. The builder itself knows nothing about markdown/HTML; all
real work is done by plugins through the hooks below.

The lifecycle uses phased passes: each pass sweeps the whole set of sources
before the next begins (like webpack building all modules before sealing). This
is what lets plugins see the entire site -- needed for navigation, collections
and derived pages (n-to-m), which a per-source loop cannot express.

Lifecycle:

    initialize                      (after every plugin is applied)
    before_run
      discover                      (collect Sources into the build)
      load       (each source)      (read raw content)
      parse      (each source)      (split frontmatter / body)
      collect    (whole build)      (build site-wide context into build.meta)
      transform  (each source)      (body -> content) [waterfall]
      render     (each source)      (emit Output; sees the whole site)
      generate   (whole build)      (derived pages: tag index, pagination, rss)
      optimize   (whole build)      (optimize/minify; use stage to order taps)
      emit       (whole build)      (write to disk)
      after_emit (whole build)      (sitemap, graph, report...)
    done | failed
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from pyssg.build import Build
from pyssg.config import Config, validate_config
from pyssg.errors import BuildError, warn, wrap
from pyssg.hooks import SyncHook, SyncWaterfallHook
from pyssg.models import Source
from pyssg.schema import FrontmatterSchema


class BuilderHooks:
    """A builder's set of hooks. Plugins tap these inside their ``apply``."""

    __slots__ = (
        "initialize",
        "before_run",
        "discover",
        "load",
        "parse",
        "collect",
        "transform",
        "render",
        "generate",
        "optimize",
        "emit",
        "after_emit",
        "done",
        "failed",
    )

    def __init__(self) -> None:
        self.initialize: SyncHook[Builder] = SyncHook()
        self.before_run: SyncHook[Build] = SyncHook()
        self.discover: SyncHook[Build] = SyncHook()
        self.load: SyncHook[Source, Build] = SyncHook()
        self.parse: SyncHook[Source, Build] = SyncHook()
        self.collect: SyncHook[Build] = SyncHook()
        self.transform: SyncWaterfallHook[Source, Build] = SyncWaterfallHook()
        self.render: SyncHook[Source, Build] = SyncHook()
        self.generate: SyncHook[Build] = SyncHook()
        self.optimize: SyncHook[Build] = SyncHook()
        self.emit: SyncHook[Build] = SyncHook()
        self.after_emit: SyncHook[Build] = SyncHook()
        self.done: SyncHook[Build] = SyncHook()
        self.failed: SyncHook[Exception, Build] = SyncHook()


class Builder:
    __slots__ = ("config", "hooks", "schema")

    def __init__(self, config: Config) -> None:
        self.config = config
        self.hooks = BuilderHooks()
        self.schema = FrontmatterSchema()
        for plugin in config.plugins:
            plugin.apply(self)
        self.hooks.initialize.call(self)

    def run(self) -> Build:
        build = Build(config=self.config)
        try:
            validate_config(self.config)
            if not self.hooks.emit.has_taps:
                warn(
                    "No plugin taps the 'emit' hook, so the build will not write "
                    "any files. Add a WriteFile plugin or use a preset."
                )
            with _stage("before_run"):
                self.hooks.before_run.call(build)
            with _stage("discover"):
                self.hooks.discover.call(build)
            for source in build.sources:
                with _stage("load", source):
                    self.hooks.load.call(source, build)
            for source in build.sources:
                with _stage("parse", source):
                    self.hooks.parse.call(source, build)
            with _stage("collect"):
                self.hooks.collect.call(build)
            for index, source in enumerate(build.sources):
                with _stage("transform", source):
                    build.sources[index] = self.hooks.transform.call(source, build)
            for source in build.sources:
                with _stage("render", source):
                    self.hooks.render.call(source, build)
            with _stage("generate"):
                self.hooks.generate.call(build)
            with _stage("optimize"):
                self.hooks.optimize.call(build)
            with _stage("emit"):
                self.hooks.emit.call(build)
            with _stage("after_emit"):
                self.hooks.after_emit.call(build)
            # The done hook is intentionally unguarded: the DevServer enters its
            # blocking watch loop here, and a KeyboardInterrupt must pass through.
            self.hooks.done.call(build)
        except BuildError as error:
            build.errors.append(error)
            self.hooks.failed.call(error, build)
            raise
        return build


@contextmanager
def _stage(stage: str, source: Source | None = None) -> Iterator[None]:
    """Attribute any error raised inside a lifecycle phase to its stage/source."""

    source_path = source.path if source is not None else None
    try:
        yield
    except BuildError as error:
        error.with_context(stage=stage, source_path=source_path)
        raise
    except Exception as error:
        raise wrap(error, stage=stage, source_path=source_path) from error
