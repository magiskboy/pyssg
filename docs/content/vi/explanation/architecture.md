---
title: Kiến trúc
nav_title: Kiến trúc
order: 2
---

# Kiến trúc

PySSG được tổ chức như một **nhân nhỏ, thuần khiết** được bao quanh bởi các
**plugin ngoại vi**, theo tinh thần tách compiler/plugin của Webpack. Hiểu ranh
giới này sẽ giải thích được phần lớn các quyết định thiết kế.

## Lõi chỉ dùng thư viện chuẩn

Mọi thứ dưới `pyssg/core/` chỉ dùng thư viện chuẩn của Python - không import bên
thứ ba. Lõi sở hữu các *thuật toán*: đồ thị phụ thuộc, các pha build, engine tăng
tiến, hệ thống hook và scheduler. Nó biết cách biến một đồ thị node thành đầu ra,
nhưng không biết gì về Markdown, Pygments, Jinja hay watchdog.

Bất cứ thứ gì cần thư viện bên thứ ba đều nằm ở **phần ngoại vi**:

- `pyssg/plugins/` - các plugin tích hợp sẵn (phân tích Markdown, tô màu code,
  điều hướng, RSS, v.v.).
- `pyssg/contrib/` - plugin cộng đồng (`apidoc`, `external_links`). Chúng đi kèm
  test và vượt qua `mypy --strict`, nhưng không được tự động re-export vào
  `pyssg.plugins`.
- `pyssg/presets/` - các factory thuần khiết trả về một `Config` (một danh sách
  plugin cộng một theme); chúng khai báo sự kiện, không sở hữu thuật toán.
- `pyssg/themes/` - các theme Jinja tích hợp sẵn.

## Plugin khai báo sự kiện; engine sở hữu thuật toán

Nhiệm vụ của một plugin là đóng góp các *sự kiện* bằng cách gắn vào hook: "đây là
cách phân tích một file `.md`", "tài liệu này liên kết tới tài liệu kia", "URL của
trang này là X". Plugin **không** quyết định cái gì là "bẩn", không quản lý cache,
cũng không lên lịch công việc. Điều đó giữ phần máy móc khó và sống còn về tính
đúng đắn (vô hiệu hóa tăng tiến, sắp xếp tất định) ở một nơi - phần lõi - thay vì
rải rác khắp mọi plugin.

## Mặt phẳng dữ liệu: một đồ thị các node

Một lần build là một `DependencyGraph` gồm các **node** có kiểu. Các loại node
chính là `MARKDOWN`, `DATA`, `DIRECTORY`, `ASSET` và `PAGE`; quan hệ giữa chúng là
các **connection** có kiểu (`CONTAINMENT`, `LINK`, `EMBED`, `ASSET_REF`,
`TEMPLATE`, `COLLECTION`, `GENERATED_FROM`, ...). Một `Document` (một file `.md` đã
phân tích) thường *sinh ra* một `Page`; cạnh `GENERATED_FROM` nối chúng lại.

Việc biểu diễn liên kết và nhúng bằng các cạnh thật là thứ khiến **backlink** và
**vô hiệu hóa tăng tiến** xuất hiện một cách tự nhiên: nếu bạn biết cái gì liên kết
tới cái gì, bạn biết cả ai được ghi nhận backlink lẫn cái gì cần render lại khi một
đích di chuyển.

## Mặt phẳng điều khiển: hook

Plugin gắn vào các **hook** tại những điểm được định nghĩa rõ ràng. Có hai phạm vi:

- **Builder hook** - trên trình biên dịch sống lâu (`initialize`, `before_run`,
  `this_compilation`, `make`, `after_emit`, `done`, ...).
- **Build hook** - trên một lần biên dịch (`load_node`, `parse`, `resolve`,
  `finalize_content`, `expand_content`, `generate`, `route`, `render_page`,
  `emit`, ...).

Trang tiếp theo, [Pipeline plugin](plugin-pipeline.md), đi qua từng bước một file
"du hành" qua các hook này để trở thành một trang.

## Vì sao cấu hình bằng mã (code-as-config)

Cấu hình là một file Python (`pyssg.config.py`) export một biến `config`, không
phải YAML hay TOML. Mã cho phép bạn kết hợp các *instance* plugin và các biến
template tùy ý với kiểm tra kiểu đầy đủ - đó chính là điểm mấu chốt: người dùng cơ
bản viết một dòng, còn người dùng nâng cao có cả ngôn ngữ trong tay mà không cần
một DSL cấu hình plugin mới.
