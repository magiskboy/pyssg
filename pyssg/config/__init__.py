"""Site configuration loading.

Configuration is expressed as Python code in a ``pyssg.config.py`` file at the
site root, rather than as YAML/TOML. Code lets the user compose plugin instances
and arbitrary template variables with full type checking, which is the whole
point of the design: the basic user only ever touches this file plus a layout
package.

The file MUST expose a module-level ``config`` bound to a :class:`Config`
instance. Loading is deterministic and side-effect free with respect to this
module: we import the file fresh each call and read back the variable, holding no
global mutable state.
"""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from pyssg.core.errors import ConfigError

if TYPE_CHECKING:
    # The runtime ``plugins`` list holds plugin instances; importing the Plugin
    # protocol only under TYPE_CHECKING keeps this module free of the heavier
    # plugin/builder imports. Thanks to ``from __future__ import annotations`` the
    # annotation below stays a string and never triggers a runtime import.
    from pyssg.plugins.api import Plugin

# Name of the configuration file expected at the site root.
CONFIG_FILENAME = "pyssg.config.py"

# Stable synthetic module name used when importing the user's config file. A
# fixed name keeps the import deterministic and avoids leaking the site path into
# the module registry.
_CONFIG_MODULE_NAME = "pyssg_user_config"

# Name of the variable the config module MUST export.
_CONFIG_VARIABLE = "config"


@dataclass(slots=True)
class Config:
    """Resolved site configuration.

    Directory fields are relative to the site directory; the engine joins them
    against the site root when it runs. ``plugins`` order is the apply order.
    ``site`` holds arbitrary template variables (title, etc.).

    ``layout`` is either a ``str`` path relative to the site directory, or an
    absolute :class:`~pathlib.Path` (e.g. a built-in theme; see
    :func:`pyssg.themes.theme_path`) used as-is.

    ``theme`` holds site-level overrides for the active layout's configurable
    options (colors, layout toggles, nav, ...). A theme declares its option
    defaults in its ``layout.toml`` ``[options]`` table; the engine resolves the
    effective options as ``layout defaults <- this dict`` and exposes them to
    templates as ``theme``. The merge is a shallow per-key override.

    The *mechanism* is standardized but the *option vocabulary* is per-theme:
    each theme owns its own option names, so consult that theme's documentation.
    Keys a theme does not declare are still passed through (a theme may read
    freeform extras), but the engine emits a non-fatal warning for them, since an
    undeclared key is usually a typo. For consistency across themes, theme
    authors are encouraged -- not required -- to reuse a few conventional names
    when applicable, e.g. ``default_theme`` ("auto"/"light"/"dark" color scheme)
    and ``accent`` (primary color).

    ``deploy`` holds per-target options for the ``pyssg deploy`` subcommand;
    keys are target names (``"github-pages"``, ``"cloudflare"``, ``"netlify"``)
    and values are the option dicts passed to that target. This field is not
    validated at load time: a site that never deploys does not need to fill it
    in, and validation runs only when the user actually invokes
    ``pyssg deploy <target>``.
    """

    content_dir: str = "content"
    output_dir: str = "dist"
    layout: str | Path | None = None
    base_url: str = ""
    plugins: list[Plugin] = field(default_factory=list)
    site: dict[str, object] = field(default_factory=dict)
    theme: dict[str, object] = field(default_factory=dict)
    deploy: dict[str, dict[str, object]] = field(default_factory=dict)


def load_config(site_dir: Path) -> Config:
    """Load and validate the ``pyssg.config.py`` found in ``site_dir``.

    Raises :class:`ConfigError` if the file is missing, does not export a
    ``config`` variable, or that variable is not a :class:`Config` instance.
    """
    config_path = site_dir / CONFIG_FILENAME
    if not config_path.is_file():
        raise ConfigError(f"no {CONFIG_FILENAME} found in site directory {site_dir}")

    spec = importlib.util.spec_from_file_location(_CONFIG_MODULE_NAME, config_path)
    # ``spec``/``spec.loader`` are only None for exotic loaders; for a plain file
    # path both are populated. Guard anyway so mypy --strict is satisfied and any
    # surprising loader surfaces as a clear ConfigError instead of an AttributeError.
    if spec is None or spec.loader is None:
        raise ConfigError(f"could not load {CONFIG_FILENAME} from {config_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    if not hasattr(module, _CONFIG_VARIABLE):
        raise ConfigError(
            f"{CONFIG_FILENAME} must define a module-level '{_CONFIG_VARIABLE}' variable"
        )

    config = getattr(module, _CONFIG_VARIABLE)
    if not isinstance(config, Config):
        raise ConfigError(
            f"'{_CONFIG_VARIABLE}' in {CONFIG_FILENAME} must be a Config instance, "
            f"got {type(config).__name__}"
        )

    return config
