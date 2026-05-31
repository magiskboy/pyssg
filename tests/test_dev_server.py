"""Unit tests for the DevServer plugin.

The blocking watch loop is not exercised; tests cover the pure helpers, the
rebuild-token guard, and a short-lived real HTTP server (no watch loop).
"""

from __future__ import annotations

import os
import tempfile
import threading
import time
import unittest
import urllib.request
from pathlib import Path
from unittest import mock

from pyssg.build import Build
from pyssg.config import Config
from pyssg_plugins.dev_server import (
    DevServer,
    _browser_url,
    _diff,
    _make_watcher,
    _PollWatcher,
    _snapshot,
    inject_livereload,
)


class SnapshotTest(unittest.TestCase):
    def test_maps_files_to_mtime(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.md").write_text("a", encoding="utf-8")
            (root / "sub").mkdir()
            (root / "sub" / "b.md").write_text("b", encoding="utf-8")

            snap = _snapshot([root], set())

            self.assertIn(root / "a.md", snap)
            self.assertIn(root / "sub" / "b.md", snap)

    def test_ignores_default_dirs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "__pycache__").mkdir()
            (root / "__pycache__" / "x.pyc").write_text("x", encoding="utf-8")
            (root / "keep.md").write_text("k", encoding="utf-8")

            snap = _snapshot([root], set())

            self.assertIn(root / "keep.md", snap)
            self.assertNotIn(root / "__pycache__" / "x.pyc", snap)

    def test_ignores_output_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = root / "public"
            out.mkdir()
            (out / "index.html").write_text("o", encoding="utf-8")
            (root / "page.md").write_text("p", encoding="utf-8")

            snap = _snapshot([root], {out.resolve()})

            self.assertIn(root / "page.md", snap)
            self.assertNotIn(out / "index.html", snap)

    def test_missing_root_is_skipped(self) -> None:
        self.assertEqual(_snapshot([Path("/no/such/dir")], set()), {})


class DiffTest(unittest.TestCase):
    def test_detects_added(self) -> None:
        self.assertEqual(_diff({}, {Path("a"): 1.0}), {Path("a")})

    def test_detects_removed(self) -> None:
        self.assertEqual(_diff({Path("a"): 1.0}, {}), {Path("a")})

    def test_detects_modified(self) -> None:
        self.assertEqual(_diff({Path("a"): 1.0}, {Path("a"): 2.0}), {Path("a")})

    def test_no_change(self) -> None:
        self.assertEqual(_diff({Path("a"): 1.0}, {Path("a"): 1.0}), set())


class SnapshotChangeTest(unittest.TestCase):
    def test_modifying_file_changes_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            f = root / "a.md"
            f.write_text("a", encoding="utf-8")

            before = _snapshot([root], set())
            os.utime(f, (1_000_000, 1_000_000))
            after = _snapshot([root], set())

            self.assertEqual(_diff(before, after), {f})


class MakeWatcherTest(unittest.TestCase):
    def test_backend_matches_availability(self) -> None:
        watcher = _make_watcher([], set(), lambda changed: None, 0.1)
        try:
            import watchdog  # noqa: F401

            self.assertEqual(watcher.backend, "watchdog")
        except ImportError:
            self.assertEqual(watcher.backend, "poll")

    def test_falls_back_to_poll_without_watchdog(self) -> None:
        try:
            import watchdog  # noqa: F401
        except ImportError:
            watcher = _make_watcher([], set(), lambda changed: None, 0.1)
            self.assertIsInstance(watcher, _PollWatcher)
        else:
            self.skipTest("watchdog is installed")


class PollWatcherTest(unittest.TestCase):
    class _Stop(Exception):
        pass

    def test_fires_on_change(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "a.md"
            target.write_text("a", encoding="utf-8")

            seen: list[set[Path]] = []

            def on_change(changed: set[Path]) -> None:
                seen.append(changed)
                raise PollWatcherTest._Stop

            watcher = _PollWatcher([root], set(), on_change, 0.01)

            def run() -> None:
                try:
                    watcher.run()
                except PollWatcherTest._Stop:
                    pass

            thread = threading.Thread(target=run)
            thread.start()
            time.sleep(0.05)
            os.utime(target, (2_000_000, 2_000_000))
            thread.join(timeout=2)

            self.assertFalse(thread.is_alive())
            self.assertTrue(seen)
            self.assertIn(target, seen[0])


class InjectLivereloadTest(unittest.TestCase):
    def test_inserts_before_body_close(self) -> None:
        out = inject_livereload("<html><body>hi</body></html>")
        self.assertIn("<script>", out)
        self.assertLess(out.index("<script>"), out.index("</body>"))

    def test_case_insensitive_body(self) -> None:
        out = inject_livereload("<BODY>hi</BODY>")
        self.assertIn("<script>", out)
        self.assertLess(out.index("<script>"), out.lower().index("</body>"))

    def test_appends_when_no_body(self) -> None:
        out = inject_livereload("<p>hi</p>")
        self.assertTrue(out.startswith("<p>hi</p>"))
        self.assertIn("<script>", out)


class GuardTest(unittest.TestCase):
    def test_rebuild_only_bumps_token(self) -> None:
        dev = DevServer()
        dev._started = True  # pretend the server is already running
        build = Build(config=Config(src=Path("content"), out=Path("public")))

        dev._on_done(build)
        dev._on_done(build)

        self.assertEqual(dev._token, 2)


class BrowserUrlTest(unittest.TestCase):
    def test_uses_host_and_port(self) -> None:
        self.assertEqual(_browser_url("127.0.0.1", 8000), "http://127.0.0.1:8000/")

    def test_wildcard_host_maps_to_localhost(self) -> None:
        self.assertEqual(_browser_url("0.0.0.0", 3000), "http://localhost:3000/")
        self.assertEqual(_browser_url("::", 3000), "http://localhost:3000/")


class OpenBrowserTest(unittest.TestCase):
    def test_default_is_off(self) -> None:
        self.assertFalse(DevServer()._open_browser)

    def _serve_once(self, dev: DevServer) -> mock.Mock:
        """Run a single serve pass with the watch loop and browser stubbed out."""

        build = Build(config=Config(src=Path("content"), out=Path("public")))
        with tempfile.TemporaryDirectory() as tmp:
            build.config.out = Path(tmp) / "public"
            with (
                mock.patch("pyssg_plugins.dev_server.webbrowser.open") as opener,
                mock.patch.object(DevServer, "_watch_loop", return_value=None),
            ):
                dev._serve_and_watch(build)
        return opener

    def test_opens_url_after_server_starts(self) -> None:
        opener = self._serve_once(DevServer(port=0, open_browser=True))
        opener.assert_called_once()
        self.assertTrue(opener.call_args.args[0].startswith("http://"))

    def test_does_not_open_when_disabled(self) -> None:
        opener = self._serve_once(DevServer(port=0, open_browser=False))
        opener.assert_not_called()


class ServerTest(unittest.TestCase):
    def test_serves_injected_html_and_token(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            (out / "index.html").write_text(
                "<html><body>Home</body></html>", encoding="utf-8"
            )
            (out / "data.json").write_text('{"a":1}', encoding="utf-8")

            dev = DevServer(port=0)  # OS-assigned port
            dev._token = 7
            server = dev._make_server(out)
            port = server.server_address[1]
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base = f"http://127.0.0.1:{port}"
                html = urllib.request.urlopen(f"{base}/index.html").read().decode()
                token = (
                    urllib.request.urlopen(f"{base}/__pyssg_livereload").read().decode()
                )
                data = urllib.request.urlopen(f"{base}/data.json").read().decode()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

            self.assertIn("Home", html)
            self.assertIn("<script>", html)  # livereload injected
            self.assertEqual(token, "7")
            self.assertEqual(data, '{"a":1}')  # non-html served verbatim

    def test_livereload_disabled_serves_plain_html(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            (out / "index.html").write_text(
                "<html><body>Home</body></html>", encoding="utf-8"
            )

            dev = DevServer(port=0, livereload=False)
            server = dev._make_server(out)
            port = server.server_address[1]
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                html = (
                    urllib.request.urlopen(f"http://127.0.0.1:{port}/").read().decode()
                )
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

            self.assertIn("Home", html)
            self.assertNotIn("<script>", html)


if __name__ == "__main__":
    unittest.main()
