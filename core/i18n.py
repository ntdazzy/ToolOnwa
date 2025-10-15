"""Quản lý ngôn ngữ tập trung cho toàn bộ ứng dụng."""

from __future__ import annotations

from typing import Callable, Dict

LANG_VI = "VN"
LANG_JP = "JP"

_current_language: str = LANG_VI
_listeners: list[Callable[[str], None]] = []

TRANSLATIONS: Dict[str, Dict[str, str]] = {
    # --- Chuỗi dùng chung ---
    "common.ok": {LANG_VI: "Đồng ý", LANG_JP: "OK"},
    "common.cancel": {LANG_VI: "Hủy", LANG_JP: "キャンセル"},
    "common.close": {LANG_VI: "Đóng", LANG_JP: "閉じる"},
    "common.copy": {LANG_VI: "Sao chép", LANG_JP: "コピー"},
    "common.yes": {LANG_VI: "Có", LANG_JP: "はい"},
    "common.no": {LANG_VI: "Không", LANG_JP: "いいえ"},
    "common.warning": {LANG_VI: "Cảnh báo", LANG_JP: "警告"},
    "common.error": {LANG_VI: "Lỗi", LANG_JP: "エラー"},
    "common.info": {LANG_VI: "Thông báo", LANG_JP: "通知"},
    "common.unknown_error": {LANG_VI: "Không rõ lỗi.", LANG_JP: "不明なエラーです。"},
    "common.loading_tables": {LANG_VI: "Đang tải danh sách bảng...", LANG_JP: "テーブル一覧を読み込み中..."},

    # --- Màn hình chính ---
    "main.section.db": {LANG_VI: "DB", LANG_JP: "DB"},
    "main.section.connection": {LANG_VI: "Thiết lập kết nối", LANG_JP: "接続設定"},
    "main.section.actions": {LANG_VI: "Tác vụ", LANG_JP: "操作"},
    "main.section.mu": {LANG_VI: "MU", LANG_JP: "MU"},
    "main.section.common": {LANG_VI: "Chung", LANG_JP: "共通"},

    "main.label.user_id": {LANG_VI: "User ID", LANG_JP: "ユーザーID"},
    "main.label.password": {LANG_VI: "Mật khẩu", LANG_JP: "パスワード"},
    "main.label.data_source": {LANG_VI: "Data Source", LANG_JP: "データソース"},
    "main.label.host_port": {LANG_VI: "Host/Port", LANG_JP: "ホスト/ポート"},
    "main.label.language": {LANG_VI: "Ngôn ngữ", LANG_JP: "言語"},

    "main.btn.show_password": {LANG_VI: "Hiện mật khẩu", LANG_JP: "パスワード表示"},
    "main.chk.sqlplus_hostport": {
        LANG_VI: "SQL Plus kèm host:port",
        LANG_JP: "SQL Plusでホスト/ポートを使用",
    },

    "main.btn.open_ora": {LANG_VI: "Mở tệp Ora", LANG_JP: "tnsnamesを開く"},
    "main.btn.check_connection": {LANG_VI: "Kiểm tra kết nối", LANG_JP: "接続チェック"},
    "main.btn.insert": {LANG_VI: "Insert", LANG_JP: "挿入"},
    "main.btn.update": {LANG_VI: "Update", LANG_JP: "更新"},
    "main.btn.backup": {LANG_VI: "Backup/Restore", LANG_JP: "バックアップ/復元"},
    "main.btn.sqlplus": {LANG_VI: "SQL Plus", LANG_JP: "SQL Plus"},
    "main.btn.compare": {LANG_VI: "So sánh dữ liệu", LANG_JP: "データ比較"},
    "main.btn.edit_conn": {LANG_VI: "Chỉnh sửa kết nối", LANG_JP: "接続編集"},
    "main.btn.read_log_mu": {LANG_VI: "Đọc log MU", LANG_JP: "MUログ読込"},
    "main.btn.rds_info": {LANG_VI: "Thông tin RDS", LANG_JP: "RDS情報"},
    "main.btn.docs": {LANG_VI: "Tài liệu", LANG_JP: "ドキュメント"},
    "main.btn.tips": {LANG_VI: "Bí kíp võ công", LANG_JP: "Tips"},
    "main.btn.details": {LANG_VI: "Chi tiết", LANG_JP: "詳細"},

    "main.status.not_connected": {LANG_VI: "Chưa kết nối", LANG_JP: "未接続"},
    "main.status.created_db_list": {
        LANG_VI: "Đã tạo configs/db_list.json mẫu",
        LANG_JP: "configs/db_list.json のテンプレートを作成しました",
    },

    "main.msg.loaded_tns": {
        LANG_VI: "Đã tải tệp tnsnames.ora mới",
        LANG_JP: "tnsnames.ora を読み込みました",
    },
    "main.msg.no_config_items": {
        LANG_VI: "Không có cấu hình trong configs/db_list.json",
        LANG_JP: "configs/db_list.json に項目がありません。",
    },
    "main.msg.conn_success": {
        LANG_VI: "Kết nối thành công",
        LANG_JP: "接続成功",
    },
    "main.msg.conn_fail": {
        LANG_VI: "Kết nối thất bại",
        LANG_JP: "接続失敗",
    },
    "main.msg.checking_connection": {
        LANG_VI: "Đang kiểm tra kết nối...",
        LANG_JP: "接続を確認しています...",
    },
    "main.msg.no_error_detail": {
        LANG_VI: "Không có chi tiết lỗi.",
        LANG_JP: "詳細情報はありません。",
    },
    "main.msg.coming_soon": {
        LANG_VI: "Tính năng đang được phát triển.",
        LANG_JP: "開発中の機能です。",
    },
    "main.popup.details_title": {
        LANG_VI: "Chi tiết",
        LANG_JP: "詳細",
    },
    "main.msg.missing_credentials": {
        LANG_VI: "Thiếu thông tin kết nối.",
        LANG_JP: "接続情報が不足しています。",
    },
    "main.msg.need_user_pass_alias": {
        LANG_VI: "Vui lòng nhập User/Password/Data Source.",
        LANG_JP: "ユーザー/パスワード/データソースを入力してください。",
    },
    "main.ask.backup_mode": {
        LANG_VI: "Bạn muốn thực hiện Backup hay Restore?\nYes = Backup, No = Restore, Cancel = Hủy.",
        LANG_JP: "バックアップしますか？それともリストアしますか？\nYes = バックアップ, No = リストア, Cancel = 中止。",
    },
    "main.ask.restore_mode": {
        LANG_VI: "Restore từ bảng backup?\nYes = Bảng backup, No = CSV, Cancel = Hủy.",
        LANG_JP: "バックアップテーブルから復元しますか？\nYes = テーブル, No = CSV, Cancel = 中止。",
    },

    # --- Màn hình Insert ---
    "insert.title": {LANG_VI: "Insert", LANG_JP: "Insert"},
    "insert.section.search": {LANG_VI: "Tìm kiếm", LANG_JP: "検索"},
    "insert.label.table_name": {LANG_VI: "Tên bảng", LANG_JP: "テーブル名"},
    "insert.section.actions": {LANG_VI: "Chức năng", LANG_JP: "機能"},
    "insert.section.connection": {LANG_VI: "Thông tin kết nối", LANG_JP: "接続情報"},
    "insert.section.sql": {LANG_VI: "Insert vào {table}", LANG_JP: "{table} へ Insert"},
    "insert.btn.import_csv": {LANG_VI: "Import CSV", LANG_JP: "CSV取り込み"},
    "insert.btn.export_csv": {LANG_VI: "Export CSV", LANG_JP: "CSV書き出し"},
    "insert.btn.add_row": {LANG_VI: "Thêm dòng trống", LANG_JP: "空行追加"},
    "insert.btn.build_sql": {LANG_VI: "Tạo câu Insert", LANG_JP: "Insert文作成"},
    "insert.btn.reorder": {LANG_VI: "Thay đổi vị trí cột", LANG_JP: "列順序変更"},
    "insert.btn.execute": {LANG_VI: "Thực thi", LANG_JP: "実行"},
    "insert.btn.clear": {LANG_VI: "Xóa dữ liệu", LANG_JP: "クリア"},
    "insert.msg.no_data_generate": {
        LANG_VI: "Không có dữ liệu để tạo câu insert.",
        LANG_JP: "Insert文を生成するデータがありません。",
    },
    "insert.msg.no_columns_update": {
        LANG_VI: "Không có cột nào để thay đổi.",
        LANG_JP: "変更可能な列がありません。",
    },
    "insert.msg.no_table": {
        LANG_VI: "Chưa chọn bảng.",
        LANG_JP: "テーブルが選択されていません。",
    },
    "insert.msg.no_data_execute": {
        LANG_VI: "Không có dữ liệu để insert.",
        LANG_JP: "Insertするデータがありません。",
    },
    "insert.msg.confirm_execute": {
        LANG_VI: "Thực thi insert?",
        LANG_JP: "Insertを実行しますか？",
    },
    "insert.msg.not_connected": {
        LANG_VI: "Chưa kết nối database.",
        LANG_JP: "データベースに接続していません。",
    },
    "insert.msg.copy_done": {
        LANG_VI: "Đã copy câu insert.",
        LANG_JP: "Insert文をコピーしました。",
    },
    "insert.msg.clear_confirm": {
        LANG_VI: "Bạn có muốn reset dữ liệu không?",
        LANG_JP: "データをリセットしますか？",
    },
    "insert.msg.pk_missing_confirm": {
        LANG_VI: "Một số dòng thiếu khóa chính, vẫn tiếp tục insert?",
        LANG_JP: "主キーが未入力の行があります。続けて Insert しますか？",
    },
    "insert.msg.check_duplicates_error": {
        LANG_VI: "Lỗi kiểm tra trùng: {error}",
        LANG_JP: "重複チェックエラー: {error}",
    },
    "insert.msg.delete_old_error": {
        LANG_VI: "Lỗi xóa dữ liệu cũ: {error}",
        LANG_JP: "既存データ削除エラー: {error}",
    },
    "insert.msg.insert_error": {
        LANG_VI: "Lỗi insert: {error}",
        LANG_JP: "Insertエラー: {error}",
    },
    "insert.msg.insert_success": {
        LANG_VI: "Insert thành công.",
        LANG_JP: "Insertに成功しました。",
    },
    "insert.msg.metadata_error": {
        LANG_VI: "Lỗi đọc metadata: {error}",
        LANG_JP: "メタデータ取得エラー: {error}",
    },

    # --- Màn hình Update ---
    "update.title": {LANG_VI: "Update", LANG_JP: "Update"},
    "update.section.search": {LANG_VI: "Tìm kiếm", LANG_JP: "検索"},
    "update.section.actions": {LANG_VI: "Chức năng", LANG_JP: "機能"},
    "update.section.connection": {LANG_VI: "Thông tin kết nối", LANG_JP: "接続情報"},
    "update.section.sql": {LANG_VI: "Update ...", LANG_JP: "Update ..."},
    "update.section.condition": {
        LANG_VI: "Điều kiện UPDATE bổ sung (dạng {{COLUMN}} để lấy giá trị dòng)",
        LANG_JP: "追加UPDATE条件（{{COLUMN}} で行の値を使用）",
    },
    "update.msg.no_data_generate": {
        LANG_VI: "Không có dữ liệu để tạo câu update.",
        LANG_JP: "Update文を生成するデータがありません。",
    },
    "update.msg.no_columns_update": {
        LANG_VI: "Không có cột nào để update.",
        LANG_JP: "更新できる列がありません。",
    },
    "update.msg.no_table": {
        LANG_VI: "Chưa chọn bảng.",
        LANG_JP: "テーブルが選択されていません。",
    },
    "update.msg.no_data_execute": {
        LANG_VI: "Không có dữ liệu để update.",
        LANG_JP: "Updateするデータがありません。",
    },
    "update.msg.not_connected": {
        LANG_VI: "Chưa kết nối database.",
        LANG_JP: "データベースに接続していません。",
    },
    "update.msg.confirm_execute": {
        LANG_VI: "Thực thi update?",
        LANG_JP: "Updateを実行しますか？",
    },
    "update.msg.where_missing": {
        LANG_VI: "Thiếu điều kiện WHERE.",
        LANG_JP: "WHERE条件が不足しています。",
    },
    "update.msg.pk_missing": {
        LANG_VI: "Khóa chính {column} bị trống.",
        LANG_JP: "主キー {column} が空です。",
    },
    "update.msg.copy_done": {
        LANG_VI: "Đã copy câu update.",
        LANG_JP: "Update文をコピーしました。",
    },
    "update.msg.clear_confirm": {
        LANG_VI: "Bạn có muốn reset dữ liệu không?",
        LANG_JP: "データをリセットしますか？",
    },
    "update.msg.cursor_error": {
        LANG_VI: "Lỗi cursor: {error}",
        LANG_JP: "カーソルエラー: {error}",
    },
    "update.msg.update_error": {
        LANG_VI: "Lỗi update: {error}",
        LANG_JP: "Updateエラー: {error}",
    },
    "update.msg.update_success": {
        LANG_VI: "Update thành công.",
        LANG_JP: "Updateに成功しました。",
    },
    "update.msg.metadata_error": {
        LANG_VI: "Lỗi đọc metadata: {error}",
        LANG_JP: "メタデータ取得エラー: {error}",
    },

    # --- Màn hình Backup ---
    "backup.title": {LANG_VI: "Backup Table", LANG_JP: "バックアップ"},
    "backup.section.search": {LANG_VI: "Tìm kiếm", LANG_JP: "検索"},
    "backup.section.sql": {LANG_VI: "SQL", LANG_JP: "SQL"},
    "backup.section.log": {LANG_VI: "Log", LANG_JP: "ログ"},
    "backup.label.table": {LANG_VI: "Tên bảng", LANG_JP: "テーブル名"},
    "backup.label.backup_table": {LANG_VI: "Bảng backup", LANG_JP: "バックアップテーブル"},
    "backup.btn.refresh_sql": {LANG_VI: "Cập nhật SQL", LANG_JP: "SQL更新"},
    "backup.btn.execute": {LANG_VI: "Thực thi", LANG_JP: "実行"},
    "backup.msg.not_connected": {
        LANG_VI: "Chưa kết nối database.",
        LANG_JP: "データベースに接続していません。",
    },
    "backup.msg.no_statement": {
        LANG_VI: "Không có câu lệnh để thực thi.",
        LANG_JP: "実行するSQLがありません。",
    },
    "backup.msg.execute_error": {
        LANG_VI: "Lỗi thực thi: {error}",
        LANG_JP: "実行エラー: {error}",
    },
    "backup.msg.execute_success": {
        LANG_VI: "Thực thi thành công.",
        LANG_JP: "実行に成功しました。",
    },
    "backup.msg.metadata_error": {
        LANG_VI: "Lỗi đọc metadata: {error}",
        LANG_JP: "メタデータ取得エラー: {error}",
    },
    "backup.msg.select_table": {
        LANG_VI: "Vui lòng chọn bảng trước khi import.",
        LANG_JP: "取り込み前にテーブルを選択してください。",
    },
    "backup.msg.read_csv_error": {
        LANG_VI: "Lỗi đọc CSV: {error}",
        LANG_JP: "CSV読み込みエラー: {error}",
    },
    "backup.msg.restore_confirm": {
        LANG_VI: "Restore {count} dòng vào {table}?",
        LANG_JP: "{table} に {count} 行を復元しますか？",
    },
    "backup.msg.restore_error": {
        LANG_VI: "Lỗi restore: {error}",
        LANG_JP: "復元エラー: {error}",
    },
    "backup.msg.restore_success": {
        LANG_VI: "Restore CSV thành công.",
        LANG_JP: "CSV復元に成功しました。",
    },

    # --- RDS info ---
    "rds.title": {LANG_VI: "Danh sách RDS", LANG_JP: "RDS一覧"},
    "rds.section.subsystems": {LANG_VI: "Chọn subsystem", LANG_JP: "サブシステム"},
    "rds.section.hosts": {LANG_VI: "Máy chủ", LANG_JP: "ホスト"},
    "rds.btn.add": {LANG_VI: "Thêm", LANG_JP: "追加"},
    "rds.btn.remove": {LANG_VI: "Xóa", LANG_JP: "削除"},
    "rds.btn.edit": {LANG_VI: "Chỉnh sửa", LANG_JP: "編集"},
    "rds.btn.view": {LANG_VI: "Xem", LANG_JP: "表示"},
    "rds.btn.close": {LANG_VI: "Đóng", LANG_JP: "閉じる"},
    "rds.field.display_name": {LANG_VI: "Tên hiển thị", LANG_JP: "表示名"},
    "rds.field.host": {LANG_VI: "Host/IP", LANG_JP: "ホスト/IP"},
    "rds.field.username": {LANG_VI: "Tên đăng nhập", LANG_JP: "ユーザー名"},
    "rds.field.password": {LANG_VI: "Mật khẩu", LANG_JP: "パスワード"},
    "rds.field.subsystem": {LANG_VI: "Subsystem", LANG_JP: "サブシステム"},
    "rds.btn.copy_host": {LANG_VI: "Copy host", LANG_JP: "ホストをコピー"},
    "rds.btn.copy_user": {LANG_VI: "Copy user", LANG_JP: "ユーザーをコピー"},
    "rds.btn.copy_pass": {LANG_VI: "Copy password", LANG_JP: "パスワードをコピー"},
    "rds.msg.select_item": {
        LANG_VI: "Vui lòng chọn subsystem và host.",
        LANG_JP: "サブシステムとホストを選択してください。",
    },
    "rds.msg.delete_confirm": {
        LANG_VI: "Xóa mục {name}?",
        LANG_JP: "{name} を削除しますか？",
    },
    "rds.msg.missing_fields": {
        LANG_VI: "Host và Username là bắt buộc.",
        LANG_JP: "ホストとユーザー名は必須です。",
    },
    "rds.msg.saved": {
        LANG_VI: "Đã lưu cấu hình RDS.",
        LANG_JP: "RDS情報を保存しました。",
    },

    # --- Log viewer ---
    "log.msg.copied": {LANG_VI: "Đã copy", LANG_JP: "コピーしました"},
    "log.msg.sql_copied": {LANG_VI: "SQL đã được copy vào clipboard", LANG_JP: "SQLをコピーしました"},
    "log.msg.details_copied": {LANG_VI: "Chi tiết đã được copy vào clipboard", LANG_JP: "詳細をコピーしました"},
}


def get_language() -> str:
    """Trả về mã ngôn ngữ hiện tại."""
    return _current_language


def set_language(lang: str) -> None:
    """Đặt ngôn ngữ hiện tại và thông báo cho các listener."""
    global _current_language
    if lang not in (LANG_VI, LANG_JP):
        lang = LANG_VI
    if lang == _current_language:
        return
    _current_language = lang
    for callback in list(_listeners):
        try:
            callback(lang)
        except Exception:
            pass


def translate(
    key: str,
    *,
    lang: str | None = None,
    default: str | None = None,
    **fmt,
) -> str:
    """Tra cứu chuỗi theo khóa, hỗ trợ định dạng."""
    target_lang = lang or _current_language
    entry = TRANSLATIONS.get(key)
    if entry is None:
        base = default if default is not None else key
        return base.format(**fmt) if fmt else base
    text = entry.get(target_lang) or entry.get(LANG_VI) or default or key
    try:
        return text.format(**fmt) if fmt else text
    except Exception:
        return text


def add_listener(callback: Callable[[str], None]) -> None:
    """Đăng ký callback lắng nghe khi thay đổi ngôn ngữ."""
    if callback not in _listeners:
        _listeners.append(callback)


def remove_listener(callback: Callable[[str], None]) -> None:
    """Hủy đăng ký callback lắng nghe khi thay đổi ngôn ngữ."""
    try:
        _listeners.remove(callback)
    except ValueError:
        pass
