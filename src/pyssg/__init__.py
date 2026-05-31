"""pyssg: a Static Site Generator with a small plugin + hook kernel.

The kernel consists only of: the hook system, the Builder (lifecycle
orchestrator), the Build (single-run state), neutral data models and the Plugin
protocol. Every feature is implemented as a plugin.
"""

from __future__ import annotations

from pyssg.build import Build
from pyssg.builder import Builder, BuilderHooks
from pyssg.config import Config, load_config
from pyssg.hooks import SyncBailHook, SyncHook, SyncWaterfallHook
from pyssg.models import Output, Source
from pyssg.plugin import Plugin

__all__ = [
    "Build",
    "Builder",
    "BuilderHooks",
    "Config",
    "Output",
    "Plugin",
    "Source",
    "SyncBailHook",
    "SyncHook",
    "SyncWaterfallHook",
    "load_config",
]
