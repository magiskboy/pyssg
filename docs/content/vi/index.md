---
title: Trang chủ
nav_title: Tổng quan
order: 1
---

# PySSG

**PySSG** là một trình tạo trang tĩnh (static site generator) nhanh, hỗ trợ build
tăng tiến (incremental) cho Markdown, với kiến trúc plugin lấy cảm hứng từ
Webpack. Nó được xây dựng cho **trang tài liệu**, **blog** và các **wiki / cơ sở
tri thức** lớn.

Phần lõi (`pyssg.core`) chỉ dùng thư viện chuẩn (standard library); mọi phụ thuộc
bên thứ ba đều nằm ở các plugin ngoại vi. Quá trình build có tính tất định
(deterministic) - build hai lần cho ra kết quả giống nhau từng byte, và một lần
build tăng tiến được đảm bảo giống hệt từng byte so với build lại toàn bộ.

> Chính trang tài liệu này cũng được build bằng PySSG. Mục **References** trong
> thanh bên được sinh tự động từ docstring của dự án bởi plugin contrib
> [`apidoc`](how-to/api-reference.md).

## Bắt đầu từ đâu

Tài liệu này tuân theo khung [Diátaxis](https://diataxis.fr/), chia tài liệu thành
bốn loại, mỗi loại phục vụ một nhu cầu khác nhau:

- **[Hướng dẫn nhập môn (Tutorial)](tutorial/build-your-first-site.md)** - định
  hướng học tập. Bắt đầu ở đây nếu bạn mới: build và chạy trang đầu tiên theo từng
  bước.
- **[Hướng dẫn theo việc (How-to)](how-to/index.md)** - các công thức theo từng
  bài toán cụ thể (thêm i18n, tùy biến theme, viết plugin, sinh API reference,
  triển khai).
- **[Tích hợp (Integrations)](integrations/index.md)** - publish từ chính công cụ
  bạn đang viết (ví dụ một vault [Obsidian](integrations/obsidian.md)).
- **[Tham chiếu (Reference)](reference/index.md)** - định hướng thông tin, mô tả
  chính xác về CLI, cấu hình, frontmatter và các plugin tích hợp sẵn.
- **[Diễn giải (Explanation)](explanation/index.md)** - định hướng hiểu sâu, bàn
  về *vì sao* PySSG hoạt động như vậy (kiến trúc, pipeline plugin, build tăng
  tiến, mô hình liên kết).
- **[References](/references/pyssg/)** - API reference sinh tự động cho gói
  `pyssg`.

## Tính năng nổi bật

- **Build tăng tiến** - mỗi lần lưu, chỉ những trang thực sự thay đổi mới được
  render lại; phần còn lại lấy từ cache, và kết quả giống hệt từng byte so với
  build lại toàn bộ.
- **Pipeline plugin** - nội dung đi qua một chuỗi hook (load -> parse -> link ->
  render), mỗi hook thuộc về một plugin nhỏ, dễ kết hợp.
- **Liên kết kiểu Obsidian** - `[[wikilinks]]`, `![[transclusion]]`, **backlink**
  tự động, và phát hiện liên kết hỏng sẵn có.
- **Taxonomy không cần cấu hình** - thêm `tags:` hoặc `category:` trong frontmatter
  và các trang chỉ mục `/tags/`, `/categories/` xuất hiện tự động.
- **Quốc tế hóa (i18n)** - locale theo thư mục với bộ chuyển ngôn ngữ và thẻ
  `hreflang`.
- **Markdown phong phú** - tô màu code (Pygments), sơ đồ Mermaid, mục lục, thời
  gian đọc và đoạn trích.
- **Đầy đủ sẵn dùng** - điều hướng thanh bên, breadcrumb, prev/next, RSS feed và
  sitemap đều được sinh sẵn cho bạn.
- **Dev server tự nạp lại** - `serve` theo dõi file, build lại tăng tiến và làm
  mới trình duyệt.

## Yêu cầu

- Python 3.13+
- [uv](https://github.com/astral-sh/uv) (trình quản lý gói và môi trường)
