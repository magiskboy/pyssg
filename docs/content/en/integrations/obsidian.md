---
title: Publish an Obsidian vault
nav_title: Obsidian
order: 2
---

# Publish an Obsidian vault

This guide shows how to turn an [Obsidian](https://obsidian.md) vault into a
static website with the **PySSG Publish** plugin, and how to do the same from the
command line if you prefer. You do not need to know Python.

## Before you begin

- Obsidian on desktop (the plugin shells out to a local process, so it is
  desktop-only).
- An internet connection the first time you build, so the plugin can download its
  runtime. You do **not** need to install Python yourself - see
  [How the Python runtime is provisioned](#how-the-python-runtime-is-provisioned).

## Install the plugin

The plugin is not yet in the community store, so install it manually:

1. Build it from the PySSG repository:

   ```bash
   cd adapters/pyssg-obsidian
   npm install
   npm run build
   ```

2. Copy `manifest.json`, `main.js` and `styles.css` into your vault under
   `.obsidian/plugins/pyssg-publish/`.
3. In Obsidian, open **Settings -> Community plugins**, reload, and enable
   **PySSG Publish**.

## Choose what gets published

By default publishing is a **denylist**: every note is published except those
whose frontmatter sets `publish: false`. This suits a whole-vault wiki - you
write notes and they go live, hiding the occasional private one:

```markdown
---
title: A private draft
publish: false
---

This note is kept out of the site.
```

Wikilinks (`[[Note]]`), note embeds (`![[Note]]`), attachment embeds
(`![[image.png]]`) and `#tags` all work; attachments are copied into the output
automatically. Hugo-style `_index.md` files become section landing pages (routed
to the folder's root). If you would rather opt notes *in*, turn on **Publish
marked notes only** in settings - then a note is published only when it sets
`publish: true`.

## Preview your site

- Run the **Preview site (live)** command (or click the globe in the ribbon).
  The plugin starts a dev server and opens a preview pane inside Obsidian. Edit a
  note and the preview reloads itself.
- Run **Open preview in browser** to view the same site in your system browser.
- Run **Stop preview server** when you are done.

## Build and export

- Run **Build site** to render the whole site once. The notice reports how many
  pages were written and where.
- Run **Open output folder** to reveal the generated site in your file manager.
  From there you can deploy it (see [Deploy a built site](../how-to/deploy.md)).

The output is written to a working directory **outside** your vault, so build
artifacts are never mixed into your notes or re-indexed by Obsidian.

## Settings

| Setting | What it controls |
| --- | --- |
| Publish marked notes only | Off (default) = publish everything except `publish: false`; on = allowlist, publish only `publish: true`. |
| Base URL | Absolute site URL used for sitemaps and RSS. |
| Content subfolder | Build only a subfolder of the vault (default: the whole vault). |
| Exclude / Include globs | Comma-separated filters, *added* to the always-excluded `.obsidian`, `.trash`, `.git` and the Templates / Daily-notes folders the plugin reads from your vault settings. |
| Preview server | Host and port for live preview. |
| pyssg executable | Use an existing `pyssg` instead of the managed runtime. |
| pyssg version (git ref) | Branch, tag or commit installed when auto-provisioning. |
| Reset managed runtime | Delete the downloaded runtime so it is rebuilt. |

## Use pyssg without the plugin

The plugin is a convenience layer; you can build the same vault from the terminal
with the `obsidian` preset. Scaffold a fresh vault-style site:

```bash
pyssg --site my-vault new site --preset obsidian
pyssg --site my-vault build
pyssg --site my-vault serve   # live preview with reload
```

To publish an **existing** vault without adding a config file to it, point
`content_dir` at the vault and write the output elsewhere - this is exactly what
the plugin does:

```python
# pyssg.config.py (kept outside the vault)
from __future__ import annotations

from pyssg.presets import obsidian

config = obsidian(
    site={"title": "My Vault"},
    base_url="https://example.com",
    content_dir="/absolute/path/to/vault",
    output_dir="/absolute/path/to/output",
    publish_required=False,           # denylist (default); True = allowlist (publish: true only)
    exclude=["Templates/**"],          # added to the .obsidian/.trash/.git defaults
)
```

Then `pyssg --site <dir-containing-this-config> build`. See the
[CLI reference](../reference/cli.md) and
[configuration reference](../reference/configuration.md) for all options.

## How the Python runtime is provisioned

The first time you build or preview, the plugin downloads
[uv](https://docs.astral.sh/uv/) (a small static binary), uses it to install a
managed Python and an isolated copy of PySSG, and caches everything in a shared
application-data directory - never inside your vault. This runs once in the
background; afterwards builds start instantly. Pin the PySSG version with the
**pyssg version (git ref)** setting for reproducible installs.

## Troubleshooting

- **Setup failed or seems stuck.** Use **Reset managed runtime** in settings, then
  build again to re-provision from scratch.
- **Offline or managed machine.** Install PySSG yourself and set the **pyssg
  executable** path in settings; the plugin then skips the download entirely.
- **A note will not publish.** Confirm its frontmatter has `publish: true` (in
  allowlist mode) and that it is not inside an excluded folder.

## Next steps

- [Deploy a built site](../how-to/deploy.md) - publish the generated output.
- [CLI reference](../reference/cli.md) - every `pyssg` command and flag.
