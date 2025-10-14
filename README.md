# Hướng Dẫn Chạy Dự Án

## 🪟 Trên Windows

### 1. Yêu cầu

- Đã cài **Python 3.10+**
- Đã cài **Git** (nếu clone từ repo)
- Đường dẫn Python đã được thêm vào **PATH**

### 2. Tạo môi trường ảo

Mở **CMD** hoặc **PowerShell** tại thư mục dự án (chứa `src`), sau đó chạy:

```bash
python -m venv .venv
.venv\Scripts\activate
```

### 3. Nếu PowerShell báo lỗi policy

Chạy lệnh sau để cho phép script chạy:

```bash
Set-ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### 4. Cách build dự án

Nếu có thêm màn hình mới, thêm dòng sau vào `build.bat`:

```
--hidden-import <tên_màn_hình_mới>
```

Sau đó chạy `build.bat` để build.

### 5. Nếu báo thiếu driver khi bấm "Check Connection"

Cài thêm thư viện Oracle:

```bash
pip install oracledb
```

Hoặc nếu vẫn lỗi:

```bash
pip install cx_Oracle
```

---

## 🐧 Trên Ubuntu / WSL

### 1. Cài đặt Python và module venv

```bash
sudo apt update
sudo apt install python3 python3-venv -y
```

### 2. Tạo môi trường ảo

Tại thư mục dự án (ví dụ: `~/Tools/ToolOnwa`):

```bash
python3 -m venv .venv
```

### 3. Kích hoạt môi trường ảo

```bash
source .venv/bin/activate
```

Khi kích hoạt thành công, bạn sẽ thấy tiền tố:

```
(.venv) ntd@DESKTOP-MLDRP0U:~/Tools/ToolOnwa$
```

### 4. Cài đặt thư viện cần thiết

```bash
pip install -r requirements.txt
```

Hoặc cài riêng:

```bash
pip install requests pandas
```

### 5. Chạy chương trình

```bash
python main.py
```

### 6. Thoát khỏi môi trường ảo

```bash
deactivate
```

### 7. Gợi ý bổ sung

Nếu muốn alias `python` trỏ tới `python3`, chạy:

```bash
echo "alias python=python3" >> ~/.bashrc
source ~/.bashrc
```

---

## 🧰 Chức năng cơ sở dữ liệu

- **Insert**: chọn bảng bằng khung tìm kiếm, dán/nhập dữ liệu trực tiếp vào lưới, xuất/nhập CSV và tạo câu lệnh `INSERT`. Công cụ kiểm tra khóa chính trùng với database, hiển thị màn hình so sánh và (nếu đồng ý) xóa/insert lại.
- **Update**: thao tác giống Insert nhưng sinh câu `UPDATE` với điều kiện xác định theo khóa chính hoặc biểu thức `{{COLUMN}}` trong khung điều kiện.
- **Backup/Restore**:
  - Bấm `Backup/Restore` ở màn hình chính → chọn `Backup` hoặc `Restore`.
  - **Backup**: tự động gợi ý tên bảng sao lưu dạng `_BK_YYYYMMDD`; có thể chỉnh sửa SQL (ví dụ thêm `WHERE`) trước khi thực thi và xem log ngay trên màn hình.
  - **Restore từ bảng backup**: sinh sẵn câu `TRUNCATE` + `INSERT` từ bảng backup. Người dùng có thể chỉnh sửa SQL rồi chạy.
  - **Restore từ CSV**: bắt buộc chọn bảng đích trước khi import. Công cụ kiểm tra header trùng khớp cột trong bảng, hiển thị dữ liệu trong lưới để xác nhận và log chi tiết khi ghi vào database.
- Trong mọi màn hình, dữ liệu có thể copy kèm header, thay đổi thứ tự cột, nhập xuất CSV và xem log ngay tại chỗ.
