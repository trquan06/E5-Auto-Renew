# MS365 Auto Renew 2.0

[English](README.md) · [Triển khai](docs/DEPLOYMENT.md) · [Thiết lập Microsoft Entra](docs/ENTRA_SETUP.md) · [Vận hành](docs/OPERATIONS.md) · [Bảo mật](SECURITY.md)

MS365 Auto Renew là WebUI tự lưu trữ dùng để lên lịch các khối lượng phát triển và kiểm thử thông qua quyền Microsoft Graph dạng ủy quyền. Phiên bản 2.0 bổ sung thiết lập lần đầu an toàn, lưu token có mã hóa, giao diện responsive ba ngôn ngữ và quy trình phát hành container có thể tái lập.

> **Quan trọng:** đây là dự án mã nguồn mở độc lập, không liên kết hoặc được Microsoft bảo trợ. Ứng dụng không bảo đảm tư cách thành viên hay việc gia hạn gói Microsoft 365 Developer. Chỉ Microsoft quyết định điều kiện hợp lệ. Chỉ dùng với tài khoản, tenant và dữ liệu bạn được phép quản lý, đồng thời tuân thủ điều khoản và chính sách Microsoft áp dụng.

![Xem trước Dashboard](docs/images/dashboard.jpg)

## Điểm nổi bật

- Chỉ hỗ trợ OAuth ủy quyền; không còn chế độ app-only.
- Mã thiết lập dùng một lần được in vào log máy chủ, hết hạn sau 15 phút, không thể tái sử dụng; mật khẩu quản trị tối thiểu 12 ký tự.
- Hash mật khẩu PBKDF2, OAuth state có chữ ký và thời hạn, token mã hóa bằng khóa bền vững, giới hạn tốc độ login/setup, kiểm soát redirect theo origin và không có mật khẩu mặc định.
- Mặc định tiếng Anh, kèm tiếng Việt và tiếng Trung giản thể; ghi nhớ ngôn ngữ và theme ở trình duyệt.
- Dashboard, tài khoản, lịch tác vụ, log thực thi, cấu hình thông báo, trạng thái tải/trống/lỗi, hộp xác nhận và focus bàn phím rõ ràng.
- Tailwind CSS và Chart.js được ghim phiên bản, phục vụ cục bộ; không phụ thuộc CDN khi chạy.
- CI Python 3.11/3.12, Docker smoke test, quét dependency/secret/image và phát hành GHCR đa kiến trúc.

## Khởi động nhanh bằng Docker

Yêu cầu Docker Engine 24+ và Docker Compose v2.

```bash
git clone https://github.com/trquan06/E5-Auto-Renew.git
cd ms365-auto-renew
cp .env.example .env
docker compose -f compose.build.yml up -d --build
docker compose -f compose.build.yml logs webui
```

Mở `http://localhost:8080`, lấy mã thiết lập trong log, tạo mật khẩu quản trị rồi đăng nhập. Mã hết hạn sau 15 phút và thay đổi nếu ứng dụng khởi động lại trước khi hoàn tất thiết lập.

Nếu dùng image phát hành, thay `OWNER` trong `compose.yml`, sau đó chạy:

```bash
docker compose up -d
docker compose logs webui
```

Database SQLite, khóa mã hóa và trạng thái runtime nằm tại `/app/data`. Hãy giữ volume này bền vững và riêng tư. Với bind mount trên Linux, UID/GID `10001` phải có quyền ghi thư mục data ở host.

## Chạy bằng Python

Yêu cầu Python 3.11 hoặc 3.12 và Node.js 20.

```bash
python -m venv .venv
source .venv/bin/activate  # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
npm ci
npm run build
python run.py
```

Lần chạy đầu sẽ in mã thiết lập trong terminal. Dùng `pytest -q` để chạy kiểm thử.

## Callback Microsoft Entra

Tạo app registration trong Entra và thêm chính xác redirect URI kiểu **Web**:

```text
https://ORIGIN-WEBUI-CUA-BAN/api/accounts/oauth/callback
```

Khi thử cục bộ, dùng `http://localhost:8080/api/accounts/oauth/callback`. Nếu có reverse proxy, đặt `PUBLIC_BASE_URL` bằng origin HTTPS mà trình duyệt truy cập. Không thêm path hoặc dấu gạch chéo cuối. Xem [hướng dẫn quyền ủy quyền đầy đủ](docs/ENTRA_SETUP.md).

## Cấu hình

Sao chép `.env.example` thành `.env`.

| Biến | Mặc định | Công dụng |
|---|---:|---|
| `DATA_DIR` | `./data` cục bộ, `/app/data` trong Docker | Database và khóa mã hóa tự sinh |
| `PUBLIC_BASE_URL` | trống | Origin WebUI bên ngoài dùng cho OAuth redirect |
| `ALLOWED_ORIGINS` | trống | Các origin tin cậy bổ sung, phân tách dấu phẩy; không dùng wildcard |
| `SECRET_KEY` | tự sinh | Ghi đè khóa bền vững; đổi khóa làm session và token cũ không đọc được |
| `DEFAULT_TIMEZONE` | `UTC` | Múi giờ IANA mặc định cho lịch mới |
| `LOG_RETENTION_DAYS` | `30` | Mục tiêu lưu log vận hành |

`WEBUI_PASSWORD` chỉ là cầu nối nâng cấp v1. Biến này không có giá trị mặc định, sẽ được hash vào database lúc khởi động và nên được xóa khỏi môi trường sau đó.

## Dữ liệu và bảo mật

- Không công khai `.env`, `data/renew.db`, `data/secret.key`, file sidecar database, log, token hoặc bản sao lưu.
- Sao lưu cả volume data để database luôn đi cùng đúng `secret.key`.
- Đặt triển khai từ xa sau reverse proxy HTTPS; `PUBLIC_BASE_URL` phải trùng origin mà trình duyệt nhìn thấy.
- Authorization code chỉ được giữ đủ lâu để đổi token, sau đó bị xóa khỏi URL callback và payload của cửa sổ OAuth.
- Đọc [SECURITY.md](SECURITY.md) trước khi mở dịch vụ ra mạng.

## Cập nhật, rollback và sao lưu

Làm theo [Operations](docs/OPERATIONS.md): sao lưu `/app/data`, kéo image mới, tạo lại container, kiểm tra `/health` và giữ tag image bất biến trước đó để rollback. Không phục hồi riêng database nếu thiếu khóa mã hóa tương ứng.

## Đóng góp và giấy phép

Xem [CONTRIBUTING.md](CONTRIBUTING.md). Dự án dùng [MIT License](LICENSE).
