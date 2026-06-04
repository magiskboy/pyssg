---
title: Build tăng tiến và tính tất định
nav_title: Build tăng tiến
order: 4
---

# Build tăng tiến và tính tất định

Tính chất quan trọng nhất của PySSG là bất biến này:

> **Một lần build tăng tiến giống hệt từng byte so với build lại toàn bộ.**

Mọi thứ trong engine tăng tiến tồn tại để giữ vững nó. Trang này giải thích điều đó
nghĩa là gì và đạt được bằng cách nào.

## Tính tất định trước tiên

Trước khi build tăng tiến có thể *đúng*, build phải **tất định**: build cùng đầu
vào hai lần cho ra kết quả giống nhau từng byte. PySSG thực thi điều này bằng cách
làm cho mỗi đơn vị xử lý thuần khiết theo các đầu vào đã khai báo:

- không có trạng thái toàn cục có thể thay đổi,
- không gọi trực tiếp `datetime.now()`, `time` hay `random`,
- các node và thành viên được xuất theo một thứ tự ổn định, đã sắp xếp.

Tính tất định là thứ làm cho "tăng tiến == toàn bộ" *kiểm tra được*: nếu build đầy
đủ là bất định, sẽ không có một mục tiêu cố định để đối chiếu.

## Build tăng tiến hoạt động thế nào

Một build đầy đủ đánh dấu mọi node "bẩn" từ pha `LOAD` và xử lý toàn bộ đồ thị. Một
build tăng tiến thay vào đó:

1. **Gieo một danh sách công việc** từ các sự kiện hệ thống tệp (một file được tạo,
   sửa, di chuyển hoặc xóa).
2. **Băm các khía cạnh (aspect)** của mỗi node (byte thô, nội dung đã phân tích,
   metadata) và so với các băm đã cache.
3. **Chỉ lan truyền những thay đổi thật** dọc theo các cạnh phụ thuộc, hội tụ về
   điểm bất động với cắt sớm (early cutoff) - nếu khía cạnh liên quan của một node
   không đổi, công việc dừng tại đó và các node phía sau được lấy từ cache.

Vì quy trình xử lý theo từng node và từng trang là *cùng một đoạn mã* mà build đầy
đủ chạy, một node được build lại không thể lệch khỏi phiên bản build đầy đủ của nó.

## Một ví dụ cụ thể: điều hướng

Điều hướng xuất hiện trên mọi trang, nên nó là trường hợp kinh điển "làm sao thứ
này có thể tăng tiến được?". PySSG xử lý nó mà không cần đặc cách gì trong plugin
`nav`:

- Một thay đổi **cấu trúc** (thêm, di chuyển hoặc xóa một tài liệu) làm đổi menu.
  Do đó HTML render của mọi trang khác đi và được xuất lại - đúng đắn.
- Một sửa đổi **chỉ ở thân bài** giữ menu y nguyên. Các trang khác băm ra cùng HTML
  render, trúng cache render, và không bị xuất lại.

Plugin chỉ khai báo menu như một sự kiện; vòng quét render của engine quyết định
cái gì thực sự đã đổi. Đây là khuôn mẫu chung: **plugin khai báo sự kiện, engine sở
hữu việc vô hiệu hóa.**

## Vì sao plugin không được quản lý cache

Nếu một plugin cố tự lan truyền tính "bẩn" của mình hoặc thọc vào cache, hai plugin
có thể bất đồng về cái gì đã đổi và bất biến sẽ vỡ. Giữ toàn bộ việc vô hiệu hóa
trong phần lõi - dựa trên băm nội dung và các cạnh đồ thị - là thứ cho phép nhiều
plugin độc lập kết hợp mà không phá vỡ khả năng tái lập từng byte.

## Kiểm thử bất biến

Bất biến này không phải khẩu hiệu; nó được kiểm thử. Bộ kiểm tra của dự án bao gồm
các test biên (boundary), một test tính tất định (build hai lần, so byte), và một
test `tăng tiến == toàn bộ`. Một thay đổi làm hỏng bất kỳ test nào trong số này sẽ
không được merge.
