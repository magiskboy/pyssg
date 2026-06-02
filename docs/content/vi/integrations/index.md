---
title: Tích hợp
nav_title: Tổng quan
order: 1
---

# Tích hợp

Các tích hợp kết nối pyssg với những công cụ bạn đang dùng để viết. Mỗi tích hợp
là một **adapter** chính thức - một lớp mỏng điều khiển quá trình build của pyssg
từ một ứng dụng khác - nằm trong thư mục `adapters/<tên>/` của dự án với bộ công
cụ riêng.

Adapter không tách nhánh engine: chúng gọi ra dòng lệnh `pyssg` (hoặc Python API)
và tái dùng đúng các plugin, preset và cơ chế build tăng dần mà CLI dùng. Build
được gì từ terminal thì adapter build y như vậy.

## Các tích hợp hiện có

- **[Obsidian](obsidian.md)** - publish một vault Obsidian thành trang tĩnh:
  wikilink, embed, tệp đính kèm và publish chọn lọc, kèm xem trước trực tiếp
  ngay trong trình soạn thảo.

Sẽ có thêm các tích hợp khác (các ứng dụng ghi chú và soạn thảo khác) xuất hiện ở
đây khi hoàn thiện. Tất cả đều theo cùng một khuôn mẫu, nên những khái niệm bạn
học cho một adapter đều áp dụng được cho adapter tiếp theo.
