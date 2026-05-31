"""DevServer plugin: live preview with rebuild-on-change (``pyssg serve``).

This is a plugin, not a kernel feature. It taps the ``done`` hook and exploits
the fact that a ``Builder`` is reusable -- calling ``builder.run()`` again
produces a fresh ``Build``. So the whole watch loop lives inside the plugin and
the kernel stays untouched.

Flow:

    builder.run()                       first build
      -> done hook fires
           -> DevServer (first time):
                start an HTTP server thread serving the output directory,
                then enter a blocking watch loop on the main thread:
                  on change, call builder.run() again
                  -> done fires again -> guarded, just bumps the reload token

File watching uses watchdog (event-based) when it is installed -- declared by
the optional ``dev`` extra -- and falls back to dependency-free mtime polling
otherwise, so the kernel keeps its stdlib-only guarantee. Browser live reload is
an injected snippet that polls a token endpoint and reloads when the token
changes after a rebuild.
"""

from __future__ import annotations

import os
import threading
import time
import webbrowser
from collections.abc import Callable
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import TYPE_CHECKING

from pyssg.build import Build
from pyssg.errors import (
    BuildError,
    render_html_overlay,
    render_terminal,
    want_traceback,
)

if TYPE_CHECKING:
    from pyssg.builder import Builder

# Collapse bursts of file-system events into one rebuild (watchdog backend).
_DEBOUNCE_INTERVAL = 0.2

_DONE_STAGE = 1000  # run after every other done tap
_LIVERELOAD_PATH = "/__pyssg_livereload"
_LIVERELOAD_SNIPPET = (
    "<script>(function(){let v=null;setInterval(function(){"
    "fetch('" + _LIVERELOAD_PATH + "').then(function(r){return r.text();})"
    ".then(function(t){if(v===null){v=t;}else if(t!==v){location.reload();}})"
    ".catch(function(){});},1000);})();</script>"
)
_DEFAULT_IGNORES = frozenset(
    {".git", "__pycache__", ".venv", "node_modules", ".mypy_cache", ".pytest_cache"}
)


class DevServer:
    def __init__(
        self,
        *,
        host: str = "127.0.0.1",
        port: int = 8000,
        watch_paths: list[str] | None = None,
        livereload: bool = True,
        poll_interval: float = 0.3,
        config_path: str | None = None,
        open_browser: bool = False,
    ) -> None:
        self._host = host
        self._port = port
        self._watch_paths = watch_paths
        self._livereload = livereload
        self._poll_interval = poll_interval
        self._config_path = config_path
        self._open_browser = open_browser

        self._builder: Builder | None = None
        self._started = False
        self._token = 0
        self._error: BuildError | None = None

    def apply(self, builder: Builder) -> None:
        self._builder = builder
        builder.hooks.done.tap("DevServer", self._on_done, stage=_DONE_STAGE)
        # Tap `failed` too so a failing *first* build still starts the server and
        # shows the error overlay instead of crashing the command.
        builder.hooks.failed.tap("DevServer", self._on_failed, stage=_DONE_STAGE)

    def _on_done(self, build: Build) -> None:
        self._error = None
        # Subsequent builds (rebuilds) only bump the reload token.
        if self._started:
            self._token += 1
            return
        self._started = True
        self._serve_and_watch(build)

    def _on_failed(self, error: Exception, build: Build) -> None:
        self._error = error if isinstance(error, BuildError) else None
        # A rebuild failure just flips the page to the overlay (token bump);
        # a first-build failure still starts serving so the overlay is visible.
        if self._started:
            self._token += 1
            return
        self._started = True
        self._serve_and_watch(build)

    # -- server + watch loop -------------------------------------------------

    def _serve_and_watch(self, build: Build) -> None:
        out_dir = build.config.out.resolve()
        out_dir.mkdir(parents=True, exist_ok=True)

        server = self._make_server(out_dir)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url = _browser_url(self._host, self._port)
        print(f"pyssg serve serving {out_dir} at {url}")
        if self._open_browser:
            # The socket is already bound (ThreadingHTTPServer binds in its
            # constructor), so the browser can connect immediately.
            webbrowser.open(url)

        try:
            self._watch_loop(build)
        except KeyboardInterrupt:
            print("\nStopping pyssg serve...")
        finally:
            server.shutdown()
            server.server_close()

    def _make_server(self, out_dir: Path) -> ThreadingHTTPServer:
        handler = self._make_handler(out_dir)
        return ThreadingHTTPServer((self._host, self._port), handler)

    def _watch_loop(self, build: Build) -> None:
        roots, ignore_dirs = self._watch_targets(build)
        config_file = Path(self._config_path).resolve() if self._config_path else None

        def on_change(changed: set[Path]) -> None:
            self._rebuild(changed, config_file)

        watcher = _make_watcher(roots, ignore_dirs, on_change, self._poll_interval)
        print(f"Watching for changes ({watcher.backend} backend)... (Ctrl-C to stop)")
        watcher.run()

    def _rebuild(self, changed: set[Path], config_file: Path | None) -> None:
        assert self._builder is not None
        if config_file is not None and config_file in changed:
            print(f"Config changed ({config_file.name}); restart pyssg serve to apply.")
            changed = changed - {config_file}
            if not changed:
                return

        print(f"Change detected ({len(changed)} file(s)); rebuilding...")
        try:
            self._builder.run()
            print("Rebuilt.")
        except BuildError as error:  # keep serving the last good output
            print(render_terminal(error, show_traceback=want_traceback()))
        except Exception as error:  # pragma: no cover - defensive
            print(f"Build failed: {error}")

    def _watch_targets(self, build: Build) -> tuple[list[Path], set[Path]]:
        if self._watch_paths is not None:
            roots = [Path(p).resolve() for p in self._watch_paths]
        else:
            roots = [build.config.src.resolve().parent]
        # Never watch the output directory: writing to it would loop forever.
        ignore_dirs = {build.config.out.resolve()}
        return roots, ignore_dirs

    # -- request handling ----------------------------------------------------

    def _make_handler(self, out_dir: Path) -> Callable[..., SimpleHTTPRequestHandler]:
        dev = self

        class Handler(SimpleHTTPRequestHandler):
            def do_GET(self) -> None:
                if self.path.split("?", 1)[0] == _LIVERELOAD_PATH:
                    self._send_token()
                    return
                # While the last build is broken, every page shows the overlay;
                # it carries the live-reload snippet so it recovers on its own.
                if dev._error is not None:
                    self._serve_overlay(dev._error)
                    return
                if dev._livereload and self._serve_injected_html():
                    return
                super().do_GET()

            def _serve_overlay(self, error: BuildError) -> None:
                body = inject_livereload(render_html_overlay(error)).encode("utf-8")
                self.send_response(500)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _send_token(self) -> None:
                body = str(dev._token).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _serve_injected_html(self) -> bool:
                target = Path(self.translate_path(self.path))
                if target.is_dir():
                    target = target / "index.html"
                if target.suffix.lower() not in (".html", ".htm"):
                    return False
                if not target.is_file():
                    return False
                body = inject_livereload(target.read_text(encoding="utf-8")).encode(
                    "utf-8"
                )
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return True

            def log_message(self, format: str, *args: object) -> None:
                # Keep the dev server quiet; rebuild logs come from the loop.
                return

        return partial(Handler, directory=str(out_dir))


OnChange = Callable[[set[Path]], None]


def _make_watcher(
    roots: list[Path],
    ignore_dirs: set[Path],
    on_change: OnChange,
    poll_interval: float,
) -> _Watcher:
    """Pick watchdog when available, else the dependency-free poll fallback."""

    try:
        import watchdog  # noqa: F401
    except ImportError:
        return _PollWatcher(roots, ignore_dirs, on_change, poll_interval)
    return _WatchdogWatcher(roots, ignore_dirs, on_change)


class _Watcher:
    """Blocks the calling thread, invoking ``on_change`` for each change batch.

    ``run`` returns when interrupted (``KeyboardInterrupt`` propagates out).
    """

    backend: str

    def run(self) -> None:
        raise NotImplementedError


class _PollWatcher(_Watcher):
    backend = "poll"

    def __init__(
        self,
        roots: list[Path],
        ignore_dirs: set[Path],
        on_change: OnChange,
        poll_interval: float,
    ) -> None:
        self._roots = roots
        self._ignore_dirs = ignore_dirs
        self._on_change = on_change
        self._poll_interval = poll_interval

    def run(self) -> None:
        snapshot = _snapshot(self._roots, self._ignore_dirs)
        while True:
            time.sleep(self._poll_interval)
            current = _snapshot(self._roots, self._ignore_dirs)
            if current == snapshot:
                continue
            changed = _diff(snapshot, current)
            snapshot = current
            self._on_change(changed)


class _WatchdogWatcher(_Watcher):
    backend = "watchdog"

    def __init__(
        self,
        roots: list[Path],
        ignore_dirs: set[Path],
        on_change: OnChange,
    ) -> None:
        self._roots = roots
        self._ignore_dirs = ignore_dirs
        self._on_change = on_change
        self._pending: set[Path] = set()
        self._lock = threading.Lock()

    def run(self) -> None:
        from watchdog.events import FileSystemEvent, FileSystemEventHandler
        from watchdog.observers import Observer

        watcher = self

        # The misc ignore is needed only when watchdog is absent (base is Any);
        # unused-ignore keeps it quiet once the typed package is installed.
        class _Handler(FileSystemEventHandler):  # type: ignore[misc, unused-ignore]
            def on_any_event(self, event: FileSystemEvent) -> None:
                if event.is_directory:
                    return
                path = Path(os.fsdecode(event.src_path)).resolve()
                if _is_ignored(path, watcher._ignore_dirs):
                    return
                with watcher._lock:
                    watcher._pending.add(path)

        observer = Observer()
        for root in self._roots:
            if root.exists():
                observer.schedule(_Handler(), str(root), recursive=True)
        observer.start()
        try:
            self._drain_loop()
        finally:
            observer.stop()
            observer.join()

    def _drain_loop(self) -> None:
        while True:
            time.sleep(_DEBOUNCE_INTERVAL)
            with self._lock:
                if not self._pending:
                    continue
                changed = self._pending
                self._pending = set()
            self._on_change(changed)


def _snapshot(roots: list[Path], ignore_dirs: set[Path]) -> dict[Path, float]:
    """Map every watched file to its mtime, skipping ignored directories."""

    result: dict[Path, float] = {}
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if _is_ignored(path, ignore_dirs):
                continue
            try:
                result[path] = path.stat().st_mtime
            except OSError:
                continue
    return result


def _is_ignored(path: Path, ignore_dirs: set[Path]) -> bool:
    for part in path.parts:
        if part in _DEFAULT_IGNORES:
            return True
    resolved = path.resolve()
    for ignored in ignore_dirs:
        if resolved == ignored or ignored in resolved.parents:
            return True
    return False


def _diff(old: dict[Path, float], new: dict[Path, float]) -> set[Path]:
    """Paths that were added, removed or modified between two snapshots."""

    changed: set[Path] = set()
    for path, mtime in new.items():
        if old.get(path) != mtime:
            changed.add(path)
    for path in old:
        if path not in new:
            changed.add(path)
    return changed


def _browser_url(host: str, port: int) -> str:
    """The URL to print and open; a wildcard bind maps to localhost for browsing."""

    display_host = "localhost" if host in ("0.0.0.0", "", "::") else host
    return f"http://{display_host}:{port}/"


def inject_livereload(html: str) -> str:
    """Insert the live-reload snippet before ``</body>`` (or append it)."""

    lowered = html.lower()
    index = lowered.rfind("</body>")
    if index == -1:
        return html + _LIVERELOAD_SNIPPET
    return html[:index] + _LIVERELOAD_SNIPPET + html[index:]
