# Hướng dẫn chạy dự án trên Windows

## 1. Yêu cầu

- Đã cài **Python 3.10+**
- Đã cài **Git** (nếu clone từ repo)
- Đường dẫn Python đã được thêm vào **PATH**

---

## 2. Cài môi trường ảo

Mở CMD hoặc PowerShell tại thư mục dự án (chứa `src`) rồi chạy:

```bash
python -m venv .venv
.venv\Scripts\activate
```

## 3. Nếu PowerShell báo lỗi policy

Chạy lệnh sau

```bash
Set-ExecutionPolicy RemoteSigned -Scope CurrentUser
```

## 4. Cách build dự án

Nếu có thêm màn hình mới thì thêm `bash--hidden-import <màn hình>` vào file build.bat
sau đó chạy file build.bat để build

## 4. Nếu báo thiếu driver khi bấm Check Connection

Chạy lệnh sau

```bash
pip install oracledb
```

hoặc

```bash
pip install cx_Oracle
```
