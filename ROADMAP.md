# Lộ trình hướng tới bản phát hành hoàn thiện

Tài liệu này theo dõi các hướng đưa pyssg từ "chạy được" lên "dùng thật được"
cho người dùng kỹ thuật. Cập nhật khi một hạng mục đổi trạng thái.

Trạng thái: `[ ]` chưa làm · `[~]` đang làm · `[x]` xong. Task đã xong được gỡ
khỏi danh sách và tóm tắt một dòng trong "Đã có"; chi tiết quyết định nằm trong
code + git history.

## Khung tư duy

Người dùng kỹ thuật đánh giá một SSG qua hai trục:

1. **Thời gian từ 0 đến site deploy được** (onboarding/DX).
2. **Output có production-grade không** (fingerprint, syntax highlight, SEO, search, feed, tốc độ).

Trục ngầm cho hệ sinh thái: **cơ chế đóng gói & nạp plugin/theme bên thứ ba** —
không có thì hệ sinh thái không tồn tại được về mặt kỹ thuật.

## Đã có (nền tảng)

Lõi:

- Kernel 0-dependency + 3 tầng plugin (read/parse/markdown/template/write, permalink/collections/listing/navigation, sitemap/rss/minify/static).
- `pyssg build` + `pyssg serve` (watch + live reload).
- Statistics plugin, presets `docs()` / `blog()` / `site()`, docs site build bằng chính pyssg.
- Template: lookup cascade kiểu Hugo + `partial()`.

Đã hoàn thành (tính tới 2026-05-31):

- **A. Onboarding/DX** — `pyssg new` (scaffolding + embedded theme docs/blog offline + fetch GitHub tarball); thông báo lỗi + build error overlay kèm `file:line`; validate `Config`/frontmatter sớm (schema registry); công thức deploy GitHub Pages / Netlify / Cloudflare Pages.
- **B. Soạn thảo** — syntax highlighting (`Highlight` plugin, Pygments build-time, sinh CSS inline qua global `highlight_css()`, dark mode).
- **C. Output** — markdown page (bản `.md` gốc cho AI); asset fingerprint/cache-busting; SEO/meta (Open Graph, Twitter, canonical, JSON-LD); `robots.txt` + redirects.
- **D. Theme** — fetch & vendor tarball bằng stdlib (không cần git); cú pháp `owner/repo[/path][@tag]` + embedded offline-first; mô hình hybrid; manifest `theme.toml`; sinh `pyssg.config.py` từ preset; folder official `themes/`.

---

## B. Sức mạnh soạn thảo nội dung

- [ ] **Data files** — nạp `data/*.toml|json|yaml` vào `build.meta` cho template. (1.0)
- [ ] **Shortcodes / admonitions** — callout (note/warning/tip), embed (youtube/gist), tab group.
- [ ] **TOC per-page** + reading time / word count.
- [ ] **Internal link resolution** — link theo đường dẫn nguồn -> permalink; báo link gãy.
- [ ] **Obsidian wikilink/backlink `[[...]]`** — plugin tự render `[[...]]` thành link markdown
      chính thống TRƯỚC khi các plugin convert ra HTML chạy. (1.1)
      **Đề xuất (chưa chốt):**
      - **Vị trí trong lifecycle:** tap `transform` ở **stage < 0** (trước Markdown stage 0) để
        viết lại `source.body` từ `[[Target|alias]]` / `[[Target#heading]]` thành `[alias](url)`
        markdown chuẩn; Markdown sau đó convert như bình thường. (Permalink đã gán URL ở `collect`
        nên URL đích sẵn có lúc `transform`.)
      - **Phân giải đích:** dựng index build-wide ở `collect` map tên note (stem filename, có thể cả
        `title`) -> URL; hỗ trợ `#heading` (slug hoá), `|alias`, và embed `![[...]]` (ảnh/transclude)
        để sau. Trùng tên -> warn + chọn deterministic.
      - **Link gãy:** không phân giải được -> `warn()` kèm `file:line` (phát hiện sớm), render fallback
        text hoặc span đánh dấu broken thay vì crash. **Dùng chung index/cơ chế báo gãy với
        [Internal link resolution] và phần lint dưới đây** (gộp một nguồn sự thật).
      - **Backlink ngược (mục "X liên kết tới đây"):** từ index có thể sinh thêm `source.meta`
        backlinks cho template hiển thị — cân nhắc tách giai đoạn sau wikilink cơ bản.
      - stdlib-only (regex), opt-in thủ công như các plugin tình huống.
- [ ] **Markdown lint/validate** — plugin kiểm tra file markdown đúng các quy tắc đặt ra, phát hiện
      lỗi sớm ngay ở bước build; điểm nhấn: **bắt internal link / wikilink gãy sớm**. (1.1)
      **Đề xuất (chưa chốt):**
      - **Tham khảo chuẩn:** [markdownlint](https://github.com/DavidAnson/markdownlint) (60 rule
        MD001–MD059, mỗi rule có alias kiểu `line-length` + gom theo tag `headings`/`line_length`)
        và remark-lint. **Tự viết bộ rule tối giản bằng stdlib/regex** (tuân thủ "hạn chế thư viện
        bên thứ 3", không kéo Node), chọn lọc tập rule giá trị cao thay vì port đủ 60.
      - **Tập rule khởi điểm:** heading tăng đúng 1 cấp (MD001), không trùng heading, fenced code
        phải khai ngôn ngữ, list indentation nhất quán, trailing whitespace, dòng quá dài (opt, tắt
        mặc định), và **link nội bộ/wikilink gãy** (killer feature — dùng index của Permalink +
        wikilink ở trên).
      - **Vị trí:** rule style chạy trên `source.body` ở `parse`; rule link-check cần index URL nên
        chạy sau `collect`/`render`. Báo lỗi kèm `file:line` (tái dùng `SourceLocation`).
      - **Severity:** mặc định **warn** (không chặn build), cờ `strict=True` / `--strict` -> nâng
        thành `BuildError` fail build (hợp CI). Per-rule enable/disable + severity qua config.
      - **Quan hệ:** bổ trợ "Validate Config/frontmatter sớm" (mục A) ở tầng nội dung; chia sẻ
        cơ chế báo link gãy với 2 mục trên. opt-in thủ công.
      - **Đóng gói (chốt):** viết thành **package riêng `src/pyssg_lint`** (KHÔNG bỏ vào
        `pyssg_plugins` built-in), phân phối/cài độc lập. Phù hợp khung mục D (add-on tách khỏi
        kernel): import path thuần trong `pyssg.config.py`, có pyproject/extra riêng. Tên/versioning
        chốt khi triển khai.

## C. Chất lượng output production

- [ ] **Search client-side** — sinh index JSON + widget nhỏ (kiểu pagefind/lunr tối giản). (1.0 hoặc 1.1)
- [ ] **Feeds mở rộng** — JSON Feed + Atom; per-tag feed.
- [ ] **Incremental build** — để 1.1+ (đụng kiến trúc phased passes + cache).

## D. Khả năng mở rộng & hệ sinh thái (nền tảng)

Nguyên tắc chốt (2026-05-30): **plugin và theme là hai cơ chế phân phối khác nhau** —
plugin là code Python (qua package/import), theme là bó file tĩnh (qua fetch & vendor).
Cơ chế **theme** (fetch & vendor + `theme.toml`) đã xong (xem "Đã có"); phần còn lại là **plugin**.

### Plugin = phân phối qua package
- [ ] **Nạp plugin = `import` Python thuần** trong `pyssg.config.py` (chọn import path,
      KHÔNG dùng entry points). User `uv add` package rồi import.
- [ ] **Official → PyPI qua CI** (versioning). **Third-party → GitHub** qua `uv pip install "git+https://..."`.
- [ ] **Monorepo**: `src/plugins/<plugin>` -> mỗi folder 1 package, CI auto-build.
      Quyết định CI để sau: tên package (vd `pyssg-<plugin>`), versioning chung/độc lập, optional-deps.
- [ ] **Phân định** built-in (trong `src/pyssg/plugins/`, ship cùng kernel, presets cần) vs
      add-on (`src/plugins/<plugin>`, package riêng).

### Schema `theme.toml` (reference — cơ chế đã xong, dùng khi tạo theme mới)

```toml
[theme]
name        = "blog"                 # bắt buộc
description = "..."
version     = "1.0.0"                # version của theme (thông tin)
requires_pyssg = ">=1.0"             # check tương thích, new cảnh báo nếu lệch
author      = "pyssg"
homepage    = "https://github.com/<owner>/pyssg"

[config]
preset = "blog"                      # bắt buộc: docs | blog | site
src    = "content"                   # -> Config(src=...)
out    = "public"                    # -> Config(out=...)

[config.options]                     # kwargs truyền thẳng vào preset, toml->literal Python 1-1
page_size           = 10
rss                 = true
sitemap             = true
minify              = false
markdown_extensions = ["fenced_code", "tables", "toc"]
template_dir        = "layouts"

[dependencies]
plugins = []                         # pip package ngoài built-in -> new gợi ý "uv add ..."

[scaffold]
include = ["layouts", "assets", "content"]   # thư mục vendor nguyên vào project
sample  = ["content"]                        # content mẫu, bỏ qua bằng --no-sample
```

Convention thư mục theme (khớp mặc định plugin): `layouts/` (Jinja2), `assets/` (StaticFiles),
`content/` (src), `theme.toml` ở root. `new` chỉ đọc toml + copy file, KHÔNG exec gì từ theme.

---

## Hệ sinh thái theme theo nhóm người dùng

**Ưu tiên đã chốt (2026-05-30): làm trước 2 theme — Docs OSS + Blog cá nhân.**

| Nhóm | Theme | Ưu tiên | Tính năng theme cần |
|---|---|---|---|
| Maintainer docs OSS | `docs` | **1** | sidebar, search, syntax highlight, edit-on-GitHub, (versioning sau) |
| Dev blog cá nhân | `blog` | **1** | dark mode, RSS/JSON feed, tag, reading time, OG image |
| Team / knowledge base | `kb` | 2 | search mạnh, breadcrumb, last-updated, internal link |
| Landing tool/startup | `landing` | 2 | section blocks, SEO/OG, CTA |

Mỗi theme: CSS responsive + dark mode, typography tốt, **không yêu cầu Node/build-step phía user**.
Nền tảng tiên quyết (fingerprint, syntax-highlight CSS, SEO/OG) đã xong -> giờ có thể làm theme.

---

## Phạm vi đề xuất cho 1.0

Lõi 1.0 (phần nền đã xong): scaffolding · lỗi/overlay DX · syntax highlight · asset fingerprint ·
SEO/OG · cơ chế nạp theme. **Còn thiếu cho 1.0:** data files, ship kèm **2 theme docs + blog** chỉn chu.

Xếp 1.1: search, shortcodes, feed mở rộng, link-checker, Obsidian wikilink, markdown lint/validate.
Sau cùng: incremental build.

## Quyết định đã chốt

- 2026-05-30: Ưu tiên 2 theme đầu tiên là **Docs OSS** và **Blog cá nhân**.
- 2026-05-30: Phiên brainstorm/triển khai kế tiếp tập trung nhánh **DX onboarding (A)**.
