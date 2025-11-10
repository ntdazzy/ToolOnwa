"""
Màn hình Backup/Restore dùng sao lưu và phục hồi dữ liệu.
"""
from __future__ import annotations

import csv
import datetime as dt
import logging
import re
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText
from typing import Any, Dict, List, Optional

from screen.DB import db_utils
from screen.DB.widgets import DataGrid, LoadingPopup
from core import history, i18n

APP_TITLE_KEY = "common.app_title"

logger = logging.getLogger("ToolVIP.Backup")


class BackupRestoreBase(tk.Toplevel):
    """
    Base class that provides table search/loading and connection management.
    """

    GEOMETRY = "520x640"

    def __init__(self, parent: tk.Widget, connection: Dict[str, str], title_key: str):
        """Khởi tạo cửa sổ nền tảng cho các màn hình backup/restore."""
        super().__init__(parent)
        self.parent = parent
        self.conn_info = connection
        self.conn = None
        self.current_owner = connection.get("user", "").upper()
        self._title_key = title_key
        self.title(self._t(self._title_key))
        self.geometry(self.GEOMETRY)
        self.minsize(480, 560)
        self.resizable(True, True)
        self._logger = logger
        self._set_icon()

        self._history_action_type = "sql_script"
        self._table_items: List[Dict[str, str]] = []
        self._table_view: List[Dict[str, str]] = []
        self._active_table: Optional[Dict[str, str]] = None
        self._columns: List[str] = []
        self._column_meta: Dict[str, dict] = {}
        self._loader: Optional[LoadingPopup] = None
        self._current_table_label: str = "..."
        self._metadata_cache: Dict[str, Dict[str, Any]] = {}
        self._metadata_token: int = 0
        self._metadata_loading: bool = False

        self.var_search = tk.StringVar()
        self.var_selected_table = tk.StringVar()

        self._build_ui()
        self._lang_listener = self._handle_language_change
        i18n.add_listener(self._lang_listener)
        self._apply_language()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(120, self._connect_async)

    def _log_exception(self, message: str, exc: Exception) -> None:
        self._logger.exception("%s", message, exc_info=exc)

    # ------------------------------------------------------------------
    def _build_ui(self):
        """Xây dựng bố cục chung gồm khung tìm kiếm và phần thân."""
        self.frm_main = ttk.Frame(self, padding=8)
        self.frm_main.pack(fill="both", expand=True)
        self.frm_main.rowconfigure(1, weight=1)
        self.frm_main.columnconfigure(0, weight=1)

        self.grp_search = ttk.LabelFrame(self.frm_main, text=self._t("backup.section.search"), padding=6)
        self.grp_search.grid(row=0, column=0, sticky="nsew", pady=(0, 6))
        self.grp_search.columnconfigure(0, weight=1)

        self.lbl_table = ttk.Label(self.grp_search, text=self._t("backup.label.table"))
        self.lbl_table.grid(row=0, column=0, sticky="w")
        self.ent_search = ttk.Entry(self.grp_search, textvariable=self.var_search)
        self.ent_search.grid(row=1, column=0, sticky="ew", pady=4)
        self.ent_search.bind("<KeyRelease>", lambda _event: self._filter_tables())

        self.list_tables = tk.Listbox(self.grp_search, height=5)
        self.list_tables.grid(row=2, column=0, sticky="nsew")
        self.list_tables.bind("<<ListboxSelect>>", self._handle_table_select)
        self.grp_search.rowconfigure(2, weight=1)

        self.body = ttk.Frame(self.frm_main)
        self.body.grid(row=1, column=0, sticky="nsew")
        self.body.columnconfigure(0, weight=1)
        self.body.rowconfigure(0, weight=1)

        self._build_body(self.body)

    def _build_body(self, parent: ttk.Frame):
        raise NotImplementedError

    def _history_object_name(self) -> str:
        """Lay ten doi tuong dung cho ghi log."""
        try:
            value = self.var_selected_table.get().strip()  # type: ignore[attr-defined]
        except Exception:
            value = ""
        if not value:
            try:
                backup = self.var_backup_name.get().strip()  # type: ignore[attr-defined]
                value = backup or value
            except Exception:
                pass
        return value

    # ------------------------------------------------------------------
    def _connect_async(self):
        """Kết nối cơ sở dữ liệu và lấy danh sách bảng ở luồng nền."""
        def worker():
            try:
                self.conn = db_utils.connect_oracle(
                    self.conn_info.get("user", ""),
                    self.conn_info.get("password", ""),
                    self.conn_info.get("host", ""),
                    self.conn_info.get("port", ""),
                    self.conn_info.get("alias", ""),
                    bool(self.conn_info.get("use_host_port")),
                )
                tables = db_utils.fetch_accessible_tables(self.conn)
            except db_utils.OracleDriverNotAvailable as exc:
                msg = str(exc)
                self._log_exception("Oracle driver unavailable for backup window", exc)
                self.after(0, lambda m=msg: self._show_error(m))
                return
            except Exception as exc:
                msg = self._t("common.msg.connection_error", error=str(exc))
                self._log_exception("Failed to connect or fetch tables in backup window", exc)
                self.after(0, lambda m=msg: self._show_error(m))
                return
            self.after(0, lambda: self._init_tables(tables))

        self._show_loading(self._t("common.loading_tables"))
        threading.Thread(target=worker, daemon=True).start()

    def _show_error(self, msg: str):
        """Hiển thị lỗi và đóng cửa sổ khi không thể tiếp tục."""
        self._hide_loading()
        self._logger.error("Backup window error: %s", msg)
        messagebox.showerror(self._t(APP_TITLE_KEY), msg, parent=self)
        self.destroy()

    def _init_tables(self, tables: List[str]):
        """Nạp danh sách bảng truy cập được vào listbox."""
        self._hide_loading()
        items: List[Dict[str, str]] = []
        for raw in tables:
            owner, name = db_utils.split_owner_table(raw, self.current_owner)
            full = f"{owner}.{name}"
            items.append({"full": full, "display": name, "owner": owner, "table": name})
        items.sort(key=lambda it: (it["display"], it["owner"]))
        self._table_items = items
        self._table_view = list(items)
        self.list_tables.delete(0, tk.END)
        for item in self._table_view:
            self.list_tables.insert(tk.END, item["display"])
        if self._table_view:
            self.list_tables.selection_set(0)
            self._handle_table_select()
        else:
            self._active_table = None
            self.var_selected_table.set("")
            self._columns.clear()
            self._column_meta.clear()
            self._current_table_label = "..."
            self._set_metadata_loading(False)
            self.on_table_ready("")

    def _filter_tables(self):
        """Lọc danh sách bảng theo từ khóa tìm kiếm."""
        keyword = self.var_search.get().strip().upper()
        current_full = self._active_table["full"] if self._active_table else None
        if keyword:
            view = [item for item in self._table_items if keyword in item["display"].upper()]
        else:
            view = list(self._table_items)
        self._table_view = view
        self.list_tables.delete(0, tk.END)
        selected_index = None
        for idx, item in enumerate(view):
            self.list_tables.insert(tk.END, item["display"])
            if item["full"] == current_full:
                selected_index = idx
        if selected_index is not None:
            self.list_tables.selection_set(selected_index)
        elif view:
            self.list_tables.selection_set(0)
            self._handle_table_select()
        else:
            self._active_table = None
            self.var_selected_table.set("")
            self.list_tables.selection_clear(0, tk.END)
            self._columns.clear()
            self._column_meta.clear()
            self._current_table_label = "..."
            self._set_metadata_loading(False)
            self.on_table_ready("")

    def _handle_table_select(self, _event=None):
        """Xử lý việc chọn bảng từ danh sách."""
        selection = self.list_tables.curselection()
        if not selection:
            return
        index = selection[0]
        if index >= len(self._table_view):
            return
        item = self._table_view[index]
        if self._active_table and self._active_table["full"] == item["full"]:
            return
        self._active_table = item
        self.var_selected_table.set(item["display"])
        self._current_table_label = item["display"]
        self._load_table_metadata(item)

    def _load_table_metadata(self, item: Dict[str, str]):
        """Đọc metadata của bảng được chọn (kèm cache và loading popup)."""
        if not self.conn:
            return
        table_key = item["full"]
        self._columns.clear()
        self._column_meta.clear()
        self._set_metadata_loading(True)

        cached = self._metadata_cache.get(table_key)
        if cached:
            self._metadata_token += 1
            token = self._metadata_token
            self._hide_loading()
            self._apply_table_metadata(item, cached["columns"], token)
            return

        self._metadata_token += 1
        token = self._metadata_token
        self._hide_loading()
        self._show_loading(self._t("common.loading_columns", table=item["display"]))

        def worker():
            try:
                columns = db_utils.fetch_table_columns(self.conn, table_key, self.current_owner)
            except Exception as exc:
                self._log_exception(f"Failed to load column metadata for {table_key}", exc)
                self.after(0, lambda: self._handle_metadata_error(item, exc, token))
                return
            self._metadata_cache[table_key] = {"columns": columns}
            self.after(0, lambda: self._apply_table_metadata(item, columns, token))

        threading.Thread(target=worker, daemon=True).start()

    def _apply_table_metadata(
        self,
        item: Dict[str, str],
        columns: List[Dict[str, Any]],
        token: Optional[int] = None,
    ):
        """Áp dụng metadata sau khi tải thành công."""
        if token is not None and token != self._metadata_token:
            return
        if not self._active_table or self._active_table["full"] != item["full"]:
            return
        self._hide_loading()
        self._columns = [c["column_name"] for c in columns]
        self._column_meta = {c["column_name"]: c for c in columns}
        self._set_metadata_loading(False)
        self.on_table_ready(item["full"])

    def _handle_metadata_error(self, item: Dict[str, str], exc: Exception, token: Optional[int]):
        """Thông báo lỗi khi không thể tải metadata."""
        if token is not None and token != self._metadata_token:
            return
        if not self._active_table or self._active_table["full"] != item["full"]:
            return
        self._hide_loading()
        self._set_metadata_loading(False)
        self._log_exception(f"Metadata error for table {item.get('full')}", exc)
        messagebox.showerror(
            self._t(APP_TITLE_KEY),
            self._t("backup.msg.metadata_error", error=str(exc)),
            parent=self,
        )
        self.on_table_ready("")

    def _set_metadata_loading(self, loading: bool) -> None:
        """Bật/tắt khả năng tương tác khi đang tải metadata."""
        self._metadata_loading = loading
        state = "disabled" if loading else "normal"
        try:
            self.list_tables.configure(state=state)
        except tk.TclError:
            pass
        try:
            self.ent_search.configure(state=state)
        except tk.TclError:
            pass
        self.on_metadata_loading(loading)

    def on_metadata_loading(self, loading: bool) -> None:
        """Hook để lớp con tùy biến việc bật/tắt nút khi metadata đang tải."""
        # Mặc định không làm gì, lớp con có thể override.
        return

    def on_table_ready(self, table: str):
        """Hook cho lớp con khi metadata đã sẵn sàng."""
        raise NotImplementedError

    # ------------------------------------------------------------------
    def _split_table(self, raw: str) -> tuple[str, str]:
        """Tách owner và tên bảng, fallback về owner hiện tại khi thiếu."""
        if raw and "." in raw:
            return db_utils.split_owner_table(raw, self.current_owner)
        if self._active_table:
            return self._active_table["owner"], self._active_table["table"]
        return db_utils.split_owner_table(raw, self.current_owner)

    def _append_log(self, text: str):
        """Ghi log vào vùng hiển thị và cuộn xuống cuối."""
        widget = getattr(self, "txt_log", None)
        if widget is None:
            return
        widget.insert(tk.END, text.strip() + "\n")
        widget.see(tk.END)

    def _on_close(self):
        """Đóng cửa sổ và giải phóng kết nối nếu có."""
        self._hide_loading()
        try:
            if self.conn:
                self.conn.close()
        except Exception as exc:
            self._log_exception("Failed to close backup connection", exc)
        self.destroy()

    def _show_loading(self, message: str):
        """Hiển thị popup đang xử lý."""
        if self._loader:
            return
        self._loader = LoadingPopup(self, message)

    def _hide_loading(self):
        """Đóng popup đang xử lý nếu tồn tại."""
        if not self._loader:
            return
        self._loader.close()
        self._loader = None

    # ------------------------------------------------------------------
    def _run_statements(self, sql_text: str) -> bool:
        """Thuc thi lan luot cac cau SQL da chuan bi va ghi log."""
        object_name = self._history_object_name()
        sql_trim = (sql_text or "").strip()
        if not self.conn:
            history.log_action(self._history_action_type, object_name, 0, "failed", message=self._t("backup.msg.not_connected"), sql_text=sql_trim)
            messagebox.showerror(self._t(APP_TITLE_KEY), self._t("backup.msg.not_connected"), parent=self)
            return False
        statements = [stmt.strip() for stmt in re.split(r";\s*(?:\n|$)", sql_text) if stmt.strip()]
        if not statements:
            messagebox.showwarning(self._t(APP_TITLE_KEY), self._t("backup.msg.no_statement"), parent=self)
            return False
        row_count = len(statements)
        try:
            cur = self.conn.cursor()
        except Exception as exc:
            msg = self._t("backup.msg.cursor_error", error=str(exc))
            self._log_exception("Failed to create cursor for backup execution", exc)
            history.log_action(self._history_action_type, object_name, row_count, "failed", message=msg, sql_text=sql_trim)
            messagebox.showerror(self._t(APP_TITLE_KEY), msg, parent=self)
            return False

        action_id = history.log_action(self._history_action_type, object_name, row_count, "pending", message="SQL script", sql_text=sql_trim)

        def _finalize(status: str, message: str) -> None:
            try:
                if action_id:
                    history.mark_action_status(action_id, status, message, row_count=row_count, sql_text=sql_trim)
                else:
                    history.log_action(self._history_action_type, object_name, row_count, status, message=message, sql_text=sql_trim)
            except Exception as exc:
                self._log_exception("Failed to finalize backup history status", exc)

        try:
            for stmt in statements:
                self._append_log(f"> {stmt}")
                try:
                    cur.execute(stmt)
                except Exception as exc:
                    if self._should_ignore_drop(stmt, exc):
                        self._append_log("  " + self._t("backup.log.skip_drop"))
                        continue
                    self.conn.rollback()
                    self._append_log(f"  ERROR: {exc}")
                    msg = self._t("backup.msg.execute_error", error=str(exc))
                    self._log_exception("Failed executing backup statement", exc)
                    _finalize("failed", msg)
                    messagebox.showerror(self._t(APP_TITLE_KEY), msg, parent=self)
                    return False
            self.conn.commit()
            self._append_log(self._t("backup.log.complete"))
            _finalize("success", self._t("backup.log.complete"))
            messagebox.showinfo(self._t(APP_TITLE_KEY), self._t("backup.msg.execute_success"), parent=self)
            return True
        finally:
            try:
                cur.close()
            except Exception as exc:
                self._logger.debug("Backup cursor close failed: %s", exc)


    @staticmethod
    def _should_ignore_drop(statement: str, exc: Exception) -> bool:
        """Kiểm tra xem có thể bỏ qua lỗi DROP do bảng không tồn tại hay không."""
        text = statement.strip().upper()
        if not text.startswith("DROP"):
            return False
        err = str(exc).upper()
        return "ORA-00942" in err or "TABLE OR VIEW DOES NOT EXIST" in err

    def destroy(self):
        """Hủy cửa sổ và gỡ listener ngôn ngữ."""
        if hasattr(self, "_lang_listener"):
            i18n.remove_listener(self._lang_listener)
        super().destroy()

    def _handle_language_change(self, _lang: str) -> None:
        """Callback khi thay đổi ngôn ngữ."""
        self._apply_language()

    def _apply_language(self) -> None:
        """Áp dụng chuỗi dịch cho các thành phần giao diện chung."""
        self.title(self._t(self._title_key))
        if hasattr(self, "grp_search"):
            self.grp_search.configure(text=self._t("backup.section.search"))
        if hasattr(self, "lbl_table"):
            self.lbl_table.configure(text=self._t("backup.label.table"))

    def _set_icon(self) -> None:
        """Áp dụng biểu tượng ứng dụng nếu khả dụng."""
        try:
            self.iconbitmap("icons/logo.ico")
        except Exception:
            pass

    def _t(self, key: str, **kwargs) -> str:
        """Tiện ích truy xuất chuỗi i18n."""
        return i18n.translate(key, **kwargs)


class BackupWindow(BackupRestoreBase):
    """Màn hình tạo bảng backup với khả năng tùy chỉnh SQL."""

    def __init__(self, parent: tk.Widget, connection: Dict[str, str]):
        super().__init__(parent, connection, title_key="backup.title")
        self._history_action_type = "backup_sql"

    def _build_body(self, parent: ttk.Frame):
        """Xây dựng giao diện đặc thù cho tác vụ backup."""
        parent.columnconfigure(0, weight=1)

        self.lbl_source = ttk.Label(parent, text=self._t("backup.label.source_table"))
        self.lbl_source.grid(row=0, column=0, sticky="w")
        self.ent_source = ttk.Entry(parent, textvariable=self.var_selected_table, state="readonly")
        self.ent_source.grid(row=1, column=0, sticky="ew", pady=(0, 6))

        self.lbl_backup = ttk.Label(parent, text=self._t("backup.label.backup_table"))
        self.lbl_backup.grid(row=2, column=0, sticky="w")
        self.var_backup_name = tk.StringVar()
        self.ent_backup = ttk.Entry(parent, textvariable=self.var_backup_name)
        self.ent_backup.grid(row=3, column=0, sticky="ew", pady=(0, 10))

        self.frm_sql_section = ttk.LabelFrame(parent, text=self._t("backup.section.sql"), padding=6)
        self.frm_sql_section.grid(row=4, column=0, sticky="nsew")
        self.frm_sql_section.columnconfigure(0, weight=1)
        self.frm_sql_section.rowconfigure(0, weight=1)

        self.txt_sql = ScrolledText(self.frm_sql_section, height=10, wrap="word")
        self.txt_sql.grid(row=0, column=0, sticky="nsew")

        self.frm_buttons = ttk.Frame(parent)
        self.frm_buttons.grid(row=5, column=0, sticky="ew", pady=6)
        self.frm_buttons.columnconfigure(0, weight=1)
        self.frm_buttons.columnconfigure(1, weight=1)
        self.btn_refresh_sql = ttk.Button(self.frm_buttons, text=self._t("backup.btn.refresh_sql"), command=self._fill_default_sql_backup)
        self.btn_refresh_sql.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        self.btn_execute = ttk.Button(self.frm_buttons, text=self._t("backup.btn.execute"), command=self._execute)
        self.btn_execute.grid(row=0, column=1, sticky="ew")

        self.frm_log = ttk.LabelFrame(parent, text=self._t("backup.section.log"), padding=6)
        self.frm_log.grid(row=6, column=0, sticky="nsew")
        self.frm_log.columnconfigure(0, weight=1)
        self.frm_log.rowconfigure(0, weight=1)

        self.txt_log = ScrolledText(self.frm_log, height=8, wrap="word", state="normal")
        self.txt_log.grid(row=0, column=0, sticky="nsew")

        parent.rowconfigure(4, weight=1)
        parent.rowconfigure(6, weight=1)

    def on_metadata_loading(self, loading: bool) -> None:
        """Vô hiệu hóa các nút thao tác khi đang tải metadata."""
        super().on_metadata_loading(loading)
        state = "disabled" if loading else "normal"
        widgets = [
            getattr(self, "ent_backup", None),
            getattr(self, "btn_refresh_sql", None),
            getattr(self, "btn_execute", None),
        ]
        for widget in widgets:
            if widget is None:
                continue
            try:
                widget.configure(state=state)
            except tk.TclError:
                continue

    def on_table_ready(self, table: str):
        """Cập nhật thông tin khi bảng nguồn đã sẵn sàng."""
        if not table:
            self.var_backup_name.set("")
            self.txt_sql.delete("1.0", tk.END)
            return
        owner, name = self._split_table(table)
        default_name = f"{owner}.{name}_BK_{dt.datetime.now().strftime('%Y%m%d')}"
        self.var_backup_name.set(default_name)
        self._fill_default_sql_backup()

    def _fill_default_sql_backup(self):
        """Sinh câu SQL tạo bảng backup từ bảng nguồn hiện tại."""
        table = self.var_selected_table.get().strip()
        backup = self.var_backup_name.get().strip()
        if not table or not backup:
            return
        owner_src, src = self._split_table(table)
        owner_bk, bk = self._split_table(backup)
        full_src = f"{owner_src}.{src}"
        full_bk = f"{owner_bk}.{bk}"
        default_sql = (
            f"DROP TABLE {full_bk};\n"
            f"CREATE TABLE {full_bk} AS\n"
            f"SELECT *\nFROM {full_src};"
        )
        self.txt_sql.delete("1.0", tk.END)
        self.txt_sql.insert(tk.END, default_sql)

    def _execute(self):
        """Thực thi các câu lệnh backup đã được chuẩn bị."""
        sql_text = self.txt_sql.get("1.0", tk.END)
        self._run_statements(sql_text)

    def _apply_language(self) -> None:
        """Cập nhật chuỗi dịch cho các thành phần của màn hình backup."""
        super()._apply_language()
        if hasattr(self, "lbl_source"):
            self.lbl_source.configure(text=self._t("backup.label.source_table"))
        if hasattr(self, "lbl_backup"):
            self.lbl_backup.configure(text=self._t("backup.label.backup_table"))
        if hasattr(self, "frm_sql_section"):
            self.frm_sql_section.configure(text=self._t("backup.section.sql"))
        if hasattr(self, "frm_log"):
            self.frm_log.configure(text=self._t("backup.section.log"))
        if hasattr(self, "btn_refresh_sql"):
            self.btn_refresh_sql.configure(text=self._t("backup.btn.refresh_sql"))
        if hasattr(self, "btn_execute"):
            self.btn_execute.configure(text=self._t("backup.btn.execute"))


class RestoreFromBackupWindow(BackupRestoreBase):
    """Khôi phục dữ liệu vào bảng đích từ bảng backup đã có."""

    def __init__(self, parent: tk.Widget, connection: Dict[str, str]):
        self.var_target_table = tk.StringVar()
        super().__init__(parent, connection, title_key="backup.restore_backup.title")
        self._history_action_type = "restore_backup_sql"

    def _build_body(self, parent: ttk.Frame):
        """Xây dựng giao diện dành cho restore từ bảng backup."""
        parent.columnconfigure(0, weight=1)

        self.lbl_target = ttk.Label(parent, text=self._t("backup.label.target_table"))
        self.lbl_target.grid(row=0, column=0, sticky="w")
        self.ent_target = ttk.Entry(parent, textvariable=self.var_target_table, state="readonly")
        self.ent_target.grid(row=1, column=0, sticky="ew", pady=(0, 6))

        self.lbl_backup_source = ttk.Label(parent, text=self._t("backup.label.backup_source_table"))
        self.lbl_backup_source.grid(row=2, column=0, sticky="w")
        self.var_backup_name = tk.StringVar()
        self.ent_backup = ttk.Entry(parent, textvariable=self.var_backup_name)
        self.ent_backup.grid(row=3, column=0, sticky="ew", pady=(0, 10))

        self.frm_sql_section = ttk.LabelFrame(parent, text=self._t("backup.section.sql"), padding=6)
        self.frm_sql_section.grid(row=4, column=0, sticky="nsew")
        self.frm_sql_section.columnconfigure(0, weight=1)
        self.frm_sql_section.rowconfigure(0, weight=1)

        self.txt_sql = ScrolledText(self.frm_sql_section, height=10, wrap="word")
        self.txt_sql.grid(row=0, column=0, sticky="nsew")

        self.frm_buttons = ttk.Frame(parent)
        self.frm_buttons.grid(row=5, column=0, sticky="ew", pady=6)
        self.frm_buttons.columnconfigure(0, weight=1)
        self.frm_buttons.columnconfigure(1, weight=1)
        self.btn_refresh_sql = ttk.Button(self.frm_buttons, text=self._t("backup.btn.refresh_sql"), command=self._fill_restore_sql)
        self.btn_refresh_sql.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        self.btn_execute = ttk.Button(self.frm_buttons, text=self._t("backup.btn.execute"), command=self._execute)
        self.btn_execute.grid(row=0, column=1, sticky="ew")

        self.frm_log = ttk.LabelFrame(parent, text=self._t("backup.section.log"), padding=6)
        self.frm_log.grid(row=6, column=0, sticky="nsew")
        self.frm_log.columnconfigure(0, weight=1)
        self.frm_log.rowconfigure(0, weight=1)

        self.txt_log = ScrolledText(self.frm_log, height=8, wrap="word", state="normal")
        self.txt_log.grid(row=0, column=0, sticky="nsew")

        parent.rowconfigure(4, weight=1)
        parent.rowconfigure(6, weight=1)

    def on_metadata_loading(self, loading: bool) -> None:
        """Disable các nút khi metadata chưa sẵn sàng."""
        super().on_metadata_loading(loading)
        state = "disabled" if loading else "normal"
        widgets = [
            getattr(self, "ent_backup", None),
            getattr(self, "btn_refresh_sql", None),
            getattr(self, "btn_execute", None),
        ]
        for widget in widgets:
            if widget is None:
                continue
            try:
                widget.configure(state=state)
            except tk.TclError:
                continue

    def on_table_ready(self, table: str):
        """Đề xuất tên backup và sinh câu SQL mặc định."""
        if not table:
            self.txt_sql.delete("1.0", tk.END)
            self.var_backup_name.set("")
            self.var_target_table.set("")
            return
        owner, name = self._split_table(table)
        full_backup = f"{owner}.{name}"
        rebuilt_target, _ = self._strip_backup_suffix(owner, name)
        self.var_backup_name.set(full_backup)
        self.var_target_table.set(rebuilt_target)
        self._fill_restore_sql()

    def _fill_restore_sql(self):
        """Sinh SQL restore dữ liệu từ bảng backup sang bảng đích."""
        target = self.var_target_table.get().strip()
        backup = self.var_backup_name.get().strip()
        if not target or not backup:
            return
        tgt_owner, tgt_name = self._split_table(target)
        bk_owner, bk_name = self._split_table(backup)
        full_target = f"{tgt_owner}.{tgt_name}"
        full_backup = f"{bk_owner}.{bk_name}"
        default_sql = (
            f"TRUNCATE TABLE {full_target};\n"
            f"INSERT INTO {full_target}\nSELECT *\nFROM {full_backup};"
        )
        self.txt_sql.delete("1.0", tk.END)
        self.txt_sql.insert(tk.END, default_sql)

    def _fill_backup_sql(self):
        """Sinh SQL để tái tạo bảng backup từ bảng đích."""
        table = self.var_target_table.get().strip()
        backup = self.var_backup_name.get().strip()
        if not table or not backup:
            return
        owner_src, src = self._split_table(table)
        owner_bk, bk = self._split_table(backup)
        full_src = f"{owner_src}.{src}"
        full_bk = f"{owner_bk}.{bk}"
        default_sql = (
            f"DROP TABLE {full_bk};\n"
            f"CREATE TABLE {full_bk} AS\n"
            f"SELECT *\nFROM {full_src};"
        )
        self.txt_sql.delete("1.0", tk.END)
        self.txt_sql.insert(tk.END, default_sql)

    def _execute(self):
        """Thực thi câu SQL hiện tại."""
        sql_text = self.txt_sql.get("1.0", tk.END)
        self._run_statements(sql_text)

    def _apply_language(self) -> None:
        """Cập nhật chuỗi dịch cho các thành phần của màn hình restore."""
        super()._apply_language()
        if hasattr(self, "lbl_target"):
            self.lbl_target.configure(text=self._t("backup.label.target_table"))
        if hasattr(self, "lbl_backup_source"):
            self.lbl_backup_source.configure(text=self._t("backup.label.backup_source_table"))
        if hasattr(self, "frm_sql_section"):
            self.frm_sql_section.configure(text=self._t("backup.section.sql"))
        if hasattr(self, "frm_log"):
            self.frm_log.configure(text=self._t("backup.section.log"))
        if hasattr(self, "btn_refresh_sql"):
            self.btn_refresh_sql.configure(text=self._t("backup.btn.refresh_sql"))
        if hasattr(self, "btn_execute"):
            self.btn_execute.configure(text=self._t("backup.btn.execute"))

    @staticmethod
    def _strip_backup_suffix(owner: str, table: str) -> tuple[str, bool]:
        """
        Remove trailing BK timestamp suffixes so restore target points back to the original table.
        """
        base = table
        changed = False
        patterns = [
            r"(.*)_BK_(\d{8})$",
            r"(.*)_BK(\d{8})$",
            r"(.*)_BK$",
        ]
        for pattern in patterns:
            match = re.match(pattern, table, flags=re.IGNORECASE)
            if match:
                candidate = match.group(1)
                if candidate:
                    base = candidate
                    changed = True
                    break
        full = f"{owner}.{base}"
        return full, changed

    def _history_object_name(self) -> str:
        target = getattr(self, "var_target_table", None)
        if isinstance(target, tk.StringVar):
            value = target.get().strip()
            if value:
                return value
        return super()._history_object_name()


class RestoreFromCSVWindow(BackupRestoreBase):
    """
    Restore data into a table using CSV import.
    """

    GEOMETRY = "720x640"

    def __init__(self, parent: tk.Widget, connection: Dict[str, str]):
        self.imported_rows: List[Dict[str, str]] = []
        self.csv_headers: List[str] = []
        self._last_csv_path: Optional[str] = None
        self._history_action_type = "restore_csv"
        super().__init__(parent, connection, title_key="backup.restore_csv.title")
        try:
            self.list_tables.configure(height=4)
            self.grp_search.rowconfigure(2, weight=0)
        except Exception:
            pass

    def _build_body(self, parent: ttk.Frame):
        """Xây dựng giao diện dành cho restore từ CSV."""
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(3, weight=1)

        self.lbl_target = ttk.Label(parent, text=self._t("backup.label.target_table"))
        self.lbl_target.grid(row=0, column=0, sticky="w")
        self.ent_target = ttk.Entry(parent, textvariable=self.var_selected_table, state="readonly")
        self.ent_target.grid(row=1, column=0, sticky="ew", pady=(0, 6))

        self.frm_actions = ttk.Frame(parent)
        self.frm_actions.grid(row=2, column=0, sticky="ew", pady=(0, 4))
        self.frm_actions.columnconfigure(0, weight=0)
        self.frm_actions.columnconfigure(1, weight=1)
        self.btn_import_csv = ttk.Button(self.frm_actions, text=self._t("backup.btn.import_csv"), command=self._import_csv)
        self.btn_import_csv.grid(row=0, column=0, sticky="w")
        self.lbl_file = ttk.Label(self.frm_actions, text=self._t("backup.label.no_file"))
        self.lbl_file.grid(row=0, column=1, sticky="w", padx=(12, 0))

        self.content_pane = ttk.Panedwindow(parent, orient="vertical")
        self.content_pane.grid(row=3, column=0, sticky="nsew")

        preview_container = ttk.Frame(self.content_pane)
        preview_container.columnconfigure(0, weight=1)
        preview_container.rowconfigure(0, weight=1)
        self.content_pane.add(preview_container, weight=3)

        self.frm_preview = ttk.LabelFrame(preview_container, text=self._t("backup.section.preview"), padding=4)
        self.frm_preview.grid(row=0, column=0, sticky="nsew")
        self.frm_preview.columnconfigure(0, weight=1)
        self.frm_preview.rowconfigure(0, weight=1)

        self.preview_grid = DataGrid(self.frm_preview)
        self.preview_grid.grid(row=0, column=0, sticky="nsew")

        self.frm_preview_buttons = ttk.Frame(self.frm_preview)
        self.frm_preview_buttons.grid(row=1, column=0, sticky="ew", pady=(6, 0))
        self.frm_preview_buttons.columnconfigure(0, weight=1)
        self.frm_preview_buttons.columnconfigure(1, weight=0)
        self.btn_clear_preview = ttk.Button(self.frm_preview_buttons, text=self._t("backup.btn.clear_preview"), command=self._clear_preview)
        self.btn_clear_preview.grid(row=0, column=0, sticky="w")
        self.btn_execute_restore = ttk.Button(self.frm_preview_buttons, text=self._t("backup.btn.execute_restore"), command=self._execute_restore)
        self.btn_execute_restore.grid(row=0, column=1, sticky="e", padx=(12, 0))

        log_container = ttk.Frame(self.content_pane)
        log_container.columnconfigure(0, weight=1)
        log_container.rowconfigure(0, weight=1)
        self.content_pane.add(log_container, weight=2)

        self.frm_log = ttk.LabelFrame(log_container, text=self._t("backup.section.log"), padding=6)
        self.frm_log.grid(row=0, column=0, sticky="nsew")
        self.frm_log.columnconfigure(0, weight=1)
        self.frm_log.rowconfigure(0, weight=1)

        self.txt_log = ScrolledText(self.frm_log, height=8, wrap="word", state="normal")
        self.txt_log.grid(row=0, column=0, sticky="nsew")


    def on_metadata_loading(self, loading: bool) -> None:
        """Khóa các thao tác nhập CSV khi metadata chưa sẵn sàng."""
        super().on_metadata_loading(loading)
        state = "disabled" if loading else "normal"
        widgets = [
            getattr(self, "btn_import_csv", None),
            getattr(self, "btn_clear_preview", None),
            getattr(self, "btn_execute_restore", None),
        ]
        for widget in widgets:
            if widget is None:
                continue
            try:
                widget.configure(state=state)
            except tk.TclError:
                continue
        try:
            self.preview_grid.tree.configure(state="normal" if not loading else "disabled")
        except (AttributeError, tk.TclError):
            pass

    def on_table_ready(self, table: str):
        """Chuẩn bị lại dữ liệu xem trước khi bảng đích thay đổi."""
        if self._columns:
            self.preview_grid.configure_columns(self._columns)
        self.imported_rows.clear()
        self.preview_grid.clear()
        self.lbl_file.config(text=self._t("backup.label.no_file"))

    def _import_csv(self):
        """Đọc dữ liệu từ tệp CSV và hiển thị lên lưới xem trước."""
        table = self.var_selected_table.get().strip()
        if not table:
            messagebox.showwarning(self._t(APP_TITLE_KEY), self._t("backup.msg.no_target_table"), parent=self)
            return
        path = filedialog.askopenfilename(
            title=self._t("backup.dialog.select_csv"),
            filetypes=[
                (self._t("backup.dialog.csv_files"), "*.csv"),
                (self._t("backup.dialog.all_files"), "*.*"),
            ],
            parent=self,
        )
        if not path:
            return
        self._last_csv_path = path
        try:
            with open(path, "r", encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                if not reader.fieldnames:
                    raise ValueError(self._t("backup.msg.missing_header"))
                headers = [h.strip() for h in reader.fieldnames]
                rows = [row for row in reader]
        except Exception as exc:
            self._log_exception(f"Failed to import CSV {path}", exc)
            messagebox.showerror(self._t(APP_TITLE_KEY), self._t("backup.msg.read_csv_error", error=str(exc)), parent=self)
            return

        table_cols = [col.upper() for col in self._columns]
        csv_cols = [h.upper() for h in headers]
        missing = [col for col in table_cols if col not in csv_cols]
        extra = [col for col in csv_cols if col not in table_cols]
        warnings = []
        if missing:
            warnings.append(self._t("backup.msg.missing_columns", columns=", ".join(missing)))
        if extra:
            warnings.append(self._t("backup.msg.extra_columns", columns=", ".join(extra)))
        if warnings:
            messagebox.showwarning(self._t(APP_TITLE_KEY), "\n".join(warnings), parent=self)

        self.lbl_file.config(text=path)
        self.preview_grid.configure_columns(self._columns)
        self.preview_grid.clear()

        formatted_rows: List[Dict[str, str]] = []
        for row in rows:
            normalized = {(key or "").upper(): value for key, value in row.items()}
            item = {}
            for col in self._columns:
                item[col] = normalized.get(col.upper(), "")
            formatted_rows.append(item)
            self.preview_grid.append_dict(item)

        self.imported_rows = formatted_rows
        self.csv_headers = headers
        self._append_log(self._t("backup.log.import_summary", count=len(formatted_rows), path=path))

    def _clear_preview(self):
        """Xóa dữ liệu CSV đang xem trước."""
        self.imported_rows.clear()
        self.preview_grid.clear()
        self.lbl_file.config(text=self._t("backup.label.no_file"))

    def _execute_restore(self):
        """Restore du lieu CSV vao bang dich."""
        table = self.var_selected_table.get().strip()
        if not table:
            messagebox.showwarning(self._t(APP_TITLE_KEY), self._t("backup.msg.select_table"), parent=self)
            return
        if not self.imported_rows:
            messagebox.showwarning(self._t(APP_TITLE_KEY), self._t("backup.msg.no_csv_data"), parent=self)
            return
        row_count = len(self.imported_rows)
        sql_summary = f"CSV restore into {table}"
        log_message = f"Restore from {self._last_csv_path}" if getattr(self, "_last_csv_path", None) else "Restore from CSV"
        if not self.conn:
            history.log_action(self._history_action_type, table, row_count, "failed", message=self._t("backup.msg.not_connected"), sql_text=sql_summary)
            messagebox.showerror(self._t(APP_TITLE_KEY), self._t("backup.msg.not_connected"), parent=self)
            return
        if not messagebox.askyesno(
            self._t(APP_TITLE_KEY),
            self._t("backup.msg.restore_confirm", count=row_count, table=table),
            parent=self,
        ):
            return

        owner, name = self._split_table(table)
        full_table = f"{owner}.{name}"
        col_list = ", ".join(self._columns)

        try:
            cur = self.conn.cursor()
        except Exception as exc:
            msg = self._t("backup.msg.cursor_error", error=str(exc))
            self._log_exception("Failed to create cursor for CSV restore", exc)
            history.log_action(self._history_action_type, full_table, row_count, "failed", message=msg, sql_text=sql_summary)
            messagebox.showerror(self._t(APP_TITLE_KEY), msg, parent=self)
            return

        action_id = history.log_action(self._history_action_type, full_table, row_count, "pending", message=log_message, sql_text=sql_summary)

        def _finalize(status: str, message: str) -> None:
            try:
                if action_id:
                    history.mark_action_status(action_id, status, message, row_count=row_count, sql_text=sql_summary)
                else:
                    history.log_action(self._history_action_type, full_table, row_count, status, message=message, sql_text=sql_summary)
            except Exception as exc:
                self._log_exception("Failed to finalize CSV restore history", exc)

        try:
            for idx, row in enumerate(self.imported_rows, start=1):
                values = []
                for col in self._columns:
                    meta = self._column_meta.get(col)
                    values.append(db_utils.format_sql_literal(row.get(col), meta))
                stmt = f"INSERT INTO {full_table} ({col_list}) VALUES ({', '.join(values)})"
                self._append_log(f"> {stmt}")
                cur.execute(stmt)
                if idx % 100 == 0:
                    self.conn.commit()
            self.conn.commit()
        except Exception as exc:
            self.conn.rollback()
            self._append_log(f"ERROR: {exc}")
            msg = self._t("backup.msg.restore_error", error=str(exc))
            self._log_exception("Failed during CSV restore execution", exc)
            _finalize("failed", msg)
            messagebox.showerror(self._t(APP_TITLE_KEY), msg, parent=self)
            return
        finally:
            try:
                cur.close()
            except Exception as exc:
                self._logger.debug("CSV restore cursor close failed: %s", exc)

        self._append_log(self._t("backup.log.restore_done"))
        _finalize("success", self._t("backup.log.restore_done"))
        messagebox.showinfo(self._t(APP_TITLE_KEY), self._t("backup.msg.restore_success"), parent=self)


    def _apply_language(self) -> None:
        """Cập nhật chuỗi dịch cho các thành phần restore CSV."""
        super()._apply_language()
        if hasattr(self, "lbl_target"):
            self.lbl_target.configure(text=self._t("backup.label.target_table"))
        if hasattr(self, "frm_preview"):
            self.frm_preview.configure(text=self._t("backup.section.preview"))
        if hasattr(self, "frm_log"):
            self.frm_log.configure(text=self._t("backup.section.log"))
        if hasattr(self, "btn_import_csv"):
            self.btn_import_csv.configure(text=self._t("backup.btn.import_csv"))
        if hasattr(self, "btn_clear_preview"):
            self.btn_clear_preview.configure(text=self._t("backup.btn.clear_preview"))
        if hasattr(self, "btn_execute_restore"):
            self.btn_execute_restore.configure(text=self._t("backup.btn.execute_restore"))
        if hasattr(self, "lbl_file") and not self.imported_rows:
            self.lbl_file.configure(text=self._t("backup.label.no_file"))
        if hasattr(self, "preview_grid"):
            self.preview_grid.apply_language()


class BackupModeDialog(tk.Toplevel):
    """Hộp thoại chọn chế độ Backup/Restore."""

    def __init__(self, parent: tk.Widget):
        super().__init__(parent)
        self.result: Optional[str] = None
        self.title(i18n.translate("backup.choice.title"))
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        frame = ttk.Frame(self, padding=16)
        frame.pack(fill="both", expand=True)

        ttk.Label(
            frame,
            text=i18n.translate("backup.choice.message"),
            wraplength=360,
            justify="left",
        ).pack(fill="x", pady=(0, 12))

        ttk.Button(
            frame,
            text=i18n.translate("backup.choice.backup"),
            command=lambda: self._set_choice("backup"),
        ).pack(fill="x", pady=4)
        ttk.Button(
            frame,
            text=i18n.translate("backup.choice.restore_backup"),
            command=lambda: self._set_choice("restore_backup"),
        ).pack(fill="x", pady=4)
        ttk.Button(
            frame,
            text=i18n.translate("backup.choice.restore_csv"),
            command=lambda: self._set_choice("restore_csv"),
        ).pack(fill="x", pady=(4, 12))
        ttk.Button(
            frame,
            text=i18n.translate("common.cancel"),
            command=self._cancel,
        ).pack(fill="x")

        self.bind("<Escape>", lambda _e: self._cancel())
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self._center_over_parent(parent)

    def _center_over_parent(self, parent: tk.Widget):
        try:
            self.update_idletasks()
            px = parent.winfo_rootx()
            py = parent.winfo_rooty()
            pw = parent.winfo_width()
            ph = parent.winfo_height()
            w = self.winfo_width()
            h = self.winfo_height()
            if w <= 1 or h <= 1:
                w = self.winfo_reqwidth()
                h = self.winfo_reqheight()
            x = px + (pw - w) // 2
            y = py + (ph - h) // 2
            self.geometry(f"+{x}+{y}")
        except Exception:
            pass

    def _set_choice(self, choice: str):
        self.result = choice
        self.destroy()

    def _cancel(self):
        self.result = None
        self.destroy()


def ask_backup_mode(parent: tk.Widget) -> Optional[str]:
    """Hiển thị hộp thoại chọn chế độ Backup/Restore."""
    dialog = BackupModeDialog(parent)
    parent.wait_window(dialog)
    return dialog.result


def open_backup_window(parent: tk.Widget, connection: Dict[str, str]):
    """Mở màn hình tạo backup."""
    BackupWindow(parent, connection)


def open_restore_from_backup_window(parent: tk.Widget, connection: Dict[str, str]):
    """Mở màn hình restore từ bảng backup."""
    RestoreFromBackupWindow(parent, connection)


def open_restore_from_csv_window(parent: tk.Widget, connection: Dict[str, str]):
    """Mở màn hình restore từ tệp CSV."""
    RestoreFromCSVWindow(parent, connection)
