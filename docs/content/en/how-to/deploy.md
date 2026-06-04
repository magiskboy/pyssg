---
title: Deploy a built site
nav_title: Deploy
order: 6
---

# Deploy a built site

**Goal:** publish the static output produced by `build`.

## 1. Produce a clean build

```bash
pyssg --site my-site build
```

Everything to deploy is now in the output directory (`dist/` by default; set
`output_dir` in your config to change it). The output is a plain tree of HTML,
CSS, and assets - no server runtime is required.

## 2. Set `base_url`

If your site is served from a subpath (for example a GitHub Pages project site at
`https://user.github.io/repo`), set `base_url` so generated absolute URLs - the
sitemap, RSS feed, and `hreflang` tags - are correct:

```python
config = docs(
    site={"title": "My Docs"},
    base_url="https://user.github.io/repo",
)
```

## 3. Deploy with `pyssg deploy`

PySSG ships a built-in deploy command for the common hosts. Declare per-target
options under `Config.deploy` (keyed by target name), then run
`pyssg deploy <target>`. The command builds the site, uploads the output, and
records the result so a re-run with byte-identical output is a no-op.

```python
config = docs(
    site={"title": "My Docs"},
    base_url="https://user.github.io",
    deploy={
        # GitHub Pages: pushes dist/ to a content branch. Auth via the `gh` CLI
        # or a GITHUB_TOKEN in the environment.
        "github-pages": {"repo": "user/repo"},  # plus optional branch, cname, ...
        # Cloudflare Pages: auth via the CLOUDFLARE_API_TOKEN environment variable.
        "cloudflare": {"account_id": "...", "project": "my-site"},
        # Netlify: auth via the NETLIFY_AUTH_TOKEN environment variable.
        "netlify": {"site_id": "..."},
    },
)
```

Credentials are always read from the environment, never from the config file.
Then deploy:

```bash
pyssg --site my-site deploy list           # configured targets + whether each is implemented
pyssg --site my-site deploy github-pages   # build and publish
pyssg --site my-site deploy status         # last-deploy record per target
```

Each target subcommand accepts `--dry-run` (validate and report what would be
uploaded, without pushing), `--force` (redeploy even if the output is unchanged),
`--skip-build` (reuse the existing output directory), and `--skip-check` (skip
the post-build sanity check). See the [CLI reference](../reference/cli.md) for
the full surface.

The built-in targets publish from the domain root (a user/org GitHub Pages site
or a custom domain), so keep `base_url` at the root - a project site served from
a `/repo/` subpath is not yet supported by these targets; deploy it manually
instead.

## 4. Or upload `dist/` manually

For a host without a built-in target, point it at the output directory yourself.
A few common targets:

- **GitHub Pages** - push the `dist/` contents to the `gh-pages` branch, or use a
  Pages action that uploads the directory as the artifact.
- **Netlify / Cloudflare Pages / Vercel** - set the build command to
  `pyssg --site my-site build` and the publish directory to
  `my-site/dist`.
- **Any web server / object storage** - copy `dist/` to the document root or
  bucket.

## 5. Keep builds reproducible in CI

PySSG builds are deterministic: given the same inputs, two builds produce
byte-identical output. In CI, run a full `build` (the cache is an optimization,
not a correctness requirement) - pass `--no-cache` if you want to prove a clean
build from scratch:

```bash
pyssg --site my-site build --no-cache
```

To remove the output directory and cache locally, use `clean`:

```bash
pyssg --site my-site clean --yes
```
