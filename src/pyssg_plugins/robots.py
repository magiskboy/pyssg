"""Robots plugin: generate a ``robots.txt`` for the built site.

Taps ``generate`` and appends one ``Output``. Standard library only.

A static ``robots.txt`` is trivial, so this plugin earns its place by wiring in
site-wide context the author would otherwise repeat by hand:

- the ``Sitemap:`` directive is emitted as an absolute URL built from
  ``site["base_url"]`` (the spec requires an absolute location), and only when a
  base URL is configured;
- a single ``site["private"]`` flag flips the whole file to "disallow
  everything", a one-switch guard for staging deploys.

Without options the output allows every crawler. ``disallow``/``allow`` set
rules for the default ``*`` group, while ``groups`` gives full control with
per-user-agent rules.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from pyssg.build import Build
from pyssg.builder import Builder
from pyssg.content import absolute_url, site
from pyssg.models import Output

# Robots only emits a file; run alongside the other generators.
_GENERATE_STAGE = 100


class Robots:
    def __init__(
        self,
        *,
        path: str = "robots.txt",
        disallow: Sequence[str] = (),
        allow: Sequence[str] = (),
        sitemap: bool = True,
        sitemap_path: str = "sitemap.xml",
        groups: list[dict[str, object]] | None = None,
    ) -> None:
        self._path = path
        self._disallow = list(disallow)
        self._allow = list(allow)
        self._sitemap = sitemap
        self._sitemap_path = sitemap_path
        self._groups = groups

    def apply(self, builder: Builder) -> None:
        builder.hooks.generate.tap("Robots", self._generate, stage=_GENERATE_STAGE)

    def _generate(self, build: Build) -> None:
        options = site(build)
        base_url = str(options.get("base_url", ""))
        private = bool(options.get("private", False))

        lines: list[str] = []
        if private:
            # Staging guard: keep the whole site out of every index.
            lines.extend(["User-agent: *", "Disallow: /"])
        else:
            lines.extend(self._rule_lines())

        # A sitemap reference must be absolute, so it needs a base URL. It is
        # also pointless on a fully disallowed site.
        if self._sitemap and base_url and not private:
            lines.append("")
            lines.append(f"Sitemap: {absolute_url(base_url, self._sitemap_path)}")

        document = "\n".join(lines) + "\n"
        build.outputs.append(Output(path=Path(self._path), content=document))

    def _rule_lines(self) -> list[str]:
        if self._groups is not None:
            return _group_lines(self._groups)
        lines = ["User-agent: *"]
        for path in self._allow:
            lines.append(f"Allow: {path}")
        for path in self._disallow:
            lines.append(f"Disallow: {path}")
        # An empty "Disallow:" line is the canonical "allow everything" rule.
        if not self._disallow:
            lines.append("Disallow:")
        return lines


def _group_lines(groups: list[dict[str, object]]) -> list[str]:
    lines: list[str] = []
    for index, group in enumerate(groups):
        if index > 0:
            lines.append("")
        for agent in _agents(group.get("user_agent")):
            lines.append(f"User-agent: {agent}")
        for path in _paths(group.get("allow")):
            lines.append(f"Allow: {path}")
        disallow = _paths(group.get("disallow"))
        for path in disallow:
            lines.append(f"Disallow: {path}")
        if not disallow:
            lines.append("Disallow:")
    return lines


def _agents(value: object) -> list[str]:
    if isinstance(value, str) and value:
        return [value]
    if isinstance(value, (list, tuple)):
        agents = [str(item) for item in value if str(item)]
        if agents:
            return agents
    return ["*"]


def _paths(value: object) -> list[str]:
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value if str(item)]
    return []
