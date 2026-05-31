---
title: Deploy
order: 4
---

# Deploy

A pyssg build is a plain folder of static files (`public/` by default), so it
hosts anywhere. This guide covers ready-made recipes for the three most common
free platforms. Copy-paste configurations live in
[`recipes/deploy/`](https://github.com/your-org/pyssg/tree/main/recipes/deploy).

## Two things to check first

**Serve from the domain root.** pyssg emits root-absolute links (`/blog/`,
`/style.css`), so the site must live at the root of a domain. A custom domain, a
`<user>.github.io` user/org site, a Netlify subdomain and a `*.pages.dev`
subdomain all qualify. A GitHub Pages **project site** at
`user.github.io/<repo>/` serves from a subpath and is not yet supported -- that
needs a `base_url` feature, tracked in the roadmap.

**Set a canonical site URL** so the Sitemap and RSS plugins emit absolute URLs:

```python
Config(..., options={"base_url": "https://your-domain.example"})
```

## GitHub Pages

1. Copy `recipes/deploy/github-pages/deploy.yml` to
   `.github/workflows/deploy.yml`.
2. Copy `recipes/deploy/github-pages/.nojekyll` to your project root (it stops
   GitHub from running the output through Jekyll).
3. In the repo, set **Settings -> Pages -> Source** to "GitHub Actions".
4. Push to `main`. The workflow builds with uv and publishes the artifact:

```yaml
- uses: astral-sh/setup-uv@v5
- run: uv run --python 3.13 --with "pyssg[plugins]" pyssg build
- uses: actions/upload-pages-artifact@v3
  with:
    path: public
```

For a custom domain, add a `CNAME` file containing your domain to `public/`
(for example with a `StaticFiles` entry).

## Netlify

Copy `recipes/deploy/netlify/netlify.toml` to your project root and connect the
repository in Netlify. Netlify images ship Python but not uv, so the build uses
pip:

```toml
[build]
  command = "pip install 'pyssg[plugins]' && pyssg build"
  publish = "public"

[build.environment]
  PYTHON_VERSION = "3.13"
```

## Cloudflare Pages

Create a Pages project from your repository and set:

- **Build command:** `pip install "pyssg[plugins]" && pyssg build`
- **Build output directory:** `public`
- **Environment variable:** `PYTHON_VERSION = 3.13`

Prefer CI-driven deploys? Use `recipes/deploy/cloudflare-pages/deploy.yml`,
which builds in GitHub Actions and uploads with Wrangler (needs the
`CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID` secrets).

## Other hosts

Any static host works: build locally with `pyssg build` and upload `public/`.
The recipes above are described by a small `deploy.toml` manifest per target, so
new platforms are easy to add -- see the
[recipes README](https://github.com/your-org/pyssg/tree/main/recipes/deploy).
