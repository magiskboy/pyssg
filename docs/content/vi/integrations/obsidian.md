---
title: Publish một vault Obsidian
nav_title: Obsidian
order: 2
---

# Publish một vault Obsidian

Hướng dẫn này chỉ cách biến một vault [Obsidian](https://obsidian.md) thành trang
web tĩnh bằng plugin **PySSG Publish**, và cách làm tương tự từ dòng lệnh nếu bạn
muốn. Bạn không cần biết Python.

## Trước khi bắt đầu

- Obsidian bản desktop (plugin gọi ra một tiến trình cục bộ nên chỉ chạy trên
  desktop).
- Có kết nối mạng ở lần build đầu tiên để plugin tải runtime. Bạn **không** cần
  tự cài Python - xem [Cách runtime Python được dựng tự
  động](#cach-runtime-python-duoc-dung-tu-dong).

## Cài plugin

Plugin chưa có trên cửa hàng cộng đồng nên hãy cài thủ công:

1. Build từ kho pyssg:

   ```bash
   cd adapters/pyssg-obsidian
   npm install
   npm run build
   ```

2. Chép `manifest.json`, `main.js` và `styles.css` vào vault tại
   `.obsidian/plugins/pyssg-publish/`.
3. Trong Obsidian, mở **Settings -> Community plugins**, tải lại và bật
   **PySSG Publish**.

## Chọn nội dung để publish

Mặc định theo cơ chế **denylist**: mọi note đều được publish, *trừ* note có
frontmatter đặt `publish: false`. Phù hợp cho wiki cả-vault - bạn viết note là nó
lên site, chỉ ẩn vài note riêng tư:

```markdown
---
title: Bản nháp riêng tư
publish: false
---

Note này không lên site.
```

Wikilink (`[[Note]]`), embed note (`![[Note]]`), embed tệp đính kèm
(`![[image.png]]`) và `#tags` đều hoạt động; tệp đính kèm được tự động chép vào
output. File `_index.md` kiểu Hugo trở thành trang đại diện của thư mục (route về
gốc thư mục). Nếu muốn opt-in từng note, **bật** **Publish marked notes only** -
khi đó note chỉ lên khi đặt `publish: true`.

## Xem trước trang

- Chạy lệnh **Preview site (live)** (hoặc bấm biểu tượng quả cầu ở thanh ribbon).
  Plugin khởi động một dev server và mở khung xem trước ngay trong Obsidian. Sửa
  một note thì khung xem trước tự tải lại.
- Chạy **Open preview in browser** để xem cùng trang đó trên trình duyệt hệ thống.
- Chạy **Stop preview server** khi xong.

## Build và export

- Chạy **Build site** để render toàn bộ trang một lần. Thông báo cho biết đã ghi
  bao nhiêu trang và ở đâu.
- Chạy **Open output folder** để mở thư mục kết quả trong trình quản lý tệp. Từ
  đó bạn có thể deploy (xem [Deploy một trang đã build](../how-to/deploy.md)).

Output được ghi vào một thư mục làm việc **ngoài** vault, nên các tệp build không
bao giờ lẫn vào ghi chú hay bị Obsidian index lại.

## Cài đặt

| Cài đặt | Điều khiển |
| --- | --- |
| Publish marked notes only | Tắt (mặc định) = publish tất trừ `publish: false`; bật = allowlist, chỉ publish `publish: true`. |
| Base URL | URL tuyệt đối của site, dùng cho sitemap và RSS. |
| Content subfolder | Chỉ build một thư mục con của vault (mặc định: cả vault). |
| Exclude / Include globs | Bộ lọc cách nhau bằng dấu phẩy, *cộng thêm* vào các mục luôn bị loại: `.obsidian`, `.trash`, `.git` và các thư mục Templates / Daily notes mà plugin tự đọc từ cấu hình vault của bạn. |
| Preview server | Host và port cho xem trước trực tiếp. |
| pyssg executable | Dùng một `pyssg` có sẵn thay cho runtime tự quản. |
| pyssg version (git ref) | Nhánh, tag hoặc commit được cài khi tự dựng runtime. |
| Reset managed runtime | Xoá runtime đã tải để dựng lại. |

## Dùng pyssg không qua plugin

Plugin chỉ là lớp tiện ích; bạn có thể build cùng vault đó từ terminal với preset
`obsidian`. Tạo một site kiểu vault mới:

```bash
pyssg init --preset obsidian --site my-vault
pyssg --site my-vault build
pyssg --site my-vault serve   # xem trước trực tiếp, tự tải lại
```

Để publish một vault **đã có** mà không thêm tệp cấu hình vào nó, trỏ
`content_dir` vào vault và ghi output ra nơi khác - đây chính là cách plugin làm:

```python
# pyssg.config.py (đặt ngoài vault)
from __future__ import annotations

from pyssg.presets import obsidian

config = obsidian(
    site={"title": "My Vault"},
    base_url="https://example.com",
    content_dir="/duong/dan/tuyet/doi/toi/vault",
    output_dir="/duong/dan/tuyet/doi/toi/output",
    publish_required=False,           # denylist (mặc định); True = allowlist (chỉ publish: true)
    exclude=["Templates/**"],          # cộng thêm vào mặc định .obsidian/.trash/.git
)
```

Sau đó `pyssg --site <thư-mục-chứa-config> build`. Xem [tham chiếu
CLI](../reference/cli.md) và [tham chiếu cấu hình](../reference/configuration.md)
để biết mọi tuỳ chọn.

## Cách runtime Python được dựng tự động

Lần đầu build hoặc xem trước, plugin tải [uv](https://docs.astral.sh/uv/) (một
binary tĩnh nhỏ gọn), dùng nó cài một Python tự quản và một bản pyssg độc lập, rồi
lưu cache vào thư mục dữ liệu ứng dụng dùng chung - không bao giờ nằm trong vault.
Việc này chạy một lần ở chế độ nền; sau đó build khởi động tức thì. Hãy ghim phiên
bản pyssg qua cài đặt **pyssg version (git ref)** để cài đặt tái lập được.

## Khắc phục sự cố

- **Dựng runtime lỗi hoặc treo.** Dùng **Reset managed runtime** trong cài đặt
  rồi build lại để dựng lại từ đầu.
- **Máy offline hoặc bị quản lý.** Tự cài pyssg và đặt đường dẫn **pyssg
  executable** trong cài đặt; plugin sẽ bỏ qua bước tải.
- **Một note không chịu publish.** Kiểm tra frontmatter có `publish: true` (ở chế
  độ allowlist) và note không nằm trong thư mục bị loại.

## Bước tiếp theo

- [Deploy một trang đã build](../how-to/deploy.md) - publish output đã tạo.
- [Tham chiếu CLI](../reference/cli.md) - mọi lệnh và cờ của `pyssg`.
