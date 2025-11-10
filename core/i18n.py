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
    "common.app_title": {LANG_VI: "Tool VIP", LANG_JP: "Tool VIP"},
    "common.yes": {LANG_VI: "Có", LANG_JP: "はい"},
    "common.no": {LANG_VI: "Không", LANG_JP: "いいえ"},
    "common.warning": {LANG_VI: "Cảnh báo", LANG_JP: "警告"},
    "common.error": {LANG_VI: "Lỗi", LANG_JP: "エラー"},
    "common.info": {LANG_VI: "Thông báo", LANG_JP: "通知"},
    "common.reset": {LANG_VI: "Đặt lại", LANG_JP: "リセット"},
    "common.unknown_error": {LANG_VI: "Không rõ lỗi.", LANG_JP: "不明なエラーです。"},
    "common.loading_tables": {LANG_VI: "Đang tải danh sách bảng...", LANG_JP: "テーブル一覧を読み込み中..."},
    "common.loading_columns": {
        LANG_VI: "Đang tải cột của {table}...",
        LANG_JP: "{table} の列を読み込み中...",
    },
    "common.msg.connection_error": {
        LANG_VI: "Lỗi kết nối: {error}",
        LANG_JP: "接続エラー: {error}",
    },

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
    "main.btn.show_logs": {LANG_VI: "Xem log", LANG_JP: "ログ表示"},
    "main.btn.delete_log": {LANG_VI: "Xóa log", LANG_JP: "ログ削除"},
    "main.btn.read_log_mu": {LANG_VI: "Đọc log MU", LANG_JP: "MUログ読込"},
    "main.btn.run_ttl": {LANG_VI: "Chạy TTL", LANG_JP: "TTL実行"},
    "main.btn.rds_info": {LANG_VI: "Thông tin RDS", LANG_JP: "RDS情報"},
    "main.btn.docs": {LANG_VI: "Tài liệu", LANG_JP: "ドキュメント"},
    "main.btn.tips": {LANG_VI: "Bí kíp võ công", LANG_JP: "Tips"},
    "main.btn.history": {LANG_VI: "Lịch sử thao tác", LANG_JP: "Action History"},
    "compare.title": {LANG_VI: "So sánh dữ liệu", LANG_JP: "データ比較"},
    "compare.label.columns": {LANG_VI: "Số cột", LANG_JP: "列数"},
    "compare.btn.apply_columns": {LANG_VI: "Áp dụng", LANG_JP: "適用"},
    "compare.btn.add_rows": {LANG_VI: "Thêm 5 dòng", LANG_JP: "5行追加"},
    "compare.btn.clear": {LANG_VI: "Xóa dữ liệu", LANG_JP: "クリア"},
    "compare.btn.run": {LANG_VI: "So sánh", LANG_JP: "比較"},
    "compare.grid.left": {LANG_VI: "Bản chụp A", LANG_JP: "スナップ A"},
    "compare.grid.right": {LANG_VI: "Bản chụp B", LANG_JP: "スナップ B"},
    "compare.summary.placeholder": {LANG_VI: "Chưa có kết quả so sánh", LANG_JP: "比較結果はありません"},
    "compare.summary.same": {LANG_VI: "Hai bảng giống nhau.", LANG_JP: "両方とも同じです。"},
    "compare.summary.diff": {LANG_VI: "Có {count} ô khác nhau.", LANG_JP: "{count} 個のセルが異なります。"},
    "compare.msg.clear_confirm": {
        LANG_VI: "Xóa toàn bộ dữ liệu ở cả hai bảng?",
        LANG_JP: "両方の表のデータをすべてクリアしますか？",
    },
    "main.btn.details": {LANG_VI: "Chi tiết", LANG_JP: "詳細"},

    "main.status.not_connected": {LANG_VI: "Chưa kết nối", LANG_JP: "未接続"},
    "main.status.created_db_list": {
        LANG_VI: "Đã tạo configs/db_list.json mẫu",
        LANG_JP: "configs/db_list.json のテンプレートを作成しました",
    },
    "main.ttl.menu.add": {LANG_VI: "Thêm file TTL...", LANG_JP: "TTLファイル追加..."},
    "main.ttl.menu.manage": {LANG_VI: "Quản lý TTL...", LANG_JP: "TTL管理..."},
    "main.ttl.menu.empty": {LANG_VI: "Chưa có file TTL nào", LANG_JP: "TTLファイルがありません"},
    "main.ttl.menu.missing_suffix": {LANG_VI: " (mất)", LANG_JP: " (見つかりません)"},
    "main.ttl.dialog.title": {LANG_VI: "Trình chạy TTL", LANG_JP: "TTLランチャー"},
    "main.ttl.column.name": {LANG_VI: "Tên", LANG_JP: "名前"},
    "main.ttl.column.path": {LANG_VI: "Đường dẫn", LANG_JP: "パス"},
    "main.ttl.column.status": {LANG_VI: "Trạng thái", LANG_JP: "状態"},
    "main.ttl.column.last": {LANG_VI: "Lần chạy", LANG_JP: "最終実行"},
    "main.ttl.status.ready": {LANG_VI: "Sẵn sàng", LANG_JP: "利用可"},
    "main.ttl.status.missing": {LANG_VI: "Không tìm thấy", LANG_JP: "見つかりません"},
    "main.ttl.btn.run": {LANG_VI: "Chạy", LANG_JP: "実行"},
    "main.ttl.btn.add": {LANG_VI: "Thêm mới", LANG_JP: "追加"},
    "main.ttl.btn.remove": {LANG_VI: "Xóa", LANG_JP: "削除"},
    "main.ttl.btn.close": {LANG_VI: "Đóng", LANG_JP: "閉じる"},
    "main.ttl.msg.no_selection": {
        LANG_VI: "Hãy chọn một file TTL trước.",
        LANG_JP: "TTLファイルを選択してください。",
    },
    "main.ttl.msg.not_found": {
        LANG_VI: "Không tìm thấy file TTL:\n{path}",
        LANG_JP: "TTLファイルが見つかりません:\n{path}",
    },
    "main.ttl.msg.open_error": {
        LANG_VI: "Không chạy được TTL: {error}",
        LANG_JP: "TTLを実行できません: {error}",
    },
    "main.ttl.msg.add_none": {
        LANG_VI: "Chưa chọn file TTL nào.",
        LANG_JP: "TTLファイルが選択されていません。",
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
    "main.msg.load_tns_error": {
        LANG_VI: "Không tải được tnsnames.ora: {error}",
        LANG_JP: "tnsnames.ora を読み込めません: {error}",
    },
    "main.msg.sqlplus_error": {
        LANG_VI: "Không chạy được SQL*Plus: {error}",
        LANG_JP: "SQL*Plus を起動できません: {error}",
    },
    "main.msg.log_viewer_error": {
        LANG_VI: "Không mở được log viewer: {error}",
        LANG_JP: "ログビューアを開けません: {error}",
    },
    "main.msg.generic_error": {
        LANG_VI: "Đã xảy ra lỗi: {error}",
        LANG_JP: "エラーが発生しました: {error}",
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
    "insert.btn.save_template": {LANG_VI: "Lưu template", LANG_JP: "Save Template"},
    "insert.btn.select_template": {LANG_VI: "Chọn template", LANG_JP: "Choose Template"},
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
    "update.label.table_name": {LANG_VI: "Tên bảng", LANG_JP: "テーブル名"},
    "update.label.host": {LANG_VI: "Host", LANG_JP: "ホスト"},
    "update.label.port": {LANG_VI: "Port", LANG_JP: "ポート"},
    "update.btn.import_csv": {LANG_VI: "Import CSV", LANG_JP: "CSV取り込み"},
    "update.btn.export_csv": {LANG_VI: "Export CSV", LANG_JP: "CSV書き出し"},
    "update.btn.add_row": {LANG_VI: "Thêm dòng trống", LANG_JP: "空行追加"},
    "update.btn.build_sql": {LANG_VI: "Tạo câu Update", LANG_JP: "Update文作成"},
    "update.btn.save_template": {LANG_VI: "Lưu template", LANG_JP: "Save Template"},
    "update.btn.select_template": {LANG_VI: "Chọn template", LANG_JP: "Choose Template"},
    "update.btn.reorder": {LANG_VI: "Thay đổi vị trí cột", LANG_JP: "列順序変更"},
    "update.btn.execute": {LANG_VI: "Thực thi", LANG_JP: "実行"},
    "update.btn.clear": {LANG_VI: "Xóa dữ liệu", LANG_JP: "クリア"},
    "update.section.sql": {LANG_VI: "Update {table}", LANG_JP: "Update {table}"},
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
    "update.msg.where_missing_no_pk": {
        LANG_VI: "Thiếu điều kiện WHERE. Bảng không có khóa chính nên cần nhập điều kiện.",
        LANG_JP: "WHERE条件が不足しています。主キーがないため条件を入力してください。",
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
    "backup.choice.title": {LANG_VI: "Chọn chế độ Backup/Restore", LANG_JP: "バックアップ/リストアモードの選択"},
    "backup.choice.message": {
        LANG_VI: "Vui lòng chọn chế độ bạn muốn sử dụng cho kết nối hiện tại.",
        LANG_JP: "現在の接続で実行するモードを選択してください。",
    },
    "backup.choice.backup": {LANG_VI: "Tạo backup", LANG_JP: "バックアップを作成"},
    "backup.choice.restore_backup": {
        LANG_VI: "Restore từ bảng backup",
        LANG_JP: "バックアップテーブルから復元",
    },
    "backup.choice.restore_csv": {LANG_VI: "Restore từ CSV", LANG_JP: "CSV から復元"},
    "backup.title": {LANG_VI: "Backup Table", LANG_JP: "バックアップ"},
    "backup.restore_backup.title": {
        LANG_VI: "Restore từ bảng backup",
        LANG_JP: "バックアップテーブルから復元",
    },
    "backup.restore_csv.title": {
        LANG_VI: "Restore từ CSV",
        LANG_JP: "CSVから復元",
    },
    "backup.section.search": {LANG_VI: "Tìm kiếm", LANG_JP: "検索"},
    "backup.section.sql": {LANG_VI: "SQL", LANG_JP: "SQL"},
    "backup.section.log": {LANG_VI: "Log", LANG_JP: "ログ"},
    "backup.section.preview": {LANG_VI: "Xem thử dữ liệu", LANG_JP: "データプレビュー"},
    "backup.label.table": {LANG_VI: "Tên bảng", LANG_JP: "テーブル名"},
    "backup.label.source_table": {LANG_VI: "Bảng nguồn", LANG_JP: "元テーブル"},
    "backup.label.target_table": {LANG_VI: "Bảng đích", LANG_JP: "対象テーブル"},
    "backup.label.backup_table": {LANG_VI: "Bảng backup", LANG_JP: "バックアップテーブル"},
    "backup.label.backup_source_table": {
        LANG_VI: "Bảng backup nguồn",
        LANG_JP: "バックアップ元テーブル",
    },
    "backup.label.no_file": {LANG_VI: "Chưa chọn file", LANG_JP: "ファイル未選択"},
    "backup.btn.refresh_sql": {LANG_VI: "Cập nhật SQL", LANG_JP: "SQL更新"},
    "backup.btn.execute": {LANG_VI: "Thực thi", LANG_JP: "実行"},
    "backup.btn.import_csv": {LANG_VI: "Import CSV", LANG_JP: "CSV取り込み"},
    "backup.btn.clear_preview": {LANG_VI: "Xóa dữ liệu", LANG_JP: "データをクリア"},
    "backup.btn.execute_restore": {LANG_VI: "Thực thi", LANG_JP: "実行"},
    "backup.dialog.select_csv": {LANG_VI: "Chọn file CSV", LANG_JP: "CSVファイルを選択"},
    "backup.dialog.csv_files": {LANG_VI: "File CSV", LANG_JP: "CSVファイル"},
    "backup.dialog.all_files": {LANG_VI: "Tất cả các file", LANG_JP: "すべてのファイル"},
    "backup.msg.not_connected": {
        LANG_VI: "Chưa kết nối database.",
        LANG_JP: "データベースに接続していません。",
    },
    "backup.msg.no_statement": {
        LANG_VI: "Không có câu lệnh để thực thi.",
        LANG_JP: "実行するSQLがありません。",
    },
    "backup.msg.no_csv_data": {
        LANG_VI: "Chưa có dữ liệu để restore.",
        LANG_JP: "復元するCSVデータがありません。",
    },
    "backup.msg.no_target_table": {
        LANG_VI: "Chưa chọn bảng đích.",
        LANG_JP: "対象テーブルが選択されていません。",
    },
    "backup.msg.cursor_error": {
        LANG_VI: "Lỗi tạo cursor: {error}",
        LANG_JP: "カーソル作成エラー: {error}",
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
    "backup.msg.missing_header": {
        LANG_VI: "Không tìm thấy header trong file.",
        LANG_JP: "ファイルにヘッダーが見つかりません。",
    },
    "backup.msg.missing_columns": {
        LANG_VI: "Thiếu cột: {columns}",
        LANG_JP: "不足列: {columns}",
    },
    "backup.msg.extra_columns": {
        LANG_VI: "Dư cột: {columns}",
        LANG_JP: "余分な列: {columns}",
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
    "backup.log.complete": {LANG_VI: "Hoàn thành.", LANG_JP: "完了しました。"},
    "backup.log.skip_drop": {
        LANG_VI: "(Bảng không tồn tại, bỏ qua DROP)",
        LANG_JP: "（テーブルが存在しないため DROP をスキップ）",
    },
    "backup.log.import_summary": {
        LANG_VI: "Đã import {count} dòng từ {path}",
        LANG_JP: "CSV {path} から {count} 行を取り込みました。",
    },
    "backup.log.restore_done": {
        LANG_VI: "Restore CSV hoàn thành.",
        LANG_JP: "CSV復元が完了しました。",
    },

    # --- Widgets & DataGrid ---
    "widget.loading.title": {LANG_VI: "Đang xử lý", LANG_JP: "処理中"},
    "widget.loading.message": {LANG_VI: "Vui lòng chờ trong giây lát...", LANG_JP: "しばらくお待ちください…"},
    "grid.dialog.open_csv": {LANG_VI: "Chọn tệp CSV", LANG_JP: "CSVファイルを選択"},
    "grid.dialog.save_csv": {LANG_VI: "Lưu tệp CSV", LANG_JP: "CSVファイルを保存"},
    "grid.msg.read_csv_error": {
        LANG_VI: "Không đọc được CSV: {error}",
        LANG_JP: "CSVを読み込めません: {error}",
    },
    "grid.msg.write_csv_error": {
        LANG_VI: "Không ghi được CSV: {error}",
        LANG_JP: "CSVを書き出せません: {error}",
    },
    "grid.menu.copy_rows": {LANG_VI: "Sao chép dòng", LANG_JP: "行をコピー"},
    "grid.menu.copy_rows_header": {LANG_VI: "Sao chép dòng + tiêu đề", LANG_JP: "行とヘッダーをコピー"},
    "grid.menu.copy_all": {LANG_VI: "Sao chép tất cả", LANG_JP: "すべてコピー"},
    "grid.menu.paste": {LANG_VI: "Dán", LANG_JP: "貼り付け"},
    "grid.menu.delete_rows": {LANG_VI: "Xóa dòng", LANG_JP: "行を削除"},
    "grid.duplicate.title": {LANG_VI: "Cảnh báo dữ liệu trùng", LANG_JP: "重複データの警告"},
    "grid.duplicate.message": {
        LANG_VI: "Phát hiện dữ liệu trùng khóa chính. Bạn có muốn ghi đè dữ liệu hiện có?",
        LANG_JP: "主キーが重複しているデータがあります。既存データを上書きしますか？",
    },
    "grid.duplicate.table": {LANG_VI: "Bảng: {table}", LANG_JP: "テーブル: {table}"},
    "grid.duplicate.pk": {LANG_VI: "Khóa chính: {keys}", LANG_JP: "主キー: {keys}"},
    "grid.duplicate.user_data": {LANG_VI: "Dữ liệu của bạn", LANG_JP: "入力データ"},
    "grid.duplicate.database_data": {LANG_VI: "Dữ liệu trong database", LANG_JP: "データベース"},
    "grid.order.title": {LANG_VI: "Thay đổi vị trí cột", LANG_JP: "列順序を変更"},
    "grid.order.hint": {
        LANG_VI: "Kéo thả hoặc dùng Ctrl+↑/↓ để sắp xếp cột.",
        LANG_JP: "ドラッグ＆ドロップ、または Ctrl+↑/↓ で列順序を変更できます。",
    },
    "grid.order.move_up": {LANG_VI: "Di chuyển lên", LANG_JP: "上へ移動"},
    "grid.order.move_down": {LANG_VI: "Di chuyển xuống", LANG_JP: "下へ移動"},


    # --- Template Library ---
    "template.save.title": {LANG_VI: "Lưu template", LANG_JP: "Save Template"},
    "template.save.name": {LANG_VI: "Tên template", LANG_JP: "Template Name"},
    "template.save.description": {LANG_VI: "Mô tả", LANG_JP: "Description"},
    "template.save.type": {LANG_VI: "Loại", LANG_JP: "Type"},
    "template.save.message_missing": {LANG_VI: "Vui lòng nhập tên template.", LANG_JP: "Please enter template name."},
    "template.save.message_no_sql": {LANG_VI: "Không có SQL để lưu.", LANG_JP: "No SQL to save."},
    "template.save.message_saved": {LANG_VI: "Đã lưu template.", LANG_JP: "Template saved."},
    "template.dialog.title": {LANG_VI: "Thư viện template", LANG_JP: "Template Library"},
    "template.dialog.column.name": {LANG_VI: "Tên", LANG_JP: "Name"},
    "template.dialog.column.type": {LANG_VI: "Loại", LANG_JP: "Type"},
    "template.dialog.column.description": {LANG_VI: "Mô tả", LANG_JP: "Description"},
    "template.dialog.column.created": {LANG_VI: "Tạo lúc", LANG_JP: "Created"},
    "template.dialog.preview": {LANG_VI: "Nội dung", LANG_JP: "Content"},
    "template.dialog.btn.apply": {LANG_VI: "Sử dụng", LANG_JP: "Apply"},
    "template.dialog.btn.copy": {LANG_VI: "Copy", LANG_JP: "Copy"},
    "template.dialog.btn.delete": {LANG_VI: "Xóa", LANG_JP: "Delete"},
    "template.dialog.btn.close": {LANG_VI: "Đóng", LANG_JP: "Close"},
    "template.dialog.confirm_delete": {LANG_VI: "Xóa template này?", LANG_JP: "Delete this template?"},
    "template.dialog.no_selection": {LANG_VI: "Chưa chọn template.", LANG_JP: "No template selected."},
    "template.dialog.empty": {LANG_VI: "Thư viện đang rỗng.", LANG_JP: "Library is empty."},


    # --- History ---
    "history.title": {LANG_VI: "Lịch sử thao tác", LANG_JP: "Action History"},
    "history.column.time": {LANG_VI: "Thời gian", LANG_JP: "Time"},
    "history.column.type": {LANG_VI: "Loại", LANG_JP: "Type"},
    "history.column.object": {LANG_VI: "Đối tượng", LANG_JP: "Object"},
    "history.column.rows": {LANG_VI: "Số dòng", LANG_JP: "Rows"},
    "history.column.status": {LANG_VI: "Trạng thái", LANG_JP: "Status"},
    "history.column.message": {LANG_VI: "Thông điệp", LANG_JP: "Message"},
    "history.column.sql": {LANG_VI: "SQL", LANG_JP: "SQL"},
    "history.filter.type": {LANG_VI: "Lọc theo loại", LANG_JP: "Filter by type"},
    "history.filter.all": {LANG_VI: "Tất cả", LANG_JP: "All"},
    "history.search.placeholder": {LANG_VI: "Nhập từ khóa", LANG_JP: "Enter keyword"},
    "history.btn.refresh": {LANG_VI: "Tải lại", LANG_JP: "Refresh"},
    "history.btn.detail": {LANG_VI: "Xem chi tiết", LANG_JP: "View Detail"},
    "history.btn.export_csv": {LANG_VI: "Xuất CSV", LANG_JP: "Export CSV"},
    "history.detail.title": {LANG_VI: "Chi tiết hành động", LANG_JP: "Action Detail"},
    "history.detail.message": {LANG_VI: "Thông điệp", LANG_JP: "Message"},
    "history.detail.sql": {LANG_VI: "SQL đầy đủ", LANG_JP: "Full SQL"},
    "history.detail.copy": {LANG_VI: "Copy", LANG_JP: "Copy"},
    "history.detail.use_insert": {LANG_VI: "Dùng cho Insert", LANG_JP: "Use for Insert"},
    "history.detail.use_update": {LANG_VI: "Dùng cho Update", LANG_JP: "Use for Update"},
    "history.msg.no_selection": {LANG_VI: "Chưa chọn bản ghi.", LANG_JP: "No row selected."},
    "history.msg.export_success": {LANG_VI: "Đã xuất CSV.", LANG_JP: "CSV exported."},
    "history.msg.export_error": {LANG_VI: "Không thể xuất CSV.", LANG_JP: "Failed to export CSV."},
    "history.msg.clipboard": {LANG_VI: "Đã copy vào clipboard.", LANG_JP: "Copied to clipboard."},
    "history.msg.no_window": {LANG_VI: "Không tìm thấy cửa sổ phù hợp.", LANG_JP: "No target window."},
    "history.msg.open_error": {LANG_VI: "Không mở được màn hình lịch sử: {error}", LANG_JP: "Cannot open history: {error}"},

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
    "rds.btn.open_detail": {LANG_VI: "Chi tiết", LANG_JP: "詳細"},
    "rds.detail.title": {LANG_VI: "Chi tiết RDS", LANG_JP: "RDS詳細"},
    "rds.msg.copy_success": {
        LANG_VI: "Đã copy {field} vào clipboard.",
        LANG_JP: "{field} をクリップボードにコピーしました。",
    },
    "rds.msg.no_host": {
        LANG_VI: "Chưa chọn host.",
        LANG_JP: "ホストが選択されていません。",
    },
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
    "rds.msg.save_error": {
        LANG_VI: "Không lưu được cấu hình RDS: {error}",
        LANG_JP: "RDS情報を保存できません: {error}",
    },
    "rds.msg.open_error": {
        LANG_VI: "Không mở được màn hình RDS: {error}",
        LANG_JP: "RDS画面を開けません: {error}",
    },

    # --- Log viewer ---
    "log.title": {LANG_VI: "Trình xem log MU", LANG_JP: "MUログビューア"},
    "log.section.filters": {LANG_VI: "Bộ lọc", LANG_JP: "フィルタ"},
    "log.section.results": {LANG_VI: "Kết quả", LANG_JP: "結果"},
    "log.label.file": {LANG_VI: "Tệp log", LANG_JP: "ログファイル"},
    "log.label.choose": {LANG_VI: "Chọn log", LANG_JP: "ログ選択"},
    "log.label.type": {LANG_VI: "Loại log", LANG_JP: "ログ種別"},
    "log.label.screen": {LANG_VI: "Màn hình", LANG_JP: "画面"},
    "log.label.command_type": {LANG_VI: "Loại lệnh", LANG_JP: "コマンド種別"},
    "log.label.command": {LANG_VI: "Loại lệnh", LANG_JP: "コマンド種別"},
    "log.label.important_only": {LANG_VI: "Chỉ hiển thị cột quan trọng", LANG_JP: "重要列のみ表示"},
    "log.label.keyword": {LANG_VI: "Từ khóa", LANG_JP: "キーワード"},
    "log.label.time_display": {LANG_VI: "Hiển thị thời gian", LANG_JP: "時間の表示"},
    "log.label.param_display": {LANG_VI: "Tham số", LANG_JP: "パラメータ"},
    "log.label.important_only": {LANG_VI: "Chỉ hiển thị cột quan trọng", LANG_JP: "重要列のみ表示"},
    "log.option.sql": {LANG_VI: "SQL", LANG_JP: "SQL"},
    "log.option.error": {LANG_VI: "Lỗi", LANG_JP: "エラー"},
    "log.option.param_show": {LANG_VI: "Hiện tham số", LANG_JP: "パラメータ表示"},
    "log.option.param_hide": {LANG_VI: "Ẩn tham số", LANG_JP: "パラメータ非表示"},
    "log.option.time_full": {LANG_VI: "yyyy-mm-dd hh:mm:ss", LANG_JP: "yyyy-mm-dd hh:mm:ss"},
    "log.option.time_time": {LANG_VI: "hh:mm:ss", LANG_JP: "hh:mm:ss"},
    "log.btn.choose": {LANG_VI: "Chọn...", LANG_JP: "選択..."},
    "log.btn.choose_new": {LANG_VI: "Chọn log mới", LANG_JP: "新しいログを選択"},
    "log.btn.choose_recent": {LANG_VI: "Log đã xem", LANG_JP: "最近のログ"},
    "log.btn.search": {LANG_VI: "Tìm kiếm", LANG_JP: "検索"},
    "log.btn.copy": {LANG_VI: "Copy", LANG_JP: "コピー"},
    "log.btn.clear": {LANG_VI: "Xóa", LANG_JP: "クリア"},
    "log.btn.refresh": {LANG_VI: "Tải lại", LANG_JP: "再読込"},
    "log.btn.reset": {LANG_VI: "Đặt lại lọc", LANG_JP: "フィルタをリセット"},
    "log.btn.open_folder": {LANG_VI: "Mở thư mục", LANG_JP: "フォルダを開く"},
    "log.btn.save_log": {LANG_VI: "Lưu log", LANG_JP: "ログ保存"},
    "log.btn.view_saved": {LANG_VI: "Log đã lưu", LANG_JP: "保存済みログ"},
    "log.btn.delete_log": {LANG_VI: "Xóa log", LANG_JP: "ログ削除"},
    "log.btn.close": {LANG_VI: "Đóng", LANG_JP: "閉じる"},
    "log.btn.toggle_param_sql": {LANG_VI: "Đổi Param/SQL", LANG_JP: "パラメータ/SQL切替"},
    "log.dialog.choose_source": {LANG_VI: "Chọn nguồn log", LANG_JP: "ログ選択"},
    "log.dialog.recent_title": {LANG_VI: "Log đã mở gần đây", LANG_JP: "最近開いたログ"},
    "log.column.filename": {LANG_VI: "Tên log", LANG_JP: "ログ名"},
    "log.column.path": {LANG_VI: "Đường dẫn", LANG_JP: "パス"},
    "log.column.opened_at": {LANG_VI: "Ngày mở", LANG_JP: "開いた日時"},
    "log.column.size": {LANG_VI: "Dung lượng", LANG_JP: "サイズ"},
    "log.column.screen_id": {LANG_VI: "Mã màn hình", LANG_JP: "画面ID"},
    "log.column.time": {LANG_VI: "Thời gian", LANG_JP: "日時"},
    "log.column.command": {LANG_VI: "Lệnh", LANG_JP: "コマンド"},
    "log.column.function": {LANG_VI: "Hàm", LANG_JP: "関数"},
    "log.column.params": {LANG_VI: "Tham số", LANG_JP: "パラメータ"},
    "log.column.sql": {LANG_VI: "SQL", LANG_JP: "SQL"},
    "log.column.summary": {LANG_VI: "Tóm tắt", LANG_JP: "概要"},
    "log.column.details": {LANG_VI: "Chi tiết", LANG_JP: "詳細"},
    "log.column.field": {LANG_VI: "Trường", LANG_JP: "フィールド"},
    "log.column.value": {LANG_VI: "Giá trị", LANG_JP: "値"},
    "log.msg.no_file": {LANG_VI: "Chưa chọn file log.", LANG_JP: "ログファイルが選択されていません。"},
    "log.msg.read_error": {LANG_VI: "Không đọc được log: {error}", LANG_JP: "ログを読み込めません: {error}"},
    "log.msg.parse_error": {LANG_VI: "Không phân tích được log.", LANG_JP: "ログを解析できません。"},
    "log.msg.no_results": {LANG_VI: "Không có dữ liệu hiển thị.", LANG_JP: "表示するデータがありません。"},
    "log.msg.save_success": {LANG_VI: "Đã lưu {count} log.", LANG_JP: "{count}件のログを保存しました。"},
    "log.msg.save_none": {LANG_VI: "Chưa chọn log nào để lưu.", LANG_JP: "保存するログが選択されていません。"},
    "log.msg.no_saved_log": {LANG_VI: "Chưa có log nào được lưu.", LANG_JP: "保存済みのログはありません。"},
    "log.msg.no_recent_log": {LANG_VI: "Chưa có log nào được mở trước đó.", LANG_JP: "最近開いたログがありません。"},
    "log.msg.choose_prompt": {LANG_VI: "Nhấn Chọn... để mở log.", LANG_JP: "「選択...」ボタンを押してログを開いてください。"},
    "log.msg.delete_confirm": {LANG_VI: "Xóa {count} log đã chọn?", LANG_JP: "選択した{count}件のログを削除しますか?"},
    "log.msg.delete_done": {LANG_VI: "Đã xóa {count} log.", LANG_JP: "{count}件のログを削除しました。"},
    "log.msg.delete_none": {LANG_VI: "Chưa chọn log để xóa.", LANG_JP: "削除するログが選択されていません。"},
    "log.msg.delete_error": {LANG_VI: "Không thể xóa log: {error}", LANG_JP: "ログを削除できません: {error}"},
    "log.msg.copied": {LANG_VI: "Đã copy", LANG_JP: "コピーしました"},
    "log.msg.sql_copied": {LANG_VI: "SQL đã được copy vào clipboard", LANG_JP: "SQLをコピーしました"},
    "log.msg.details_copied": {LANG_VI: "Chi tiết đã được copy vào clipboard", LANG_JP: "詳細をコピーしました"},
    "log.msg.open_folder_error": {
        LANG_VI: "Không mở được thư mục log: {error}",
        LANG_JP: "ログフォルダを開けません: {error}",
    },
    "log.status.summary": {
        LANG_VI: "{visible} dòng (tổng {total})",
        LANG_JP: "{visible}件 / 全{total}件",
    },
    "log.dialog.saved_title": {LANG_VI: "Log đã lưu", LANG_JP: "保存済みログ"},
    "log.column.saved_at": {LANG_VI: "Lưu lúc", LANG_JP: "保存時刻"},
    "log.detail.sql_title": {LANG_VI: "Chi tiết SQL", LANG_JP: "SQL詳細"},
    "log.detail.error_title": {LANG_VI: "Chi tiết lỗi", LANG_JP: "エラー詳細"},
    "log.detail.params_title": {LANG_VI: "Tham số", LANG_JP: "パラメータ"},

    # --- Main logs ---
    "main.log.title": {LANG_VI: "Danh sách log", LANG_JP: "ログ一覧"},
    "main.log.no_files": {LANG_VI: "Chưa có file log.", LANG_JP: "ログファイルがありません。"},
    "main.log.open_error": {LANG_VI: "Không mở được log: {error}", LANG_JP: "ログを開けません: {error}"},
    "main.log.delete_confirm": {LANG_VI: "Xóa file log {name}?", LANG_JP: "ログ {name} を削除しますか?"},
    "main.log.delete_done": {LANG_VI: "Đã xóa file log.", LANG_JP: "ログを削除しました。"},
    "main.log.delete_error": {LANG_VI: "Không thể xóa log: {error}", LANG_JP: "ログを削除できません: {error}"},
    "main.log.delete_none": {LANG_VI: "Chưa chọn file log.", LANG_JP: "ログファイルが選択されていません。"},
    "main.log.content_title": {LANG_VI: "Nội dung {name}", LANG_JP: "{name} の内容"},
    "main.log.copied": {LANG_VI: "Đã copy vào clipboard", LANG_JP: "クリップボードにコピーしました"},
    "main.log.copy": {LANG_VI: "Copy", LANG_JP: "コピー"},
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
