
# Quy tắc

- Tuân thủ các quy tắc của Python 3.13
- Tuân thủ nghiêm ngặt type checking của Python
- Simple first, performance và clean code
- Không sử dụng emoji, viết code chuẩn design thay vì lạm dụng comment
- Trong code (comment, docstring, tên định danh, chuỗi log/error) chỉ sử dụng tiếng Anh
- Khi phản hồi người dùng chỉ sử dụng tiếng Việt

# Development

- Sử dụng uv - python làm python package manager
- Luôn sử dụng virtualenv thông qua: source .venv/bin/activate
- Hạn chế sử dụng thư viện bên thứ 3
- Những tính năng / design mới nên brainstorm trước khi thực hiện

# Testing

- Luôn có unit test cho từng đoạn code tự viết
- Chỉ sư dụng unittest module có săn của Python
- Tuân thủ test regression