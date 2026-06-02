"""Deploy targets: registry and public surface.

Deploy is a periphery subsystem; the engine never imports it. A *target* is a
small object that knows how to push a built site to one hosting provider; the
pipeline orchestrates the provider-agnostic part (build, hash, skip, persist).

Built-in targets are not registered automatically: each one lives in its own
module (``github_pages``, ``cloudflare``, ``netlify``) and calls
:func:`register` at import time. The CLI imports them lazily, so a user who
never runs ``pyssg deploy`` does not pay for the optional third-party imports.
For tests, the registry can be passed in explicitly via the ``targets`` keyword
of :func:`pyssg.deploy.pipeline.run_deploy`, so there is no need to mutate
module-level state.
"""

from __future__ import annotations

from pyssg.deploy.base import (
    DeployContext,
    DeployError,
    DeployResult,
    DeployTarget,
)

__all__ = [
    "TARGETS",
    "DeployContext",
    "DeployError",
    "DeployResult",
    "DeployTarget",
    "get_target",
    "list_targets",
    "load_builtin_targets",
    "register",
]

# Built-in target modules, in MVP priority order. Each one calls register() at
# import time; missing modules (a milestone not yet landed) are skipped so the
# CLI keeps working as targets come online one at a time.
_BUILTIN_MODULES = ("github_pages", "cloudflare", "netlify")

# Module-level registry. Mutable by design: targets register themselves at
# import time. Tests should NOT mutate this dict directly; the pipeline accepts
# an explicit ``targets=`` argument for isolation.
TARGETS: dict[str, DeployTarget] = {}


def register(target: DeployTarget) -> None:
    """Add a target to the global registry.

    Raises :class:`DeployError` if a target with the same ``name`` is already
    registered, which catches double-imports and accidental name clashes
    between built-in and third-party targets.
    """
    if target.name in TARGETS:
        raise DeployError(f"deploy target already registered: {target.name}")
    TARGETS[target.name] = target


def get_target(name: str, *, targets: dict[str, DeployTarget] | None = None) -> DeployTarget:
    """Look up a target by name; raise :class:`DeployError` if unknown.

    ``targets`` defaults to the global registry; tests pass an explicit dict to
    avoid touching module state.
    """
    registry = targets if targets is not None else TARGETS
    if name not in registry:
        available = ", ".join(sorted(registry)) or "(none)"
        raise DeployError(f"unknown deploy target: {name}. available: {available}")
    return registry[name]


def list_targets(*, targets: dict[str, DeployTarget] | None = None) -> list[str]:
    """Names of registered targets, sorted."""
    registry = targets if targets is not None else TARGETS
    return sorted(registry)


def load_builtin_targets() -> None:
    """Import the built-in target modules so they register themselves.

    Idempotent: a module is imported at most once (Python caches it), so calling
    this repeatedly does not double-register. Targets whose module does not exist
    yet (a future milestone) are skipped silently; any other import error -- a
    real bug in a target module -- is allowed to propagate.

    The CLI calls this before dispatching a deploy so the global :data:`TARGETS`
    registry is populated; tests that pass an explicit ``targets=`` registry do
    not need it and stay isolated from module-level state.
    """
    import importlib

    for module in _BUILTIN_MODULES:
        try:
            importlib.import_module(f"{__name__}.{module}")
        except ModuleNotFoundError as exc:
            # Only swallow "the target module itself is absent"; a missing
            # *dependency* of an existing module (e.g. httpx) is a different
            # error class handled at deploy time, and a typo in an import inside
            # a target module must not be hidden here.
            if exc.name == f"{__name__}.{module}":
                continue
            raise
