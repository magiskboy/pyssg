---
title: Xây dựng trang đầu tiên
nav_title: Xây dựng trang đầu tiên
order: 1
---

# Xây dựng trang đầu tiên

Bài hướng dẫn này đưa bạn từ một thư mục trống đến một trang tài liệu chạy thật,
tự nạp lại. Khi kết thúc, bạn sẽ đã khởi tạo (scaffold) một trang, build nó, chạy
cục bộ và thực hiện một thay đổi được nạp lại ngay trên trình duyệt.

Đây là một *bài học*, không phải tài liệu tham chiếu: cứ làm theo thứ tự là bạn sẽ
có kết quả chạy được. Bạn chưa cần hiểu mọi chi tiết - phần
[Diễn giải](../explanation/index.md) sẽ nói về *vì sao* sau.

## Yêu cầu trước

- Đã cài **Python 3.13+** và **[uv](https://github.com/astral-sh/uv)**.
- Có pyssg. Cách đơn giản nhất khi học là clone kho mã và chạy mọi thứ qua
  `uv run`:

  ```bash
  git clone https://github.com/magiskboy/pyssg && cd pyssg
  uv sync
  ```

  Trong dự án của riêng bạn, thay vào đó hãy thêm nó như một phụ thuộc:

  ```bash
  uv add git+https://github.com/magiskboy/pyssg
  ```

Mọi lệnh bên dưới được viết dạng `pyssg ...`. Tùy chọn `--site`
chọn thư mục trang; mặc định là thư mục hiện tại.

## Bước 1 - Khởi tạo trang mới

**Preset** là một cấu hình dựng sẵn, gói sẵn đúng bộ plugin và một theme mặc định.
Khởi tạo một trang tài liệu với preset `docs`:

```bash
pyssg --site my-site new site --preset docs
```

Lệnh này tạo ba file:

```
my-site/
  pyssg.config.py                     # cấu hình một dòng
  content/index.md                    # trang chủ
  content/guide/getting-started.md    # một trang mẫu
```

Mở `my-site/pyssg.config.py`. Toàn bộ cấu hình chỉ là một lời gọi:

```python
from __future__ import annotations

from pyssg.presets import docs

config = docs(
    site={"title": "My Docs"},
    base_url="https://example.com",
)
```

## Bước 2 - Build trang

Render nội dung ra thư mục đầu ra (mặc định là `dist/`):

```bash
pyssg --site my-site build
```

Bạn sẽ thấy thông báo kiểu `build: 3 pages written`. HTML giờ nằm trong
`my-site/dist/`. Mỗi trang được ghi dưới dạng *pretty URL* -
`content/guide/getting-started.md` trở thành `dist/guide/getting-started/index.html`,
phục vụ tại `/guide/getting-started/`.

## Bước 3 - Chạy với tự nạp lại

Thay vì build thủ công, hãy chạy dev server. Nó theo dõi file, chỉ build lại phần
thay đổi, và tự làm mới trình duyệt:

```bash
pyssg --site my-site serve
```

Mở URL được in ra (mặc định <http://127.0.0.1:8000>). Bạn sẽ thấy trang chủ cùng
thanh bên liệt kê các trang mẫu.

## Bước 4 - Thay đổi và xem nó tự nạp lại

Cứ để `serve` chạy. Ở một cửa sổ terminal khác (hoặc trong trình soạn thảo), mở
`my-site/content/index.md` và đổi tiêu đề:

```markdown
---
title: Home
---
# Welcome to my docs

This is my first pyssg site.
```

Lưu file. Terminal hiện một lần build tăng tiến nhanh và trình duyệt tự nạp lại -
chỉ trang bạn vừa sửa được render lại.

## Bước 5 - Thêm trang mới và liên kết tới nó

Tạo `my-site/content/guide/concepts.md`:

```markdown
---
title: Core concepts
order: 2
---
# Core concepts

Back to [getting started](getting-started.md).
```

Lưu lại. Một mục mới xuất hiện trong thanh bên dưới nhóm **guide**, sắp theo trường
frontmatter `order`. Liên kết tới `getting-started.md` được tự động viết lại thành
URL của trang đích - liên kết nội bộ được phân giải theo đường dẫn, nên chúng vẫn
hoạt động kể cả khi bạn di chuyển trang về sau.

## Bạn vừa tạo được gì

Bây giờ bạn đã có một trang chạy được với:

- một trang chủ và một mục `guide/` đã trở thành một nhóm trong thanh bên,
- build tăng tiến kèm tự nạp lại,
- liên kết nội bộ tự phân giải.

## Bước tiếp theo

- Giải quyết các bài toán cụ thể với **[Hướng dẫn theo việc](../how-to/index.md)**
  - ví dụ [tùy biến theme](../how-to/customize-theme.md) hoặc
  [thêm ngôn ngữ thứ hai](../how-to/internationalization.md).
- Tra cứu tùy chọn chính xác trong **[Tham chiếu](../reference/index.md)**.
- Hiểu cách build hoạt động trong **[Diễn giải](../explanation/index.md)**.
