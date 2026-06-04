---
title: Tùy biến theme
nav_title: Tùy biến theme
order: 3
---

# Tùy biến theme

**Mục tiêu:** thay đổi giao diện trang bằng cách sửa template và CSS, bắt đầu từ
một theme tích hợp sẵn thay vì làm lại từ đầu.

## 1. Tách (eject) một theme tích hợp

`new theme` sao chép một theme tích hợp vào trang của bạn để bạn có thể sửa:

```bash
pyssg --site my-site new theme --name docs --to layouts/theme
```

Lệnh này sao chép theme `docs` vào `my-site/layouts/theme/`. (Các theme có sẵn là
`docs` và `blog`.) Lệnh từ chối ghi đè lên một đích đã tồn tại, nên bạn sẽ không vô
tình làm hỏng một layout đã tùy biến.

## 2. Trỏ cấu hình vào layout đã tách

Trong `pyssg.config.py`, đặt `layout` thành thư mục vừa sao chép (đường dẫn tương
đối so với gốc trang):

```python
from __future__ import annotations

from pyssg.presets import docs

config = docs(
    site={"title": "My Docs"},
    base_url="https://example.com",
    layout="layouts/theme",
)
```

`layout` nhận một `str` là đường dẫn tương đối so với trang, hoặc một `Path` tuyệt
đối (chính là cách các theme tích hợp được tham chiếu nội bộ qua
`pyssg.themes.theme_path`).

## 3. Sửa template và style

Bên trong `layouts/theme/` bạn sẽ thấy các template Jinja và CSS. Sửa chúng rồi
chạy lại `serve` để xem thay đổi trực tiếp:

```bash
pyssg --site my-site serve
```

Template nhận nội dung đã render của trang cùng các biến ngữ cảnh do plugin đóng
góp - ví dụ `menu` điều hướng, `breadcrumbs`, các trang prev/next, và (nếu plugin
`i18n` đang bật) `lang` cùng `translations`.

## Mẹo: bắt đầu từ preset, chỉ ghi đè phần cần thiết

Bạn không bắt buộc phải tách cả theme chỉ để chỉnh một thứ. Vì một preset chỉ là
một factory trả về `Config`, bạn cũng có thể tự dựng một `Config` bằng tay và tái
sử dụng đúng những plugin mình muốn - xem
[tham chiếu cấu hình](../reference/configuration.md).
