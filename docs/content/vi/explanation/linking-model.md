---
title: Mô hình liên kết
nav_title: Mô hình liên kết
order: 5
---

# Mô hình liên kết

PySSG coi liên kết là dữ liệu hạng nhất, không chỉ là văn bản trong đầu ra. Đó là
thứ khiến wikilink, transclusion, backlink và liên kết nội bộ an toàn cùng hoạt
động ăn khớp.

## Liên kết Markdown nội bộ

Một liên kết Markdown thông thường tới một file `.md` cục bộ được viết lại thành URL
đã phân giải của trang đích, và một connection `LINK` chiều ngược được ghi lại để
backlink hoạt động:

```markdown
See [getting started](getting-started.md).
```

Việc phân giải diễn ra trong `evaluate_collections`, sau khi mọi tài liệu đã được
phân tích và mọi URL trang đã biết. Việc viết lại luôn bắt đầu từ HTML trước-phân-
giải của tài liệu, nên nếu một đích bị di chuyển hoặc đổi tên, liên kết sẽ cập nhật
ở lần finalize kế tiếp - dù tài liệu *chứa liên kết* không hề được sửa lại. Nội dung
đã viết lại được băm lại, và đó chính xác là thứ khiến vòng quét render render lại
một trang có đích liên kết đã đổi (giữ tăng tiến == toàn bộ).

## Wikilink

Plugin `wikilink` thêm các liên kết kiểu Obsidian `[[...]]`, phân giải theo tiêu đề
hoặc tên file đích:

```markdown
Read about [[Core concepts]] next.
```

Wikilink chạy sớm trong waterfall `finalize_content` (stage 100), trước khi phân
giải liên kết nội bộ thông thường (stage 200), nên đến lúc các plugin khác thấy
HTML thì wikilink đã là các href bình thường.

## Transclusion

`![[...]]` *nhúng* nội dung đã finalize của một tài liệu khác vào trang hiện tại,
thay vì chỉ liên kết tới nó:

```markdown
![[shared/disclaimer]]
```

Transclusion chạy trong `expand_content`, sau `finalize_content`, vì nó cần HTML
*đã finalize* của tài liệu được nhúng (liên kết đã phân giải) để chèn vào.

## Backlink

Vì mỗi liên kết đã phân giải được lưu thành một cạnh chiều ngược trong đồ thị, PySSG
có thể hiển thị, trên bất kỳ trang nào, những trang nào khác liên kết tới nó - mà
không cần cấu hình thêm. Danh sách backlink được suy ra từ chính các connection
`LINK` mà bộ phân giải ghi lại, nên nó luôn nhất quán với các liên kết thực sự
trong nội dung của bạn.

## Phát hiện liên kết hỏng

Vì liên kết được phân giải dựa trên đồ thị tài liệu thật, một liên kết có đích không
tồn tại sẽ phát hiện được thay vì âm thầm tạo ra một href chết. Đây là nửa còn lại
của việc coi liên kết là dữ liệu: bạn biết ngay lúc build, không phải lúc người đọc
bấm vào.

## Liên kết ngoài

Các liên kết có lược đồ URL (`http:`, `mailto:`, ...) được bộ phân giải nội bộ để
yên. Plugin contrib tùy chọn `external_links` có thể viết lại các anchor ra ngoài
site để mở trong tab mới với `rel="noopener noreferrer"`; nó gắn vào
`finalize_content` ở stage 300, sau wikilink và phân giải nội bộ, nên chỉ thấy các
href cuối cùng.
