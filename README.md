# ToolONWA VIP v1.0

## Tổng quan

ToolONWA là ứng dụng desktop (Tkinter) hỗ trợ thao tác nhanh với cơ sở dữ liệu Oracle trong môi trường nội bộ.  
Mục tiêu chính:

- Quản lý cấu hình kết nối Oracle (tnsnames, danh sách alias, tùy chọn kiểm tra kết nối).
- Sinh và thực thi câu lệnh INSERT/UPDATE hàng loạt (bao gồm kiểm tra khóa chính, so sánh dữ liệu với DB).
- Tạo/khôi phục backup bảng, import/export dữ liệu CSV.
- Đọc log hệ thống MU, lọc theo màn hình, SQL/ERROR và xem chi tiết truy vấn.
- Quản lý danh sách máy chủ RDS phục vụ thao tác kết nối nhanh.

Ứng dụng sử dụng cơ chế đa ngôn ngữ (Việt – Nhật) thông qua module `core/i18n.py`.

## Chức năng chính

- **Màn hình chính (`main.py`)**
  - Chọn alias TNS, chỉnh sửa kết nối, kiểm tra trạng thái.
  - Mở các màn hình tiện ích (Insert/Update/Backup, Log MU, RDS Info, SQL*Plus).
  - Lựa chọn ngôn ngữ hiển thị, lưu cấu hình vào thư mục `configs/`.

- **Insert (`screen/DB/insert.py`)**
  - Tải danh sách bảng người dùng, xem metadata, sinh câu lệnh INSERT theo dữ liệu nhập.
  - Kiểm tra trùng khóa chính với DB, cho phép xóa dòng trùng trước khi ghi.
  - Hỗ trợ nhập/xuất dữ liệu CSV.

- **Update (`screen/DB/update.py`)**
  - Tương tự Insert nhưng sinh câu lệnh UPDATE.
  - Cho phép thêm điều kiện bổ sung bằng placeholder `{{COLUMN}}`.

- **Backup/Restore (`screen/DB/backup.py`)**
  - Sinh script backup bảng, chạy trực tiếp và ghi log.
  - Restore từ bảng backup hoặc từ CSV (kiểm tra header, ghi log từng bước).

- **Log Viewer MU (`screen/MU/log_viewer.py`)**
  - Đọc file log, lọc theo màn hình, loại lệnh (SQL/ERROR), thời gian.
  - Xem chi tiết SQL, Error, sao chép nội dung nhanh.

- **RDS Info (`screen/General/rdsinfo.py`)**
  - Quản lý danh sách subsystem/host RDS, hỗ trợ xem/copy nhanh thông tin.


## Yêu cầu hệ thống

- Python 3.11 (khuyến nghị 3.10+)
- Windows/macOS/Linux (đã kiểm thử trên Windows 10/11, Ubuntu 22.04, macOS Ventura với Python từ hệ thống hoặc Homebrew).
- Gói bổ sung (cài qua `pip`):
  - `oracledb` hoặc `cx_Oracle` nếu cần kết nối Oracle thực.
  - `pyinstaller` (chỉ khi build file .exe).
  - Các gói chuẩn khác sử dụng trong dự án (nếu có) – khuyến nghị giữ file `requirements.txt` để cài tự động.


## Hướng dẫn thiết lập & chạy

### 1. Trên Windows (CMD hoặc PowerShell)

1. **Cài đặt Python 3.11** (nhớ chọn “Add to PATH”).
2. **Tạo môi trường ảo**:
   ```bash
   cd đường_dẫn_tới_thư_mục_project
   python -m venv .venv
   .venv\Scripts\activate
   ```
   Nếu PowerShell chặn script, chạy `Set-ExecutionPolicy RemoteSigned -Scope CurrentUser`.
3. **Cài đặt thư viện**:
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt      # sử dụng file đã cung cấp
   ```
4. **Chạy ứng dụng**:
   ```bash
   python main.py
   ```
5. **Build file .exe** (tùy chọn):
   - Chạy `build.bat`, file kết quả nằm trong `dist/ToolONWA.exe`.

### 2. Trên macOS

1. **Cài Python 3.11** (ví dụ: `brew install python@3.11`).
2. **Tạo môi trường ảo**:
   ```bash
   cd /đường/dẫn/tới/project
   python3 -m venv .venv
   source .venv/bin/activate
   ```
3. **Cài thư viện**:
   ```bash
   pip install --upgrade pip
    pip install -r requirements.txt
   ```
   *Lưu ý:* nếu dùng `oracledb/cx_Oracle`, cần cài Instant Client của Oracle hoặc cấu hình phù hợp.
4. **Chạy chương trình**:
   ```bash
   python main.py
   ```
5. **Thoát môi trường ảo**: `deactivate`.

### 3. Trên Ubuntu / Debian

1. **Cài Python và venv**:
   ```bash
   sudo apt update
   sudo apt install python3 python3-venv python3-pip -y
   ```
2. **Tạo môi trường ảo**:
   ```bash
   cd ~/project/ToolONWA
   python3 -m venv .venv
   source .venv/bin/activate
   ```
3. **Cài thư viện**:
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```
4. **Chạy ứng dụng**:
   ```bash
   python main.py
   ```
5. (Tùy chọn) Tạo alias `python=python3` trong `~/.bashrc`:
   ```bash
   echo "alias python=python3" >> ~/.bashrc
   source ~/.bashrc
   ```

### Ghi chú chung

- Môi trường sản xuất nên đặt log, cấu hình, templates trong `configs/` (tự động tạo nếu chưa có).
- Khi dùng Oracle thật, cần đảm bảo máy có thể truy cập TNS/tnsnames.ora, driver Oracle đầy đủ.
- Nếu build cross-platform (ví dụ build .exe trên macOS/Linux) cần dùng PyInstaller tương ứng và cấu hình icon/asset phù hợp.

Chúc bạn sử dụng ToolONWA hiệu quả!
