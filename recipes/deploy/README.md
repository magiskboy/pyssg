# Deploy recipes

Copy-paste configurations for hosting a pyssg site. Each subdirectory is one
deploy target, self-contained and described by a static `deploy.toml` manifest.

| Target | Folder | Project files to copy |
|---|---|---|
| GitHub Pages | [`github-pages/`](github-pages/) | `.github/workflows/deploy.yml` + `.nojekyll` |
| Netlify | [`netlify/`](netlify/) | `netlify.toml` |
| Cloudflare Pages | [`cloudflare-pages/`](cloudflare-pages/) | dashboard config (or optional `.github/workflows/deploy.yml`) |

All recipes build with `pyssg build`, which writes to `public/` (the default
`Config.out`). Adjust the `pyssg[plugins]` extra to match your project's
dependencies.

## Before you deploy

1. **Serve from the domain root.** pyssg emits root-absolute links (`/blog/`,
   `/style.css`), so the site must live at the root of a domain. A custom
   domain, a `<user>.github.io` user/org site, a Netlify subdomain or a
   `*.pages.dev` subdomain all qualify. A GitHub Pages **project site** at
   `user.github.io/<repo>/` serves from a subpath and is **not yet supported**
   -- that needs a `base_url` feature (tracked separately in `ROADMAP.md`).

2. **Set a canonical site URL.** The Sitemap and RSS plugins emit absolute URLs
   only when `base_url` is set in your config options:

   ```python
   Config(..., options={"base_url": "https://your-domain.example"})
   ```

## Quick start

- **GitHub Pages** -- copy `github-pages/deploy.yml` to
  `.github/workflows/deploy.yml` and `github-pages/.nojekyll` to your project
  root. In the repo, set Settings -> Pages -> Source to "GitHub Actions". Push
  to `main`.
- **Netlify** -- copy `netlify/netlify.toml` to your project root and connect
  the repo in Netlify. The publish directory and build command come from the
  file.
- **Cloudflare Pages** -- create a Pages project, set the build command to
  `pip install "pyssg[plugins]" && pyssg build`, the output directory to
  `public`, and the env var `PYTHON_VERSION=3.13`. Or use the optional
  `cloudflare-pages/deploy.yml` workflow.

## Manifest schema (`deploy.toml`)

Each target carries a static manifest -- the single source of truth a future
deploy plugin reads. It is plain data (parsed with `tomllib`); no code runs.

```toml
[target]
name        = "github-pages"   # stable id
title       = "GitHub Pages"   # human label
homepage    = "https://..."    # docs link
publish_dir = "public"         # must equal Config.out
root_served_only = true        # true until base_url supports subpaths

[[project_files]]              # written once into the project (repo root)
path   = ".github/workflows/deploy.yml"
source = "deploy.yml"          # file in this folder to copy

[[output_files]]               # emitted into the build output every build
path    = ".nojekyll"
content = ""                   # inline content
```

## Future: a deploy plugin

The two file categories map cleanly onto the two ways pyssg already distributes
things, so each target can graduate into a plugin without changing the data:

- `output_files` -> a `DeployPlugin(target="github-pages")` taps the `generate`
  hook and appends each entry as an `Output`, so `.nojekyll`, `_redirects` or
  `_headers` are written on every build.
- `project_files` -> a `pyssg deploy init <target>` command copies these into
  the project once, the same way `pyssg new` vendors a theme.

Because the manifest is the contract, adding a new platform is just a new folder
with a `deploy.toml`; the plugin and the init command need no per-platform code.
