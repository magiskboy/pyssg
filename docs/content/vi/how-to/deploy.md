---
title: Triển khai trang đã build
nav_title: Triển khai
order: 6
---

# Triển khai trang đã build

**Mục tiêu:** xuất bản đầu ra tĩnh do `build` tạo ra.

## 1. Tạo một bản build sạch

```bash
pyssg --site my-site build
```

Mọi thứ cần triển khai giờ nằm trong thư mục đầu ra (mặc định `dist/`; đặt
`output_dir` trong cấu hình để đổi). Đầu ra là một cây HTML, CSS và asset thuần -
không cần runtime máy chủ nào.

## 2. Đặt `base_url`

Nếu trang của bạn được phục vụ từ một đường dẫn con (ví dụ một trang dự án GitHub
Pages tại `https://user.github.io/repo`), hãy đặt `base_url` để các URL tuyệt đối
được sinh - sitemap, RSS feed và thẻ `hreflang` - đều chính xác:

```python
config = docs(
    site={"title": "My Docs"},
    base_url="https://user.github.io/repo",
)
```

## 3. Triển khai bằng `pyssg deploy`

PySSG có sẵn lệnh deploy tích hợp cho các host phổ biến. Khai báo tùy chọn theo
từng target dưới `Config.deploy` (khóa là tên target), rồi chạy
`pyssg deploy <target>`. Lệnh sẽ build trang, tải đầu ra lên, và ghi lại kết quả
để lần chạy sau với đầu ra giống hệt từng byte trở thành no-op.

```python
config = docs(
    site={"title": "My Docs"},
    base_url="https://user.github.io",
    deploy={
        # GitHub Pages: đẩy dist/ lên một nhánh nội dung. Xác thực qua `gh` CLI
        # hoặc biến môi trường GITHUB_TOKEN.
        "github-pages": {"repo": "user/repo"},  # cùng các tùy chọn branch, cname, ...
        # Cloudflare Pages: xác thực qua biến môi trường CLOUDFLARE_API_TOKEN.
        "cloudflare": {"account_id": "...", "project": "my-site"},
        # Netlify: xác thực qua biến môi trường NETLIFY_AUTH_TOKEN.
        "netlify": {"site_id": "..."},
    },
)
```

Thông tin xác thực luôn được đọc từ môi trường, không bao giờ từ file cấu hình.
Sau đó triển khai:

```bash
pyssg --site my-site deploy list           # các target đã cấu hình + cái nào đã hiện thực
pyssg --site my-site deploy github-pages   # build và xuất bản
pyssg --site my-site deploy status         # bản ghi lần deploy gần nhất theo target
```

Mỗi subcommand target nhận `--dry-run` (kiểm tra và báo cáo những gì sẽ tải lên,
nhưng không đẩy), `--force` (deploy lại kể cả khi đầu ra không đổi), `--skip-build`
(dùng lại thư mục đầu ra sẵn có) và `--skip-check` (bỏ qua bước kiểm tra sau build).
Xem [tham chiếu CLI](../reference/cli.md) để biết toàn bộ.

Các target tích hợp xuất bản từ gốc tên miền (một trang user/org GitHub Pages hoặc
một tên miền tùy chỉnh), nên hãy giữ `base_url` ở gốc - một trang dự án phục vụ từ
đường dẫn con `/repo/` chưa được các target này hỗ trợ; hãy triển khai thủ công
thay thế.

## 4. Hoặc tải `dist/` lên thủ công

Với một host không có target tích hợp, hãy tự trỏ nó vào thư mục đầu ra. Một vài
đích phổ biến:

- **GitHub Pages** - đẩy nội dung `dist/` lên nhánh `gh-pages`, hoặc dùng một Pages
  action tải thư mục lên làm artifact.
- **Netlify / Cloudflare Pages / Vercel** - đặt lệnh build là
  `pyssg --site my-site build` và thư mục xuất bản là
  `my-site/dist`.
- **Bất kỳ web server / object storage nào** - sao chép `dist/` vào document root
  hoặc bucket.

## 5. Giữ build có thể tái lập trong CI

Build của PySSG là tất định: với cùng đầu vào, hai lần build cho ra kết quả giống
nhau từng byte. Trong CI, hãy chạy một lần `build` đầy đủ (cache là tối ưu, không
phải yêu cầu về tính đúng đắn) - truyền `--no-cache` nếu bạn muốn chứng minh một
bản build sạch từ đầu:

```bash
pyssg --site my-site build --no-cache
```

Để xóa thư mục đầu ra và cache ở máy cục bộ, dùng `clean`:

```bash
pyssg --site my-site clean --yes
```
