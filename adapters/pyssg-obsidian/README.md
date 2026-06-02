# PySSG Publish (Obsidian plugin)

Build and preview your Obsidian vault as a static website with
[PySSG](https://github.com/magiskboy/pyssg), without leaving the editor.

- **Publish what you choose** - by default only notes whose frontmatter sets
  `publish: true` are rendered, so private notes stay private.
- **PKM-native** - `[[wikilinks]]`, `![[note]]` embeds, `![[image.png]]`
  attachments and `#tags` are handled by PySSG's built-in pipeline.
- **Live preview** - render the site inside Obsidian or in your browser; edits
  rebuild incrementally and the preview reloads itself.
- **Zero-setup Python** - on first use the plugin downloads an isolated Python
  runtime (via [uv](https://docs.astral.sh/uv/)) and installs PySSG into it. No
  system Python required; nothing is written into your vault.

## How it works

The plugin is a thin UI layer over the `pyssg` command-line tool. It generates a
`pyssg.config.py` in a private working directory **outside** the vault (using the
`pyssg.presets.obsidian` preset with your settings), then shells out to:

- `pyssg --site <workdir> build --json` for one-shot builds, and
- `pyssg --site <workdir> serve --json` for live preview.

Both commands speak newline-delimited JSON (`--json`), which the plugin parses to
track the served URL and rebuild progress. The build output is written outside
the vault, so it is never re-indexed by Obsidian.

## Commands

| Command | What it does |
| --- | --- |
| **Build site** | Full build to the output directory; reports the page count. |
| **Preview site (live)** | Starts the dev server and opens a preview pane. |
| **Open preview in browser** | Opens the running preview in your system browser. |
| **Stop preview server** | Stops the dev server and closes the preview pane. |

A ribbon globe icon runs **Preview site**.

## Settings

- **Publish marked notes only** - allowlist (`publish: true`) vs. publish-all
  (except `publish: false`).
- **Base URL** - absolute site URL for sitemaps/RSS.
- **Content subfolder** - build only a subfolder of the vault (default: whole vault).
- **Exclude / Include globs** - comma-separated filters. The `.obsidian`,
  `.trash` and `.git` folders are always excluded, and the plugin auto-discovers
  your Templates / Daily-notes folders from the vault's own settings and excludes
  them too; these globs are *added* on top.
- **Preview server** - host and port for live preview.
- **pyssg executable** - point at an existing `pyssg` instead of the managed
  runtime (useful for offline / CI machines).
- **pyssg version (git ref)** - branch, tag or commit to install when
  auto-provisioning.
- **Reset managed runtime** - delete the downloaded runtime so it is rebuilt.

## Development

```bash
npm install
npm run dev      # watch + rebuild main.js
npm run build    # type-check + production bundle
```

Copy `manifest.json`, `main.js` and `styles.css` into
`<vault>/.obsidian/plugins/pyssg-publish/` to test locally, or symlink this
folder there.

This adapter lives in the PySSG monorepo under `adapters/pyssg-obsidian/`. It has
its own Node/TypeScript toolchain and is not covered by the Python test suite;
future ecosystem integrations follow the same `adapters/<name>/` layout.
