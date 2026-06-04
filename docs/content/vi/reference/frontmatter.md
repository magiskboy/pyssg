---
title: Tham chiếu frontmatter
nav_title: Frontmatter
order: 4
---

# Tham chiếu frontmatter

Mỗi tài liệu Markdown có thể bắt đầu bằng một khối frontmatter YAML phân định bởi
`---`. Plugin `frontmatter` phân tích nó thành metadata của tài liệu để các plugin
sau đọc. Các trường bên dưới là những trường mà các plugin tích hợp của PySSG hiểu;
mọi khóa khác được giữ lại và cấp cho template.

```markdown
---
title: Getting Started
order: 2
tags: [intro, setup]
---
# Getting Started
...
```

## Các trường được plugin tích hợp đọc

| Trường | Kiểu | Đọc bởi | Tác dụng |
|---|---|---|---|
| `title` | `str` | nav, render, taxonomy | Tiêu đề trang (mục thanh bên, `<title>`, breadcrumb). |
| `nav_title` | `str` | nav | Ghi đè `title` chỉ trong menu điều hướng. |
| `order` | `int` | nav | Thứ tự sắp trong một mục; trang không có `order` xếp cuối, rồi theo URL. |
| `date` | `str` | blog, rss | Ngày xuất bản (dùng cho sắp xếp và feed). |
| `tags` | `list[str]` | taxonomy | Sinh các trang chỉ mục `/tags/<tag>/`. |
| `category` / `categories` | `str` / `list[str]` | taxonomy | Sinh các trang chỉ mục `/categories/<category>/`. |
| `draft` | `bool` | (loader) | Đánh dấu một tài liệu là bản nháp. |
| `template` | `str` | render | Chọn một template layout cụ thể cho trang này. |
| `permalink` | `str` | permalink | Đặt một URL đầu ra tường minh cho trang này. |
| `excerpt` | `str` | content_meta | Ghi đè đoạn trích sinh tự động. |
| `toc` | (suy ra) | content_meta | Mục lục / outline (được tính, cấp cho template). |

## Metadata được tính toán

Ngoài những gì bạn viết, plugin `content_meta` suy ra và gắn thêm:

- `word_count` và `reading_time`,
- `excerpt` (nếu không đặt tường minh),
- `toc` (outline tiêu đề).

Chúng có sẵn cho template bên cạnh các trường frontmatter.

## Ghi chú

- **Locale không phải một trường frontmatter.** Dưới plugin `i18n`, locale là thư
  mục content cấp cao nhất (`content/en/...`), theo thiết kế - xem
  [quốc tế hóa](../how-to/internationalization.md).
- Markdown được render bằng [Python-Markdown](https://python-markdown.github.io/)
  (các extension `fenced_code`, `tables`, `sane_lists`, `toc`), nên **bảng kiểu GFM
  dạng pipe được hỗ trợ**. HTML thô cũng đi qua nguyên vẹn - đó là cách plugin
  `apidoc` phát các bảng tham số của nó.
