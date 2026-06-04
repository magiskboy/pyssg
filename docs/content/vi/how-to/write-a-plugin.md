---
title: Viết plugin riêng
nav_title: Viết plugin
order: 5
---

# Viết plugin riêng

**Mục tiêu:** thêm hành vi của riêng bạn bằng cách gắn vào một hook, đúng cách mà
các plugin tích hợp làm.

Để hiểu bức tranh tổng thể về cách các plugin ghép với nhau, hãy đọc
[Pipeline plugin](../explanation/plugin-pipeline.md) trước. Hướng dẫn này là công
thức thực hành.

Để bắt đầu từ một khung sẵn chạy thay vì một file trống, chạy
`pyssg new plugin <name>`: nó tạo `plugins/<name>.py` với lớp, factory và phần nối
hook đã sẵn sàng để tùy biến.

## Hình hài một plugin

Một plugin là bất kỳ đối tượng nào có thuộc tính `name` và phương thức
`apply(builder)`. Bên trong `apply`, bạn gắn vào một hoặc nhiều hook. Quy ước là
cung cấp một hàm factory nhỏ trả về một instance, để nó đọc gọn gàng trong file
cấu hình.

```python
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pyssg.core.builder import Builder


class UppercaseTitles:
    """Force every page title to upper case (a tiny example)."""

    name = "uppercase_titles"

    def apply(self, builder: Builder) -> None:
        @builder.hooks.this_compilation.tap(self.name)
        def _(build: object) -> None:
            # Tap a per-build hook here; see the hook reference for the full set.
            ...


def uppercase_titles() -> UppercaseTitles:
    return UppercaseTitles()
```

## Gắn vào đâu

Hook tồn tại ở hai phạm vi:

- **Builder hook** (`builder.hooks.*`) - trình biên dịch sống lâu. Gắn vào
  `this_compilation` để chạm vào từng lần build, hoặc `make` để chèn các node tổng
  hợp vào đồ thị (đây là cách `apidoc` thêm các trang reference của nó).
- **Build hook** (`build.hooks.*`) - một lần biên dịch. Đây là các điểm gắn theo
  từng tài liệu và từng trang: `parse`, `resolve`, `finalize_content`, `route`,
  `render_page`, và nhiều hơn.

Danh sách đầy đủ kèm chữ ký nằm trong
[tham chiếu plugin & hook](../reference/plugins.md).

## Thứ tự các tap

Các tap khai báo thứ tự *tương đối* bằng một số nguyên `stage` thô cùng ràng buộc
tên `before` / `after`. Ví dụ, `external_links` gắn vào `finalize_content` tại
`stage=300` để chạy sau khi phân giải wikilink (100) và phân giải liên kết nội bộ
(200), nhờ đó nó thấy các href cuối cùng:

```python
@builder.hooks... .tap(self.name, stage=300)
def _(html: str) -> str:
    ...
```

Trước mỗi lần gọi, các tap được sắp xếp theo thứ tự tô-pô; một ràng buộc tạo vòng
lặp sẽ ném `HookOrderError`.

## Các quy tắc mọi plugin phải tuân theo

Đây không phải tùy chọn - chúng là thứ giữ cho các đảm bảo build của PySSG đứng
vững:

1. **Thuần khiết theo các đầu vào đã khai báo.** Không có trạng thái toàn cục có
   thể thay đổi, và không gọi trực tiếp `datetime.now()` / `time` / `random`.
   Build hai lần phải giống nhau từng byte.
2. **Khai báo sự kiện; để engine sở hữu thuật toán.** Plugin không tự lan truyền
   "bẩn" (dirtiness) hay tự quản lý cache.
3. **`route` trả về `""` nghĩa là "không có trang".** Một tap `route` trả về chuỗi
   rỗng sẽ chặn đầu ra cho tài liệu đó (đây là cách `i18n` loại bỏ các file nằm
   ngoài mọi thư mục locale).
4. **Lõi chỉ dùng thư viện chuẩn.** Import bên thứ ba thuộc về phần ngoại vi
   (`pyssg/plugins/` hoặc `pyssg/contrib/`), không bao giờ trong `pyssg/core/`.

## Sử dụng

Import và thêm plugin của bạn trong `pyssg.config.py`:

```python
from __future__ import annotations

from pyssg.presets import docs
from mypackage.plugins import uppercase_titles

config = docs(
    site={"title": "My Docs"},
    extra_plugins=[uppercase_titles()],
)
```

`extra_plugins` được nối sau các plugin mặc định của preset, nên chúng chạy sau
cùng.
