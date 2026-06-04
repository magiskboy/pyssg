---
title: Plugin và hook
nav_title: Plugin và hook
order: 5
---

# Plugin và hook

Trang này liệt kê các plugin tích hợp và contrib, cùng các điểm hook mà một plugin
có thể gắn vào. Để xem API sinh tự động theo từng ký hiệu của mọi module, xem mục
[References](/references/pyssg/).

## Plugin tích hợp (`pyssg.plugins`)

Đây là các plugin đi kèm PySSG và được các preset sử dụng.

| Plugin | Mục đích |
|---|---|
| `directory_loader` | Phát hiện các file nguồn dưới `content/`. |
| `frontmatter` | Tách frontmatter YAML khỏi thân bài. |
| `markdown` | Nạp và phân tích Markdown thành HTML (Python-Markdown). |
| `mermaid` | Render sơ đồ Mermaid phía client. |
| `highlight` | Tô màu các khối code rào (fenced) qua Pygments. |
| `content_meta` | TOC / outline, đếm từ, thời gian đọc, đoạn trích. |
| `permalink` | Gán URL đầu ra cho mỗi trang. |
| `wikilink` | Liên kết kiểu Obsidian `[[...]]`. |
| `link_resolver` | Viết lại liên kết `.md` nội bộ; ghi backlink. |
| `transclude` | Nhúng kiểu Obsidian `![[...]]`. |
| `nav` | Menu thanh bên, breadcrumb và prev/next. |
| `taxonomy` | Trang chỉ mục `tags` và `categories` không cần cấu hình. |
| `collections` | Danh sách tài liệu khai báo, có phân trang. |
| `i18n` | Locale theo thư mục (xem hướng dẫn i18n). |
| `rss` | RSS feed. |
| `sitemap` | `sitemap.xml`. |
| `asset_copy` | Sao chép asset tĩnh vào đầu ra. |
| `render` | Render trang qua layout Jinja. |

## Plugin contrib (`pyssg.contrib`)

Plugin cộng đồng. Chúng đi kèm test và vượt qua `mypy --strict`, nhưng **không**
được tự động re-export vào `pyssg.plugins` - hãy import từ module của chúng.

| Plugin | Import | Mục đích |
|---|---|---|
| `apidoc` | `from pyssg.contrib.apidoc import apidoc` | Một mục `References` từ docstring Python (xem [hướng dẫn](../how-to/api-reference.md)). |
| `external_links` | `from pyssg.contrib.external_links import external_links` | Mở liên kết ra ngoài site trong tab mới với `rel="noopener noreferrer"`. |

## Hệ thống hook

Một plugin là một đối tượng có `name` và phương thức `apply(builder)`; bên trong
`apply` nó gắn vào các hook. Hook có bốn "vị", mỗi vị có một ngữ nghĩa luồng giá trị
khác nhau:

| Vị | Ngữ nghĩa |
|---|---|
| `SyncHook` | Gọi mọi tap để lấy hiệu ứng phụ. |
| `AsyncSeriesHook` | Await từng tap theo thứ tự (I/O, ví dụ ghi file). |
| `WaterfallHook` | Luồn một giá trị qua các tap; mỗi tap trả về đầu vào tiếp theo. |
| `BailHook` | Dừng ở tap đầu tiên trả về giá trị khác `None`. |

Các tap tự sắp thứ tự bằng một số nguyên `stage` thô cùng ràng buộc tên `before` /
`after`; chúng được sắp xếp tô-pô trước mỗi lần gọi (một vòng lặp sẽ ném
`HookOrderError`).

### Builder hook (`builder.hooks`)

Phạm vi trình biên dịch sống lâu.

| Hook | Vị | Khi nào |
|---|---|---|
| `initialize` | Sync | Builder được tạo. |
| `before_run` | AsyncSeries | Trước một lần chạy build. |
| `this_compilation` | Sync | Một `Build` mới vừa được tạo. |
| `make` | AsyncSeries | Chèn các node tổng hợp vào đồ thị (được `apidoc` dùng). |
| `after_emit` | AsyncSeries | Sau khi mọi đầu ra đã được xuất. |
| `done` | Sync | Build kết thúc (nhận `BuildStats`). |
| `failed` | Sync | Build ném lỗi. |
| `watch_run` | AsyncSeries | Một lần build do watch kích hoạt bắt đầu. |
| `invalidate` | Sync | Các node bị vô hiệu hóa. |

### Build hook (`build.hooks`)

Phạm vi một lần biên dịch.

| Hook | Vị | Vai trò |
|---|---|---|
| `load_node` | Bail | Nạp một đường dẫn nguồn thành một `Node`. |
| `parse` | Sync | Phân tích một node đã nạp. |
| `resolve` | Bail | Phân giải một phụ thuộc thành một `Connection`. |
| `evaluate_collections` | Sync | Dựng các danh sách toàn-đồ-thị (nav, taxonomy, phân giải liên kết). |
| `finalize_content` | Waterfall | Viết lại nội dung theo từng tài liệu (wikilink @100, link_resolver @200, external_links @300). |
| `expand_content` | Sync | Mở rộng nội dung toàn-build (transclusion). |
| `generate` | Sync | Sinh trang từ tài liệu. |
| `route` | Waterfall | Tính URL trang; trả về `""` nghĩa là "không có trang". |
| `transform` | Waterfall | Biến đổi payload của node. |
| `render_page` | Waterfall | Tạo HTML cuối cùng. |
| `process_assets` | Sync | Xử lý / tối ưu asset. |
| `emit` | AsyncSeries | Ghi các file đầu ra. |
| `after_emit` | AsyncSeries | Việc hậu-xuất theo từng build. |

Để viết một plugin, xem [Viết plugin riêng](../how-to/write-a-plugin.md).
