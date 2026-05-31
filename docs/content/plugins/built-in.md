---
title: Built-in plugins
order: 1
---

# Built-in plugins

## Tier 1 - Markdown to HTML

| Plugin | Hook | Dependency | Purpose |
|--------|------|------------|---------|
| `ReadFile` | `discover`, `load` | stdlib | Find source files and read their raw content. |
| `Frontmatter` | `parse` | pyyaml | Split the `---` block and parse it as YAML. |
| `Markdown` | `transform` | `markdown` | Render the body to HTML. |
| `Template` | `render` | `jinja2` | Wrap content in a Jinja2 layout, emit an Output. |
| `WriteFile` | `emit` | stdlib | Write outputs to the `out` directory. |
| `StaticFiles` | `emit` | stdlib | Copy a directory of assets (CSS/JS/images) into the output. |

### ReadFile

```python
ReadFile(patterns=("*.md", "*.markdown"))
```

Walks `src`, collecting matching files as `Source` objects, then reads each
one's raw text.

### Frontmatter

Parses a leading `---` block as YAML with PyYAML (`yaml.safe_load`), so the full
YAML spec is supported. Parse errors carry a precise `file:line:column` mark that
the CLI prints cleanly and `pyssg serve` renders as an overlay. Requires the
`pyssg[frontmatter]` extra.

### Markdown

```python
Markdown(extensions=["fenced_code", "tables"])
```

Renders `body` to `content` using python-markdown. Extensions are passed
through.

### Template

```python
Template(directory="layouts", default_layout="default.html", partials_dir="partials")
```

Renders each page with Jinja2 and emits an `Output`. The template is chosen by a
[lookup cascade](/templating/lookup-cascade/) (frontmatter `layout` wins, then
`type`/`section`/`_default` by `kind`). Supports native
[inheritance](/templating/inheritance/) and a [`partial()`](/templating/partials/)
function. Templates receive `content`, `page`, `partial`, and every key of
`build.meta` (`site`, `collections`, `menus`). See the
[Templating](/templating/) section for the full story.

### WriteFile

```python
WriteFile(clean=True)
```

Writes every `Output`. With `clean=True` the output directory is emptied first.

### StaticFiles

```python
StaticFiles(directory="assets", dest="assets")
```

Copies every file under `directory` into `out/dest`, preserving the subtree. It
runs after `WriteFile`, so it survives a clean build. Use it for CSS, JS, images
and anything served verbatim.

### Fingerprint

```python
Fingerprint(directory="assets", dest="assets", extensions=(".css", ".js"))
```

Content-hashes assets for cache-busting: `style.css` becomes
`style.<hash>.css`, and the reference is rewritten everywhere so browsers can
cache each file forever yet fetch a new one the moment its content changes.

It owns the asset directory end to end, so use it **instead of** `StaticFiles`
for that directory: files matching `extensions` are emitted under their hashed
name; everything else is copied verbatim. References are resolved two ways:

- automatically, by rewriting the logical URL (`/assets/style.css`) to the
  hashed URL in every HTML output -- including `og:image`/canonical tags from
  the Seo plugin, so nothing else needs to know the hash;
- explicitly, via an `asset()` template global: `{{ asset('/assets/style.css')
  }}` returns the hashed URL (unknown paths pass through unchanged).

Only references inside HTML are rewritten; `url(...)` inside CSS is left alone.
The default `.css`/`.js` set avoids the case where a fingerprinted image is
referenced from CSS and would otherwise break. This plugin is opt-in: add
`Fingerprint()` to your `pyssg.config.py` plugin list.

## Tier 2 - flexible structure

| Plugin | Hook (stage) | Purpose |
|--------|--------------|---------|
| `Permalink` | `collect` (-200) | Decide each page's URL and output path. |
| `Collections` | `collect` (-100) | Group pages by tag, folder or a predicate. |
| `Listing` | `collect` (0) | Turn a collection into one or more list pages. |
| `Navigation` | `collect` (100) | Build named menus and prev/next links. |

### Permalink

```python
Permalink()                              # pretty URLs: foo.md -> /foo/
Permalink(pattern="/blog/:year/:slug/")  # pattern-based
Permalink(pretty=False)                  # foo.md -> /foo.html
```

Per-page override via frontmatter: `permalink: /custom/path/`. Placeholders
include `:slug`, `:year`, `:month`, `:day`, `:title` and any frontmatter key.

### Collections

```python
Collections(by_tag=True, by_folder=True)
Collections(custom={"featured": lambda s: s.frontmatter.get("featured")})
```

Builds `build.meta["collections"]`: a dict of named, ordered groups. Sorting is
`auto` by default (by date when present, otherwise by `order` then title).

### Listing

```python
Listing(collection="blog", base_url="/blog/", title="Blog", page_size=10)
Listing(kind="tag", base_url="/tags/:name/", title=":name")
```

Turns a collection into list page(s). Pagination is just the `page_size` option.
Templates receive `page.entries` (the page refs) and, when paginated,
`page.paginator`.

### Navigation

```python
Navigation(mode="folder", sequential=True)   # docs sidebar + prev/next
Navigation(mode="frontmatter")               # pages declaring `menu: main`
Navigation(items=[...])                       # explicit tree from config
```

Writes `build.meta["menus"][name]` as a tree of nav nodes. With
`sequential=True` it also links adjacent pages via `page.prev` / `page.next`.

## Tier 3 - output and optimization

These plugins produce extra files or post-process the built output. All are
standard-library only.

| Plugin | Hook | Purpose |
|--------|------|---------|
| `Sitemap` | `generate` | Emit a `sitemap.xml` of every public page. |
| `Rss` | `generate` | Emit an RSS 2.0 feed from a collection. |
| `Robots` | `generate` | Emit a `robots.txt` with a `Sitemap:` directive. |
| `Redirects` | `generate` | Keep old URLs alive after a page moves. |
| `Minify` | `optimize` | Shrink HTML outputs, preserving `pre`/`code`/`script`. |

### Sitemap

```python
Sitemap(path="sitemap.xml")
```

Adds one `<url>` entry per public page (one with a URL, not a draft). Absolute
locations use `site["base_url"]`; without it, root-relative URLs are emitted.
Frontmatter `date` becomes `<lastmod>`.

### Rss

```python
Rss(collection="blog", path="feed.xml", title="My Blog", limit=20)
```

Turns the newest `limit` pages of a collection into an RSS 2.0 feed. Channel
metadata defaults to `site` options (`title`, `tagline`, `base_url`); item
`pubDate` comes from frontmatter `date`, and `description` from `description` or
`summary`. Does nothing if the collection does not exist.

### Robots

```python
Robots(disallow=["/private/"], sitemap=True)
```

Emits a `robots.txt`. By default it allows every crawler and, when a
`site["base_url"]` is set, appends an absolute `Sitemap:` directive. Setting
`site["private"] = True` flips the whole file to "disallow everything" -- a
one-switch guard for staging deploys. Use `groups=[{user_agent, allow,
disallow}]` for per-user-agent rules.

### Redirects

```python
Redirects(
    rules={"/old-path/": "/new-path/"},   # explicit, for non-page targets
    emit_redirects_file=False,            # also emit a Netlify/CF _redirects
)
```

Keeps old URLs working after a page moves. Redirects come from two sources,
frontmatter winning ties:

1. a page's frontmatter `aliases` (its former URLs):

   ```yaml
   ---
   title: New home
   aliases: [/old-home/, /2020/intro/]
   ---
   ```

2. explicit `rules` for targets that are not a built page (an external URL, a
   deleted page).

By default it writes one tiny HTML meta-refresh page per old URL -- portable to
any static host, including GitHub Pages. Each page carries a `<meta
http-equiv="refresh">`, a canonical link (absolute when `site["base_url"]` is
set) and a script fallback. Set `emit_redirects_file=True` to also emit a
`_redirects` manifest for true server-side 3xx responses on Netlify and
Cloudflare Pages (`status=301` by default). A redirect whose path collides with
a real built page is dropped with a warning, so the page always wins.

This plugin is opt-in: add `Redirects()` to your `pyssg.config.py` plugin list.

### Minify

```python
Minify(suffixes=(".html", ".htm"))
```

Collapses redundant whitespace and removes comments in matching outputs. It is
conservative: the content of `pre`, `code`, `textarea`, `script` and `style` is
left untouched, and IE conditional comments are kept.

### MarkdownPage

```python
MarkdownPage(
    llms_txt=True,             # also emit an /llms.txt index
    html_link=True,            # inject a <link rel="alternate"> hint
    include_title=False,       # prepend "# <title>" if the body has no heading
    include_frontmatter=False, # prepend the original frontmatter block
)
```

Serves a raw-markdown twin of every page so AI agents can read the source
instead of parsing rendered HTML. Three complementary layers, each toggleable:

1. A per-page `.md` companion, following the "append `.md` to the URL"
   convention: `/guide/intro/` is also served at `/guide/intro.md`, and the home
   page `/` at `/index.md`.
2. An `llms.txt` index at the site root ([llmstxt.org](https://llmstxt.org)):
   one markdown file listing every page and linking to its `.md` twin. Links are
   absolute when `site["base_url"]` is set.
3. A `<link rel="alternate" type="text/markdown">` hint injected into each
   page's `<head>`, so an agent that landed on the HTML can find the twin.

The companion's contents are `source.body` only by default; opt into
`include_title` and/or `include_frontmatter` to enrich it. Synthetic listing
pages and drafts are skipped (they have no authored markdown).

## Enabling tier 3 via presets

Every preset accepts `sitemap=True` / `minify=True` / `markdown_pages=True`, and
`blog()` generates an RSS feed by default (`rss=True`). See
[Presets](/plugins/presets/).

## Tooling

### Statistics

```python
Statistics(top_n=5, by_type=True, json_path=None)
```

Prints a build summary after every artifact is written: source counts (with the
number of derived/generated pages), total file count and size, a breakdown by
file type, and the largest files. The numbers are hybrid - logical counts come
from the in-memory build, while file sizes and types are read from disk under
`out`, so static assets copied by `StaticFiles` are included too.

```text
Build summary
  Sources:  17
  Files:    19    Total: 89.5 KB    Build: 124 ms
  By type:
    .html    17     84.6 KB
    .css      1      3.5 KB
    .xml      1      1.4 KB
  Largest:
    plugins/built-in/index.html   10.5 KB
    ...
```

It is opt-in: add `Statistics()` to your `config.plugins`. When enabled it
replaces the default one-line build message. It stays silent under `pyssg serve`
to avoid spamming the rebuild loop.

Pass `json_path` to also write the report as JSON (useful in CI to track build
size over time):

```python
Statistics(json_path="public/_stats.json")
```
