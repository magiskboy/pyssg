"""Dev server: watch + incremental rebuild + live reload.

Runs an initial full build, serves the output over HTTP, and watches the content
and layout directories. Each filesystem burst triggers an incremental rebuild;
the changed output URLs come straight from early-cutoff and bump a reload token
that an injected script polls, so only actually-changed pages cause the browser
to refresh.

Threading: the watchdog observer and the HTTP server each run on their own
thread; the main thread blocks until interrupted.
"""

from __future__ import annotations

import asyncio
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from time import perf_counter

from pyssg.cli.common import make_builder, open_cache
from pyssg.core.build import BuildStats
from pyssg.core.phases import IncrementalSession
from pyssg.core.types import Phase
from pyssg.watch import FsEvent, FsWatcher, coalesce

_RELOAD_PATH = "/__pyssg_reload__"
_RELOAD_SNIPPET = (
    "<script>(function(){let last=null;setInterval(async function(){"
    f'try{{const r=await fetch("{_RELOAD_PATH}");const t=await r.text();'
    "if(last!==null&&t!==last)location.reload();last=t;}catch(e){}},600);})();</script>"
).encode()


def _make_handler(directory: Path, token: list[int]) -> type[SimpleHTTPRequestHandler]:
    class _Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args: object, **kwargs: object) -> None:
            super().__init__(*args, directory=str(directory), **kwargs)  # type: ignore[arg-type]

        def log_message(self, fmt: str, *args: object) -> None:
            pass  # keep the console for build stats only

        def do_GET(self) -> None:
            if self.path == _RELOAD_PATH:
                self._send_bytes(str(token[0]).encode("ascii"), "text/plain")
                return
            html = self._html_target()
            if html is not None:
                data = html.read_bytes()
                if b"</body>" in data:
                    data = data.replace(b"</body>", _RELOAD_SNIPPET + b"</body>", 1)
                self._send_bytes(data, "text/html; charset=utf-8")
                return
            super().do_GET()

        def _html_target(self) -> Path | None:
            """The .html file this request resolves to, for live-reload injection."""
            fs = Path(self.translate_path(self.path.split("?", 1)[0]))
            if fs.is_dir():
                fs = fs / "index.html"
            return fs if fs.is_file() and fs.suffix == ".html" else None

        def _send_bytes(self, body: bytes, content_type: str) -> None:
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return _Handler


def _is_content_event(event: FsEvent, content_root: Path) -> bool:
    for raw in (event.path, event.dest):
        if raw and raw.endswith(".md") and str(content_root) in str(Path(raw).resolve()):
            return True
    return False


def _reparsed(stats: BuildStats) -> int:
    return stats.touched_per_phase.get(Phase.PARSE, 0)


def serve(
    site_dir: Path, host: str = "127.0.0.1", port: int = 8000, *, no_cache: bool = False
) -> None:
    """Build, serve and live-rebuild a site until interrupted."""
    site_dir = site_dir.resolve()
    builder = make_builder(site_dir, open_cache(site_dir, no_cache))
    session = IncrementalSession(builder)

    started = perf_counter()
    stats = asyncio.run(session.initial_build())
    print(
        f"initial build: {len(stats.changed_outputs)} pages "
        f"in {(perf_counter() - started) * 1000:.0f} ms",
        flush=True,
    )

    out_root = session.out_root
    out_root.mkdir(parents=True, exist_ok=True)
    token = [0]
    httpd = ThreadingHTTPServer((host, port), _make_handler(out_root, token))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()

    content_root = session.content_root

    def on_batch(events: list[FsEvent]) -> None:
        batch = coalesce(events)
        content_only = [e for e in batch if _is_content_event(e, content_root)]
        started = perf_counter()
        if content_only and len(content_only) == len(batch):
            stats = session.apply(content_only)
            kind = "incremental"
        else:
            fresh = IncrementalSession(session.builder)
            stats = asyncio.run(fresh.initial_build())
            kind = "full"
        if stats.changed_outputs:
            token[0] += 1
        print(
            f"{kind} rebuild: {len(stats.changed_outputs)} output(s), "
            f"{_reparsed(stats)} doc(s) reparsed, {stats.cache_hits} cache hit(s) "
            f"in {(perf_counter() - started) * 1000:.0f} ms",
            flush=True,
        )

    roots = [str(content_root)]
    if builder.layout is not None:
        roots.append(str(builder.layout.root))
    watcher = FsWatcher(roots, ignore=[str(out_root), "*.tmp"])
    watcher.run(on_batch)

    print(f"serving http://{host}:{port}/  (Ctrl-C to stop)", flush=True)
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        print("\nstopping")
    finally:
        watcher.stop()
        httpd.shutdown()
