---
title: Dev server
order: 3
---

# Dev server

`pyssg serve` builds your site, serves it locally, and rebuilds automatically
whenever a source file changes. With live reload on (the default), the browser
refreshes itself after each rebuild.

```bash
pyssg serve
```

```text
pyssg serve serving /path/to/public at http://127.0.0.1:8000/
Watching for changes (watchdog backend)... (Ctrl-C to stop)
Change detected (1 file(s)); rebuilding...
Rebuilt.
```

Open the printed URL and start editing. Stop the server with `Ctrl-C`.

## Options

| Flag | Default | Meaning |
|------|---------|---------|
| `-c`, `--config` | `pyssg.config.py` | Config file to load. |
| `--host` | `127.0.0.1` | Address to bind. |
| `--port` | `8000` | Port to bind. |
| `--no-livereload` | off | Disable automatic browser reload. |
| `--open` | off | Open the site in the default browser once the server starts. |

```bash
pyssg serve --port 3000 --open
```

## How it works

`pyssg serve` is not a kernel feature - it is the `DevServer` plugin. Because a
`Builder` is reusable (each `run()` produces a fresh build), the whole watch
loop fits inside a plugin that taps the `done` hook:

1. The first build finishes and fires `done`.
2. `DevServer` starts an HTTP server thread for the output directory, then
   enters a blocking watch loop.
3. On a file change it calls `builder.run()` again and bumps a reload token.
4. The injected live-reload script polls that token and reloads on change.

File watching uses [watchdog](https://pypi.org/project/watchdog/) (event-based)
when it is installed - enable it with the `dev` extra (`uv sync --extra dev`).
When watchdog is absent it falls back to standard-library mtime polling, so the
kernel keeps its stdlib-only guarantee either way. The output directory is never
watched (writing to it would loop forever).

## Notes

- **Config changes need a restart.** Editing `pyssg.config.py` can change the
  plugin list, which is fixed when the builder is created. `pyssg serve` detects
  the change and prints a reminder; restart it to apply.
- **Brief 404s during rebuild.** With `clean=True` (the preset default) the
  output directory is recreated on each build, so a request landing mid-rebuild
  may briefly 404. Live reload retries on the next poll.
- **Build errors keep serving.** If a rebuild fails, the error is printed and
  the last good output is kept; fix the source and save again.

## Using it in config

`pyssg serve` appends a `DevServer` automatically, so you usually do not
configure anything. For custom defaults you can add it yourself - it is just a
plugin:

```python
from pyssg_plugins import DevServer

# ... DevServer(host="0.0.0.0", port=4000, livereload=False)
```
