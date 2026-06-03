---
title: Tham chiếu CLI
nav_title: CLI
order: 2
---

# Tham chiếu CLI

pyssg được gọi như một module: `python -m pyssg [--site PATH] <command> [options]`.
Qua uv là `pyssg ...`.

## Tùy chọn toàn cục

| Tùy chọn | Mặc định | Mô tả |
|---|---|---|
| `--site PATH` | `.` | Thư mục trang. Mọi đường dẫn khác trong cấu hình (`content_dir`, `output_dir`, `layout`) đều tương đối so với nó. Đây là tùy chọn toàn cục nên đặt *trước* lệnh: `pyssg --site my-site build`. |

Chạy bất kỳ lệnh nào với `--help` để xem các tùy chọn của nó.

## `build`

Build đầy đủ ra thư mục đầu ra.

```bash
pyssg --site my-site build
```

| Tùy chọn | Mặc định | Mô tả |
|---|---|---|
| `--no-cache` | tắt | Bỏ qua cache bền vững (chứng minh một bản build sạch từ đầu). |
| `--profile` | tắt | In số lượng node "chạm" theo từng pha và số lần trúng cache. |
| `--json` | tắt | Xuất bản tóm tắt một dòng dạng máy đọc thay cho văn bản người đọc. |

In ra `build: N pages written`. Với `--json` in một đối tượng JSON, ví dụ
`{"command": "build", "ok": true, "pages": 3, "cache_hits": 0, "phases": {...}}`,
hoặc `{"command": "build", "ok": false, "error": "..."}` khi lỗi (mã thoát 1).

## `serve`

Theo dõi nội dung, build lại tăng tiến, và phục vụ kèm tự nạp lại.

```bash
pyssg --site my-site serve
```

| Tùy chọn | Mặc định | Mô tả |
|---|---|---|
| `--host HOST` | `127.0.0.1` | Địa chỉ để bind. |
| `--port PORT` | `8000` | Cổng để bind. |
| `--no-cache` | tắt | Bỏ qua cache bền vững. |
| `--json` | tắt | Xuất các sự kiện JSON phân tách theo dòng (một sự kiện `ready`, rồi mỗi lần đổi là một sự kiện `rebuild`) thay cho văn bản người đọc. |

Sửa bất kỳ file nào dưới `content/` và trang bị ảnh hưởng sẽ build lại, trình duyệt
tự nạp lại.

## `clean`

Xóa thư mục đầu ra và cache.

```bash
pyssg --site my-site clean
```

| Tùy chọn | Mặc định | Mô tả |
|---|---|---|
| `--yes` | tắt | Bỏ qua bước xác nhận tương tác. |

Khi không có `--yes`, `clean` liệt kê những gì sẽ xóa và hỏi xác nhận.

## `new`

Khởi tạo các file dự án. Mọi việc khởi tạo đều tất định (ngày tháng mẫu là hằng
cố định trừ khi bạn truyền `--date`), nên chạy hai lần cho ra các file giống hệt.

### `new site`

Khởi tạo một trang mới cho một preset: một `pyssg.config.py` một dòng cùng ít nội
dung mẫu.

```bash
pyssg --site my-site new site --preset docs
```

| Tùy chọn | Mặc định | Mô tả |
|---|---|---|
| `--preset {docs,blog,obsidian}` | `docs` | Preset nào để khởi tạo. |
| `--force` | tắt | Ghi đè `pyssg.config.py` đã tồn tại (nếu không `new site` sẽ từ chối để tránh làm hỏng một trang thật). |

### `new post`

Khởi tạo một bài viết mới dưới `content/posts/`.

```bash
pyssg --site my-site new post --title "Hello, world" --tag intro
```

| Tùy chọn | Mặc định | Mô tả |
|---|---|---|
| `--title TEXT` | `New Post` | Tiêu đề bài viết; cũng là cơ sở cho slug tên file. |
| `--tag TEXT` | *(không)* | Một thẻ thêm vào frontmatter. Lặp lại được. |
| `--date YYYY-MM-DD` | hôm nay | Ngày trong frontmatter. Truyền tường minh để kết quả tái lập được. |
| `--slug TEXT` | từ tiêu đề | Slug tên file (file là `content/posts/<slug>.md`). |
| `--force` | tắt | Ghi đè một bài viết đã tồn tại. |

### `new theme`

Sao chép một theme tích hợp vào trang để bạn có thể tùy biến (hành động "eject").

```bash
pyssg --site my-site new theme --name docs --to layouts/theme
```

| Tùy chọn | Mặc định | Mô tả |
|---|---|---|
| `--name {docs,blog}` | *(bắt buộc)* | Theme tích hợp để sao chép. |
| `--to DIR` | `layouts/theme` | Thư mục đích, tương đối so với trang. |

Từ chối ghi đè lên một đích đã tồn tại. Sau khi sao chép, đặt `layout="<DIR>"`
trong `pyssg.config.py`. Xem [Tùy biến theme](../how-to/customize-theme.md).

### `new plugin`

Khởi tạo một module plugin khởi đầu dưới `plugins/`: một lớp plugin cùng factory
chữ thường của nó, sẵn sàng để tùy biến.

```bash
pyssg --site my-site new plugin my_plugin
```

| Đối số / Tùy chọn | Mặc định | Mô tả |
|---|---|---|
| `NAME` | *(bắt buộc)* | Tên plugin; phải là một định danh Python hợp lệ (dùng làm module, factory và cơ sở tên lớp). |
| `--force` | tắt | Ghi đè một file đã tồn tại. |

Module sinh ra tự ghi rõ cách nối hook của nó. Để bật, thêm `my_plugin()` vào
`config.plugins` (thư mục plugins phải import được, ví dụ nằm trên `PYTHONPATH`).

## `deploy`

Đẩy trang đã build lên một nhà cung cấp hosting. Dạng lệnh là
`pyssg deploy <target-or-action>`, với phần cuối là một target đã cấu hình
(`github-pages`, `cloudflare`, `netlify`) hoặc một hành động meta.

```bash
pyssg --site my-site deploy list
pyssg --site my-site deploy github-pages --dry-run
```

| Hành động | Mô tả |
|---|---|
| `list` | Liệt kê các target cấu hình trong `pyssg.config.py` và mỗi cái đã được hiện thực hay chưa. |
| `status` | Hiển thị bản ghi lần deploy gần nhất (thời điểm, deployment id, URL) cho mỗi target đã cấu hình. |

Mỗi subcommand target nhận:

| Tùy chọn | Mặc định | Mô tả |
|---|---|---|
| `--dry-run` | tắt | Kiểm tra và báo cáo những gì sẽ tải lên, nhưng không đẩy. |
| `--force` | tắt | Deploy lại kể cả khi đầu ra giống hệt từng byte với lần trước. |
| `--skip-build` | tắt | Dùng lại thư mục đầu ra sẵn có thay vì build lại. |
| `--skip-check` | tắt | Bỏ qua bước kiểm tra hợp lệ sau build. |

Xem [Triển khai trang](../how-to/deploy.md) để biết cấu hình theo từng nhà cung cấp.

## Các alias không khuyến khích

Những lệnh cũ này vẫn chạy như alias ẩn; hãy ưu tiên nhóm `new`:

| Alias | Dùng thay thế |
|---|---|
| `pyssg init --preset docs` | `pyssg new site --preset docs` |
| `pyssg eject-layout --theme docs` | `pyssg new theme --name docs` |
