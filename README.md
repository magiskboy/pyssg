# pyssg

Static site generator cho Markdown, kiến trúc lấy cảm hứng từ Webpack: xử lý dạng
**hook**, dữ liệu dạng **dependency graph**, và **incremental build** là tính năng
trung tâm. Lõi (`pyssg.core`) thuần stdlib; mọi thư viện third-party nằm ở plugin
ngoại vi. Hợp cho ba use case: **docs**, **blog**, **wiki/knowledge base lớn**.

> Tài liệu thiết kế đầy đủ: [`docs/content/technical-spec-v0.1.0.md`](docs/content/technical-spec-v0.1.0.md).
> Báo cáo hành vi incremental đo trên site thật: [`examples/INCREMENTAL_REPORT.md`](examples/INCREMENTAL_REPORT.md).

---

## 1. Cài đặt

Yêu cầu: **Python 3.13** và **[uv](https://github.com/astral-sh/uv)** (công cụ quản lý
môi trường + gói của dự án). Mọi lệnh chạy qua `uv run`, dùng virtualenv `.venv`.

```bash
git clone <repo> pyssg && cd pyssg
uv sync                      # tạo .venv (Python 3.13) + cài dependencies
uv run python -m pyssg --help
```

CLI gọi bằng `uv run python -m pyssg ...` (hoặc `uv run pyssg ...` sau khi cài như
package).

---

## 2. Bắt đầu nhanh

Cách nhanh nhất là dùng **preset** — một hàm trả về `Config` hoàn chỉnh (đã gói sẵn
plugin đúng thứ tự + theme mặc định). Không cần biết plugin nào hay cách xếp thứ tự.

```bash
uv run python -m pyssg --site my-site init --preset docs   # hoặc: --preset blog
uv run python -m pyssg --site my-site build                # build full -> my-site/dist
uv run python -m pyssg --site my-site serve                # watch + incremental + live-reload
```

`init` tạo sẵn `pyssg.config.py` một dòng + nội dung mẫu. Toàn bộ file config chỉ là:

```python
from __future__ import annotations
from pyssg.presets import docs        # hoặc: from pyssg.presets import blog
config = docs(site={"title": "My Docs"}, base_url="https://example.com")
```

- **docs** — site tài liệu: nav theo thư mục, taxonomy, wikilink/transclude, RSS, sitemap.
- **blog** — blog: bài viết trong `content/posts/`, liệt kê mới-nhất-trước + **phân trang**
  (trang chủ `/`, trang 2 tại `/page/2/`), RSS.

Mở http://127.0.0.1:8000 — sửa file trong `content/` là trang tự build lại và reload.

Tuỳ biến preset mà vẫn giữ mặc định (truyền `extra_plugins` để thêm plugin của bạn,
chúng chạy sau cùng):

```python
config = docs(
    site={"title": "My Docs"},
    highlight_style="friendly",
    extra_plugins=[...],
)
```

### Built-in theme & eject

Preset dùng **theme đóng gói sẵn** (`docs`, `blog`). Muốn sửa template/CSS, copy theme
ra site rồi trỏ `layout=` vào bản copy:

```bash
uv run python -m pyssg --site my-site eject-layout --theme docs --to layouts/docs
# rồi trong config:  config = docs(..., layout="layouts/docs")
```

### Cấu hình thủ công (nâng cao)

Không dùng preset thì tự dựng `Config`: tự chọn & xếp plugin + gói layout riêng. Một site
khi đó là thư mục gồm `pyssg.config.py`, `content/`, và một **gói layout** (`layout.toml`
+ `templates/` với `base/page/term/terms.html.j2` + `assets/`).

<details>
<summary>Ví dụ <code>Config</code> đầy đủ</summary>

```python
from __future__ import annotations
from pyssg import Config
from pyssg.plugins import (
    directory_loader, frontmatter, markdown, mermaid, highlight,
    content_meta, permalink, wikilink, link_resolver, transclude,
    nav, taxonomy, sitemap, rss, asset_copy, render,
)

config = Config(
    content_dir="content",
    output_dir="dist",
    layout="layout",
    base_url="https://example.com",
    site={"title": "My Site"},          # biến tuỳ ý cho template (site.*)
    plugins=[                            # thứ tự = thứ tự apply
        directory_loader(), frontmatter(), markdown(),
        mermaid(), highlight(style="friendly"), content_meta(),
        permalink(), wikilink(), link_resolver(), transclude(),
        nav(), taxonomy(), sitemap(), rss(title="My Site"),
        asset_copy(), render(),
    ],
)
```

Plugin cộng đồng đặt ở `pyssg/contrib/<name>.py` (vd `external_links`); import tường minh
`from pyssg.contrib.external_links import external_links` rồi đưa vào `plugins`/`extra_plugins`.
</details>

---

## 3. CLI

| Lệnh | Mô tả |
|---|---|
| `pyssg init --preset docs\|blog` | Scaffold site mới cho preset (config + nội dung mẫu). `--force` để ghi đè config. |
| `pyssg build` | Build full ra `output_dir`. |
| `pyssg build --no-cache` | Bỏ qua cache bền (`.pyssg-cache/`). |
| `pyssg build --profile` | In số node tái tính theo phase + cache hits. |
| `pyssg serve` | Watch (watchdog native) + incremental rebuild + dev server + live-reload. In thời gian và số node tái tính mỗi lần rebuild. |
| `pyssg serve --port 9000 --no-cache` | Đổi cổng / tắt cache. |
| `pyssg clean` | Xoá `output_dir` + cache (hỏi xác nhận; `--yes` để bỏ qua). |
| `pyssg eject-layout --theme docs\|blog --to DIR` | Copy theme đóng gói sẵn ra site để tuỳ biến. |

`--site PATH` chọn thư mục site (mặc định `.`).

---

## 4. Viết nội dung

### Frontmatter (YAML)

```markdown
---
title: Cài đặt
nav_title: Setup           # tên hiển thị ở sidebar (tuỳ chọn)
order: 1                   # thứ tự trong sidebar/nav
tags: [python, ssg]
category: guides/advanced  # category phân cấp (sinh cả "guides" và "guides/advanced")
date: 2026-05-29
draft: false               # draft: true -> không sinh trang
permalink: /custom/url/    # ghi đè URL mặc định (tuỳ chọn)
---
```

- **Title** tự suy ra nếu thiếu: frontmatter `title` → heading `#` đầu → tên file.
- **URL mặc định** theo đường dẫn file: `content/guide/intro.md` → `/guide/intro/`;
  `index.md` → thư mục gốc của nó.

### Markdown phong phú

| Cú pháp | Kết quả |
|---|---|
| ` ```python ... ``` ` | Code highlight bằng Pygments (CSS nhúng qua `site.highlight_css`). |
| ` ```mermaid ... ``` ` | Sơ đồ Mermaid client-side (layout nạp `mermaid.js` khi có sơ đồ). |
| `[text](./other.md)` | Link nội bộ — tự rewrite sang URL đã giải; sinh **backlink**. |
| `[[Note]]`, `[[Note\|hiển thị]]`, `[[Note#Heading]]` | Wikilink kiểu Obsidian (giải theo tên file/tiêu đề); link gãy ⇒ `<span class="broken-link">`. |
| `![[Note]]` | Transclusion: nhúng nội dung Note (đệ quy, có phát hiện chu trình). |
| `#tag` trong frontmatter `tags` | Sinh trang `/tags/<tag>/` + chỉ mục `/tags/`. |

### Taxonomy (tag + category) — zero-config

Chỉ cần viết `tags:` / `category:` trong frontmatter. Tự có ngay `/tags/python/`,
`/tags/`, `/categories/guides/`, `/categories/guides/advanced/`. Thêm chiều phân loại
mới = cấu hình, không sửa engine:

```python
from pyssg.plugins.taxonomy import taxonomy, tag, category, Taxonomy
taxonomy(tag(), category(), Taxonomy("series", "series", "/series/", ("series",)))
```

---

## 5. Layout & template

Plugin `render` (Jinja2) render mỗi trang với **context** sau (template chỉ cần học chừng này):

| Biến | Nội dung |
|---|---|
| `page` | meta của trang + `page.url`, `page.title`, `page.tags`, ... |
| `site` | `Config.site` + `site.base_url` (+ `site.highlight_css` nếu bật highlight) |
| `content_html` | HTML thân bài (đã highlight, đã giải link/wikilink/embed) |
| `menu` | sidebar: danh sách `{section, items:[{url,title}]}` |
| `breadcrumbs` | `[{title,url}, ...]` theo đường dẫn |
| `prev` / `next` | trang liền kề trong thứ tự nav |
| `backlinks` | `[{title,url}]` các trang trỏ tới trang này |
| `toc` | mục lục: `[{level,text,slug}]` |
| `tags`, `all_tags` | tag của trang / mọi tag (cho tag cloud) |
| `reading_time`, `excerpt`, `word_count` | sinh bởi `content_meta` |

Template tối thiểu (`page.html.j2`):

```jinja
{% extends "base.html.j2" %}
{% block content %}
<nav>{% for c in breadcrumbs %}<a href="{{ c.url }}">{{ c.title }}</a>{% endfor %}</nav>
<article><h1>{{ page.title }}</h1>{{ content_html }}</article>
{% if next %}<a href="{{ next.url }}">{{ next.title }} →</a>{% endif %}
{% endblock %}
```

`base.html.j2` thường nhúng CSS highlight và script mermaid có điều kiện:

```jinja
{% if site.highlight_css %}<style>{{ site.highlight_css }}</style>{% endif %}
...
{% if '<pre class="mermaid"' in content_html %}
<script type="module">import mermaid from "https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs"; mermaid.initialize({startOnLoad:true});</script>
{% endif %}
```

Override template từng trang qua frontmatter `template: special.html.j2`.

Assets (CSS/JS/font) đặt ở `layout/assets/` — plugin `asset_copy` copy sang `dist/assets/`.

---

## 6. Plugin built-in

| Plugin | Vai trò |
|---|---|
| `directory_loader` | Quét `content/` → node + cạnh CONTAINMENT |
| `frontmatter` | Tách YAML frontmatter |
| `markdown` | Parse `.md` → HTML + suy ra title |
| `mermaid` | Khối ` ```mermaid ` → client-side `<pre class="mermaid">` |
| `highlight` | Highlight code (Pygments); `highlight(style=...)` |
| `content_meta` | TOC, reading time, excerpt, word count |
| `permalink` | Sinh trang + URL (file-based / override); gate `draft` |
| `wikilink` | `[[...]]` → link + backlink |
| `link_resolver` | Rewrite `[](./x.md)` + backlink |
| `transclude` | `![[...]]` embed + phát hiện chu trình |
| `nav` | Sidebar / breadcrumbs / prev-next |
| `taxonomy` | tag + category (phân cấp) zero-config |
| `sitemap` | `/sitemap.xml` |
| `rss` | `/feed.xml`; `rss(title=...)` |
| `asset_copy` | Copy assets layout |
| `render` | Render Jinja2 (terminal) |

Viết plugin riêng: một class có `name`, `cache_version`, và `apply(builder)` tap vào
hook (xem `pyssg/plugins/*.py` làm mẫu, và SPEC §5/§7/§9).

---

## 7. Incremental & watch

Khi `serve`, mỗi lần lưu file engine **chỉ tái tính phần đổi**:

- Sửa nội dung một file ⇒ thường **chỉ 1 trang** được phát lại (early-cutoff); các
  trang khác lấy từ render cache.
- Thêm/xoá/đổi tên ⇒ lan đúng phạm vi (sidebar nav xuất hiện mọi trang nên đổi cấu
  trúc sẽ phát lại nhiều trang — đúng như build full).
- **Bất biến cốt lõi:** kết quả incremental luôn **byte-identical** với build từ đầu
  (kiểm bằng property test trên cả fixture lẫn site thật). Live-reload đẩy đúng tập
  URL đổi (lấy từ early-cutoff).

Cache bền ở `.pyssg-cache/` giúp lần build sau (kể cả tiến trình mới) nhanh hơn.

---

## 8. Site ví dụ

- `examples/docs` — site tài liệu song ngữ (en/vi): nav theo cây, breadcrumbs,
  next/prev, code highlight, tag/category.
- `examples/wiki` — knowledge base (~117 note): tags dày, backlink, mermaid, highlight.

```bash
uv run python -m pyssg --site examples/docs serve
uv run python -m benchmarks --quick             # benchmark incremental + sinh báo cáo (xem benchmarks/README.md)
```

---

## 9. Phát triển

```bash
uv run mypy --strict pyssg     # zero error là điều kiện merge
uv run ruff check pyssg tests
uv run python -m unittest discover -s tests -t .   # gồm test bất biến: incremental==full, boundary, determinism
```

Quy ước đóng góp ở [`CLAUDE.md`](CLAUDE.md); tiến trình ở [`TRACK.md`](TRACK.md).
