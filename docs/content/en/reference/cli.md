---
title: CLI reference
nav_title: CLI
order: 2
---

# CLI reference

pyssg is invoked as a module: `python -m pyssg [--site PATH] <command> [options]`.
Through uv that is `pyssg ...`.

## Global option

| Option | Default | Description |
|---|---|---|
| `--site PATH` | `.` | The site directory. All other paths in the config (`content_dir`, `output_dir`, `layout`) are relative to it. It is global, so it goes *before* the command: `pyssg --site my-site build`. |

Run any command with `--help` to see its options.

## `build`

Full build to the output directory.

```bash
pyssg --site my-site build
```

| Option | Default | Description |
|---|---|---|
| `--no-cache` | off | Ignore the persistent cache (prove a clean build from scratch). |
| `--profile` | off | Print per-phase touched counts and cache hits. |
| `--json` | off | Emit a single-line machine-readable summary instead of human text. |

Prints `build: N pages written`. With `--json` it prints one JSON object, e.g.
`{"command": "build", "ok": true, "pages": 3, "cache_hits": 0, "phases": {...}}`,
or `{"command": "build", "ok": false, "error": "..."}` on failure (exit code 1).

## `serve`

Watch the content, rebuild incrementally, and serve with live reload.

```bash
pyssg --site my-site serve
```

| Option | Default | Description |
|---|---|---|
| `--host HOST` | `127.0.0.1` | Address to bind. |
| `--port PORT` | `8000` | Port to bind. |
| `--no-cache` | off | Ignore the persistent cache. |
| `--json` | off | Emit newline-delimited JSON events (a `ready` event, then a `rebuild` event per change) instead of human text. |

Edit any file under `content/` and the affected page rebuilds and the browser
reloads automatically.

## `clean`

Remove the output directory and the cache.

```bash
pyssg --site my-site clean
```

| Option | Default | Description |
|---|---|---|
| `--yes` | off | Skip the interactive confirmation. |

Without `--yes`, `clean` lists what it will remove and asks for confirmation.

## `new`

Scaffold project files. All scaffolding is deterministic (sample dates are fixed
literals unless you pass `--date`), so running it twice produces identical files.

### `new site`

Scaffold a new site for a preset: a one-line `pyssg.config.py` plus a little
sample content.

```bash
pyssg --site my-site new site --preset docs
```

| Option | Default | Description |
|---|---|---|
| `--preset {docs,blog,obsidian}` | `docs` | Which preset to scaffold. |
| `--force` | off | Overwrite an existing `pyssg.config.py` (otherwise `new site` refuses, to avoid clobbering a real site). |

### `new post`

Scaffold a new blog post under `content/posts/`.

```bash
pyssg --site my-site new post --title "Hello, world" --tag intro
```

| Option | Default | Description |
|---|---|---|
| `--title TEXT` | `New Post` | Post title; also the basis for the file slug. |
| `--tag TEXT` | *(none)* | A tag to add to the frontmatter. Repeatable. |
| `--date YYYY-MM-DD` | today | Frontmatter date. Pass it explicitly for reproducible output. |
| `--slug TEXT` | from title | File name slug (the file is `content/posts/<slug>.md`). |
| `--force` | off | Overwrite an existing post. |

### `new theme`

Copy a built-in theme into the site so you can customize it (the "eject").

```bash
pyssg --site my-site new theme --name docs --to layouts/theme
```

| Option | Default | Description |
|---|---|---|
| `--name {docs,blog}` | *(required)* | Built-in theme to copy. |
| `--to DIR` | `layouts/theme` | Destination directory, relative to the site. |

Refuses to overwrite an existing destination. After copying, set `layout="<DIR>"`
in your `pyssg.config.py`. See [Customize a theme](../how-to/customize-theme.md).

### `new plugin`

Scaffold a starter plugin module under `plugins/`: a plugin class plus its
lowercase factory, ready to customize.

```bash
pyssg --site my-site new plugin my_plugin
```

| Argument / Option | Default | Description |
|---|---|---|
| `NAME` | *(required)* | Plugin name; must be a valid Python identifier (used as the module, factory, and class basis). |
| `--force` | off | Overwrite an existing file. |

The generated module documents its own hook wiring. To enable it, add
`my_plugin()` to `config.plugins` (the plugins directory must be importable, e.g.
on `PYTHONPATH`).

## `deploy`

Push the built site to a hosting provider. The form is
`pyssg deploy <target-or-action>`, where the leaf is either a configured target
(`github-pages`, `cloudflare`, `netlify`) or a meta action.

```bash
pyssg --site my-site deploy list
pyssg --site my-site deploy github-pages --dry-run
```

| Action | Description |
|---|---|
| `list` | List the targets configured in `pyssg.config.py` and whether each is implemented. |
| `status` | Show the last-deploy record (timestamp, deployment id, URL) per configured target. |

Each target subcommand accepts:

| Option | Default | Description |
|---|---|---|
| `--dry-run` | off | Validate and report what would be uploaded, but do not push. |
| `--force` | off | Redeploy even if the output is byte-identical to the previous deploy. |
| `--skip-build` | off | Reuse the existing output directory instead of rebuilding. |
| `--skip-check` | off | Skip the post-build sanity check. |

See [Deploy your site](../how-to/deploy.md) for the per-provider configuration.

## Deprecated aliases

These earlier commands still work as hidden aliases; prefer the `new` group:

| Alias | Use instead |
|---|---|
| `pyssg init --preset docs` | `pyssg new site --preset docs` |
| `pyssg eject-layout --theme docs` | `pyssg new theme --name docs` |
