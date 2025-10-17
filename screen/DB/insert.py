"""
Màn hình Insert phục vụ nhập liệu vào bảng cơ sở dữ liệu.
"""
from __future__ import annotations

import threading
import tkinter as tk
from tkinter import messagebox, ttk
from tkinter.scrolledtext import ScrolledText
from typing import Dict, List, Optional

from screen.DB import db_utils
from screen.DB.widgets import ColumnOrderDialog, DataGrid, DuplicatePreviewDialog, LoadingPopup
from core import history, i18n, templates
from screen.DB.template_dialog import TemplateLibraryDialog, TemplateSaveDialog

APP_TITLE_KEY = "common.app_title"

ACTIVE_WINDOWS: List["InsertWindow"] = []


class InsertWindow(tk.Toplevel):
    def __init__(self, parent: tk.Widget, connection: Dict[str, str]):
        """Khởi tạo cửa sổ Insert với thông tin kết nối đã chọn."""
        super().__init__(parent)
        self.parent = parent
        self.conn_info = connection
        self.conn = None
        self.current_owner = connection.get("user", "").upper()
        self.title(self._t("insert.title"))
        self.geometry("1180x720")
        self.minsize(960, 600)
        self.resizable(True, True)
        self._set_icon()

        self._table_items: List[Dict[str, str]] = []
        self._table_view: List[Dict[str, str]] = []
        self._active_table: Optional[Dict[str, str]] = None
        self._columns: List[str] = []
        self._column_meta: Dict[str, dict] = {}
        self._pk_columns: List[str] = []
        self._generated_rows: List[Dict[str, str]] = []
        self._draft_history_id: Optional[int] = None
        self._draft_history_sql: str = ""
        self._loader: Optional[LoadingPopup] = None
        self._current_table_label: str = "..."

        ACTIVE_WINDOWS.append(self)

        self._build_ui()
        self._lang_listener = self._handle_language_change
        i18n.add_listener(self._lang_listener)
        self._apply_language()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(100, self._connect_async)

    # ------------------------------------------------------------------
    def _build_ui(self):
        """Xây dựng bố cục chính của màn hình Insert."""
        self.frm_main = ttk.Frame(self, padding=8)
        self.frm_main.pack(fill="both", expand=True)
        self.frm_main.rowconfigure(1, weight=1)
        self.frm_main.columnconfigure(0, weight=1)

        self.frm_top = ttk.Frame(self.frm_main)
        self.frm_top.grid(row=0, column=0, sticky="ew")
        for index in range(3):
            self.frm_top.columnconfigure(index, weight=0 if index else 1)

        self._build_search(self.frm_top)
        self._build_actions(self.frm_top)
        self._build_connection(self.frm_top)

        self.frm_middle = ttk.Frame(self.frm_main)
        self.frm_middle.grid(row=1, column=0, sticky="nsew", pady=(8, 6))
        self.frm_middle.rowconfigure(0, weight=1)
        self.frm_middle.columnconfigure(0, weight=1)

        self.grid = DataGrid(self.frm_middle)
        self.grid.grid(row=0, column=0, sticky="nsew")

        self.btn_bar = ttk.Frame(self.frm_middle)
        self.btn_bar.grid(row=1, column=0, sticky="e", pady=(6, 0))
        self.btn_import_csv = ttk.Button(self.btn_bar, text=self._t("insert.btn.import_csv"), command=self.grid.import_csv_dialog)
        self.btn_import_csv.pack(side="left", padx=4)
        self.btn_export_csv = ttk.Button(self.btn_bar, text=self._t("insert.btn.export_csv"), command=self.grid.export_csv_dialog)
        self.btn_export_csv.pack(side="left", padx=4)
        self.btn_add_row = ttk.Button(self.btn_bar, text=self._t("insert.btn.add_row"), command=lambda: self.grid.append_dict({}))
        self.btn_add_row.pack(side="left", padx=4)

        self.frm_sql = ttk.LabelFrame(
            self.frm_main,
            text=self._t("insert.section.sql", table=self._current_table_label),
            padding=6,
        )
        self.frm_sql.grid(row=2, column=0, sticky="nsew")
        self.frm_sql.rowconfigure(0, weight=1)
        self.frm_sql.columnconfigure(0, weight=1)

        self.txt_sql = ScrolledText(self.frm_sql, height=8, wrap="word")
        self.txt_sql.grid(row=0, column=0, sticky="nsew")


    def _build_search(self, parent: ttk.Frame):
        """Khởi tạo khu vực tìm kiếm bảng nguồn."""
        self.grp_search = ttk.LabelFrame(parent, text=self._t("insert.section.search"), padding=6)
        self.grp_search.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.grp_search.columnconfigure(0, weight=1)

        self.lbl_table_name = ttk.Label(self.grp_search, text=self._t("insert.label.table_name"))
        self.lbl_table_name.grid(row=0, column=0, sticky="w")
        self.var_search = tk.StringVar()
        self.ent_search = ttk.Entry(self.grp_search, textvariable=self.var_search)
        self.ent_search.grid(row=1, column=0, sticky="ew", pady=4)
        self.ent_search.bind("<KeyRelease>", lambda _event: self._filter_tables())
        self.list_tables = tk.Listbox(self.grp_search, height=10)
        self.list_tables.grid(row=2, column=0, sticky="nsew", pady=(0, 4))
        self.list_tables.bind("<<ListboxSelect>>", self._on_select_table)
        self.grp_search.rowconfigure(2, weight=1)



    def _build_actions(self, parent: ttk.Frame):
        """Tạo nhóm nút thao tác chính cho việc insert."""
        self.grp_actions = ttk.LabelFrame(parent, text=self._t("insert.section.actions"), padding=6)
        self.grp_actions.grid(row=0, column=1, sticky="n", padx=(0, 8))
        self.btn_build_sql = ttk.Button(self.grp_actions, text=self._t("insert.btn.build_sql"), command=self._generate_sql)
        self.btn_build_sql.grid(row=0, column=0, sticky="ew", pady=4)
        self.btn_save_template = ttk.Button(self.grp_actions, text=self._t("insert.btn.save_template"), command=self._save_template)
        self.btn_save_template.grid(row=1, column=0, sticky="ew", pady=4)
        self.btn_select_template = ttk.Button(self.grp_actions, text=self._t("insert.btn.select_template"), command=self._open_template_library)
        self.btn_select_template.grid(row=2, column=0, sticky="ew", pady=4)
        self.btn_copy = ttk.Button(self.grp_actions, text=self._t("common.copy"), command=self._copy_sql)
        self.btn_copy.grid(row=3, column=0, sticky="ew", pady=4)
        self.btn_reorder = ttk.Button(self.grp_actions, text=self._t("insert.btn.reorder"), command=self._change_column_order)
        self.btn_reorder.grid(row=4, column=0, sticky="ew", pady=4)
        self.btn_execute = ttk.Button(self.grp_actions, text=self._t("insert.btn.execute"), command=self._execute)
        self.btn_execute.grid(row=5, column=0, sticky="ew", pady=4)
        self.btn_clear = ttk.Button(self.grp_actions, text=self._t("insert.btn.clear"), command=self._clear)
        self.btn_clear.grid(row=6, column=0, sticky="ew", pady=4)



    def _build_connection(self, parent: ttk.Frame):
        """Hiển thị thông tin kết nối hiện hành."""
        self.grp_connection = ttk.LabelFrame(parent, text=self._t("insert.section.connection"), padding=6, width=240)
        self.grp_connection.grid(row=0, column=2, sticky="n")

        self.lbl_user = ttk.Label(self.grp_connection, text=self._t("main.label.user_id"))
        self.lbl_user.grid(row=0, column=0, sticky="w", pady=2)
        entry_user = ttk.Entry(self.grp_connection)
        entry_user.insert(0, self.conn_info.get("user", ""))
        entry_user.configure(state="readonly")
        entry_user.grid(row=0, column=1, sticky="ew", pady=2, padx=(6, 0))

        self.lbl_datasource = ttk.Label(self.grp_connection, text=self._t("main.label.data_source"))
        self.lbl_datasource.grid(row=1, column=0, sticky="w", pady=2)
        entry_alias = ttk.Entry(self.grp_connection)
        entry_alias.insert(0, self.conn_info.get("alias", ""))
        entry_alias.configure(state="readonly")
        entry_alias.grid(row=1, column=1, sticky="ew", pady=2, padx=(6, 0))

        self.lbl_hostport = ttk.Label(self.grp_connection, text=self._t("main.label.host_port"))
        self.lbl_hostport.grid(row=2, column=0, sticky="w", pady=2)
        entry_host = ttk.Entry(self.grp_connection)
        entry_host.insert(0, self.conn_info.get("host", ""))
        entry_host.configure(state="readonly")
        entry_host.grid(row=2, column=1, sticky="ew", pady=2, padx=(6, 0))
        entry_port = ttk.Entry(self.grp_connection, width=8)
        entry_port.insert(0, self.conn_info.get("port", ""))
        entry_port.configure(state="readonly")
        entry_port.grid(row=2, column=2, sticky="w", pady=2, padx=(3, 0))

        self.grp_connection.columnconfigure(1, weight=1)



    # ------------------------------------------------------------------
    def _connect_async(self):
        """Khởi tạo kết nối và tải danh sách bảng trong luồng nền."""
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
                self.after(0, lambda m=msg: self._show_error(m))
                return
            except Exception as exc:
                msg = self._t("common.msg.connection_error", error=str(exc))
                self.after(0, lambda m=msg: self._show_error(m))
                return
            self.after(0, lambda: self._init_tables(tables))

        self._show_loading(self._t("common.loading_tables"))
        threading.Thread(target=worker, daemon=True).start()

    def _show_error(self, msg: str):
        """Hiển thị thông báo lỗi và đóng cửa sổ."""
        self._hide_loading()
        messagebox.showerror(self._t(APP_TITLE_KEY), msg, parent=self)
        self.destroy()

    def _init_tables(self, tables: List[str]):
        """Nạp danh sách bảng truy cập được vào giao diện."""
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
            self._on_select_table()
        else:
            self._active_table = None
            self._set_sql_label("...")

    # ------------------------------------------------------------------
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
            self._on_select_table()
        else:
            self._active_table = None
            self.grid.clear()
            self.txt_sql.delete("1.0", tk.END)
            self._set_sql_label("...")

    def _on_select_table(self, _event=None):
        """Xử lý khi người dùng chọn bảng trong danh sách."""
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
        self._load_table_metadata(item)

    def _load_table_metadata(self, item: Dict[str, str]):
        """Đọc metadata của bảng để cấu hình lưới dữ liệu."""
        if not self.conn:
            return
        try:
            columns = db_utils.fetch_table_columns(self.conn, item["full"], self.current_owner)
            pk_cols = db_utils.fetch_primary_keys(self.conn, item["full"], self.current_owner)
        except Exception as exc:
            messagebox.showerror(self._t(APP_TITLE_KEY), self._t("insert.msg.metadata_error", error=str(exc)), parent=self)
            return
        self._columns = [col["column_name"] for col in columns]
        self._column_meta = {col["column_name"]: col for col in columns}
        self._pk_columns = pk_cols
        self.grid.configure_columns(self._columns)
        self.grid.clear()
        self.grid.append_dict({})
        self._generated_rows.clear()
        self._set_sql_label(item["display"])

    def _set_sql_label(self, table_display: str):
        """Cập nhật tiêu đề của khung SQL theo bảng đang chọn."""
        self._current_table_label = table_display or "..."
        self.frm_sql.config(text=self._t("insert.section.sql", table=self._current_table_label))

    # ------------------------------------------------------------------
    def _generate_sql(self):
        """Sinh câu lệnh INSERT tương ứng với dữ liệu đang có."""
        rows = self.grid.get_all()
        if not rows:
            messagebox.showwarning(self._t(APP_TITLE_KEY), self._t("insert.msg.no_data_generate"), parent=self)
            return
        if not self._columns:
            messagebox.showwarning(self._t(APP_TITLE_KEY), self._t("insert.msg.no_table"), parent=self)
            return
        table = self._current_table()
        if not table:
            messagebox.showwarning(self._t(APP_TITLE_KEY), self._t("insert.msg.no_table"), parent=self)
            return
        column_list = ", ".join(self._columns)
        sql_lines: List[str] = []
        formatted_rows: List[Dict[str, str]] = []
        for row in rows:
            values = []
            formatted_row = {}
            for col in self._columns:
                meta = self._column_meta.get(col, {})
                literal = db_utils.format_sql_literal(row.get(col), meta)
                formatted_row[col] = literal
                values.append(literal)
            sql_lines.append(f"INSERT INTO {table} ({column_list}) VALUES ({', '.join(values)});")
            formatted_rows.append(row)
        sql_text = "".join(sql_lines)
        self.txt_sql.delete("1.0", tk.END)
        self.txt_sql.insert(tk.END, sql_text)
        self._generated_rows = formatted_rows
        self._record_history_draft(table, sql_text, len(rows))

    def _record_history_draft(self, table: str, sql_text: str, row_count: int) -> None:
        """Ghi log ban nhap SQL o trang thai nhap."""
        trimmed = (sql_text or "").strip()
        self._draft_history_sql = trimmed
        if not trimmed:
            self._draft_history_id = None
            return
        try:
            action_id = history.log_action(
                "insert_sql",
                table or "",
                row_count,
                "draft",
                message=(f"Draft insert for {table}" if table else "Draft insert SQL"),
                sql_text=trimmed,
            )
            self._draft_history_id = action_id
        except Exception:
            self._draft_history_id = None

    def _copy_sql(self):
        """Copy câu SQL đã sinh vào clipboard."""
        data = self.txt_sql.get("1.0", tk.END).strip()
        if not data:
            return
        self.clipboard_clear()
        self.clipboard_append(data)
        messagebox.showinfo(self._t(APP_TITLE_KEY), self._t("insert.msg.copy_done"), parent=self)

    def _save_template(self):
        """Luu cau SQL hien tai vao thu vien template."""
        sql_text = self.txt_sql.get("1.0", tk.END).strip()
        if not sql_text:
            messagebox.showwarning(self._t(APP_TITLE_KEY), self._t("template.save.message_no_sql"), parent=self)
            return
        default_name = self._current_table() or self._current_table_label or "INSERT_SQL"
        dlg = TemplateSaveDialog(self, default_type="insert", default_name=default_name)
        self.wait_window(dlg)
        data = getattr(dlg, "result", None)
        if not data:
            return
        tpl = templates.add_template(data["name"], data["type"], sql_text, data.get("description", ""))
        if tpl:
            messagebox.showinfo(self._t(APP_TITLE_KEY), self._t("template.save.message_saved"), parent=self)
        else:
            messagebox.showerror(self._t(APP_TITLE_KEY), self._t("common.error"), parent=self)

    def _open_template_library(self):
        """Mo thu vien template de chon cau SQL co san."""
        dlg = TemplateLibraryDialog(self, template_type="insert")
        self.wait_window(dlg)
        record = getattr(dlg, "result", None)
        if record and record.get("content"):
            self.set_sql_text(record["content"])

    def set_sql_text(self, sql_text: str) -> None:
        """Dat lai noi dung SQL va dua cua so len truoc."""
        self.txt_sql.delete("1.0", tk.END)
        self.txt_sql.insert(tk.END, sql_text)
        self._draft_history_sql = (sql_text or "").strip()
        self._draft_history_id = None
        self.lift()
        self.focus_force()

    def _change_column_order(self):
        """Thay đổi thứ tự các cột trước khi xuất SQL."""
        if not self._columns:
            messagebox.showwarning(self._t(APP_TITLE_KEY), self._t("insert.msg.no_columns_update"), parent=self)
            return
        current_rows = self.grid.get_all()
        dlg = ColumnOrderDialog(self, self._columns)
        self.wait_window(dlg)
        if dlg.result:
            self._columns = dlg.result
            self.grid.configure_columns(self._columns)
            self.grid.clear()
            for row in current_rows:
                self.grid.append_dict(row)
            self._generated_rows = current_rows

    def _clear(self):
        """Xóa dữ liệu đã nhập và câu SQL đã sinh."""
        if not messagebox.askyesno(self._t(APP_TITLE_KEY), self._t("insert.msg.clear_confirm"), parent=self):
            return
        self.grid.clear()
        self.grid.append_dict({})
        self.txt_sql.delete("1.0", tk.END)
        self._generated_rows.clear()
        self._draft_history_id = None
        self._draft_history_sql = ""

    def _execute(self):
        """Thuc thi cau lenh INSERT len co so du lieu."""
        table = self._current_table()
        if not table:
            messagebox.showwarning(self._t(APP_TITLE_KEY), self._t("insert.msg.no_table"), parent=self)
            return
        rows = self.grid.get_all()
        if not rows:
            messagebox.showwarning(self._t(APP_TITLE_KEY), self._t("insert.msg.no_data_execute"), parent=self)
            return
        if not messagebox.askyesno(self._t(APP_TITLE_KEY), self._t("insert.msg.confirm_execute"), parent=self):
            return
        row_count = len(rows)
        sql_text_full = self.txt_sql.get("1.0", tk.END)
        sql_text_trim = (sql_text_full or "").strip()
        if not self.conn:
            msg = self._t("insert.msg.not_connected")
            self._log_history_status("failed", msg, row_count, sql_text_trim, table)
            messagebox.showerror(self._t(APP_TITLE_KEY), msg, parent=self)
            return
        pk_cols = self._pk_columns
        pk_missing = [row for row in rows if any(not row.get(pk) for pk in pk_cols)]
        if pk_cols and pk_missing:
            if not messagebox.askyesno(self._t(APP_TITLE_KEY), self._t("insert.msg.pk_missing_confirm"), parent=self):
                return
        duplicates: Dict[tuple, Dict[str, str]] = {}
        try:
            if pk_cols:
                keys = []
                for row in rows:
                    if any(row.get(pk) == "" for pk in pk_cols):
                        continue
                    keys.append([row.get(pk) for pk in pk_cols])
                duplicates = db_utils.fetch_rows_by_pk(self.conn, table, self.current_owner, pk_cols, keys)
        except Exception as exc:
            msg = self._t("insert.msg.check_duplicates_error", error=str(exc))
            self._log_history_status("failed", msg, row_count, sql_text_trim, table)
            messagebox.showerror(self._t(APP_TITLE_KEY), msg, parent=self)
            return

        if duplicates:
            dup_user = []
            for row in rows:
                key = tuple("" if row.get(pk) is None else str(row.get(pk)) for pk in pk_cols)
                if key in duplicates:
                    dup_user.append(row)
            dlg = DuplicatePreviewDialog(
                self,
                table_name=table,
                columns=self._columns,
                pk_columns=pk_cols,
                user_rows=dup_user,
                db_rows=list(duplicates.values()),
            )
            self.wait_window(dlg)
            if not dlg.result:
                return
            try:
                db_utils.delete_by_pk(
                    self.conn,
                    table,
                    self.current_owner,
                    pk_cols,
                    duplicates.keys(),
                )
            except Exception as exc:
                msg = self._t("insert.msg.delete_old_error", error=str(exc))
                self._log_history_status("failed", msg, row_count, sql_text_trim, table)
                messagebox.showerror(self._t(APP_TITLE_KEY), msg, parent=self)
                return

        try:
            ordered_rows = []
            for row in rows:
                ordered_rows.append([row.get(col) if row.get(col) != "" else None for col in self._columns])
            db_utils.insert_rows(self.conn, table, self.current_owner, self._columns, ordered_rows)
        except Exception as exc:
            msg = self._t("insert.msg.insert_error", error=str(exc))
            self._log_history_status("failed", msg, row_count, sql_text_trim, table)
            messagebox.showerror(self._t(APP_TITLE_KEY), msg, parent=self)
            return

        self._log_history_status("success", self._t("insert.msg.insert_success"), row_count, sql_text_trim, table)
        messagebox.showinfo(self._t(APP_TITLE_KEY), self._t("insert.msg.insert_success"), parent=self)


    # ------------------------------------------------------------------
    def _current_table(self) -> Optional[str]:
        """Trả về tên bảng đầy đủ đang được chọn."""
        if not self._active_table:
            return None
        return self._active_table["full"]

    def _on_close(self):
        """Đóng cửa sổ và giải phóng kết nối."""
        self._hide_loading()
        try:
            if self.conn:
                self.conn.close()
        except Exception:
            pass
        self.destroy()

    def destroy(self):
        """Hủy toplevel và gỡ listener ngôn ngữ."""
        if hasattr(self, "_lang_listener"):
            i18n.remove_listener(self._lang_listener)
        if self in ACTIVE_WINDOWS:
            try:
                ACTIVE_WINDOWS.remove(self)
            except ValueError:
                pass
        super().destroy()

    def _log_history_status(self, status: str, message: str, row_count: int, sql_text: str, table: Optional[str]) -> None:
        """Cap nhat lich su insert voi trang thai cu the."""
        trimmed = (sql_text or "").strip()
        base_trim = (self._draft_history_sql or "").strip()
        if not trimmed and base_trim:
            trimmed = base_trim
            sql_text = base_trim
        try:
            if self._draft_history_id and trimmed and base_trim and trimmed == base_trim:
                updated = history.mark_action_status(
                    self._draft_history_id,
                    status,
                    message,
                    row_count=row_count,
                    sql_text=sql_text,
                )
                if not updated:
                    history.log_action(
                        "insert_execute",
                        table or "",
                        row_count,
                        status,
                        message=message,
                        sql_text=sql_text,
                    )
            else:
                history.log_action(
                    "insert_execute",
                    table or "",
                    row_count,
                    status,
                    message=message,
                    sql_text=sql_text,
                )
        except Exception:
            pass
        finally:
            if status in {"success", "failed"}:
                self._draft_history_id = None

    def _show_loading(self, message: str):
        """Mở popup loading với thông điệp tương ứng."""
        if self._loader:
            return
        self._loader = LoadingPopup(self, message)

    def _hide_loading(self):
        """Đóng popup loading nếu đang hiển thị."""
        if not self._loader:
            return
        self._loader.close()
        self._loader = None

    def _handle_language_change(self, _lang: str) -> None:
        """Callback khi ngôn ngữ hệ thống thay đổi."""
        self._apply_language()

    def _apply_language(self) -> None:
        """Cập nhật toàn bộ text trên giao diện theo ngôn ngữ hiện tại."""
        self.title(self._t("insert.title"))
        if hasattr(self, "grp_search"):
            self.grp_search.config(text=self._t("insert.section.search"))
        if hasattr(self, "lbl_table_name"):
            self.lbl_table_name.config(text=self._t("insert.label.table_name"))
        if hasattr(self, "grp_actions"):
            self.grp_actions.config(text=self._t("insert.section.actions"))
        if hasattr(self, "btn_build_sql"):
            self.btn_build_sql.config(text=self._t("insert.btn.build_sql"))
        if hasattr(self, "btn_save_template"):
            self.btn_save_template.config(text=self._t("insert.btn.save_template"))
        if hasattr(self, "btn_select_template"):
            self.btn_select_template.config(text=self._t("insert.btn.select_template"))
        if hasattr(self, "btn_copy"):
            self.btn_copy.config(text=self._t("common.copy"))
        if hasattr(self, "btn_reorder"):
            self.btn_reorder.config(text=self._t("insert.btn.reorder"))
        if hasattr(self, "btn_execute"):
            self.btn_execute.config(text=self._t("insert.btn.execute"))
        if hasattr(self, "btn_clear"):
            self.btn_clear.config(text=self._t("insert.btn.clear"))
        if hasattr(self, "grp_connection"):
            self.grp_connection.config(text=self._t("insert.section.connection"))
        if hasattr(self, "lbl_user"):
            self.lbl_user.config(text=self._t("main.label.user_id"))
        if hasattr(self, "lbl_datasource"):
            self.lbl_datasource.config(text=self._t("main.label.data_source"))
        if hasattr(self, "lbl_hostport"):
            self.lbl_hostport.config(text=self._t("main.label.host_port"))
        if hasattr(self, "btn_import_csv"):
            self.btn_import_csv.config(text=self._t("insert.btn.import_csv"))
        if hasattr(self, "btn_export_csv"):
            self.btn_export_csv.config(text=self._t("insert.btn.export_csv"))
        if hasattr(self, "btn_add_row"):
            self.btn_add_row.config(text=self._t("insert.btn.add_row"))
        if hasattr(self, "frm_sql"):
            self.frm_sql.config(text=self._t("insert.section.sql", table=self._current_table_label))

    def _set_icon(self) -> None:
        """Áp dụng biểu tượng cho cửa sổ Insert nếu khả dụng."""
        try:
            self.iconbitmap("icons/logo.ico")
        except Exception:
            pass

    def _t(self, key: str, **kwargs) -> str:
        """Tra cứu chuỗi i18n."""
        return i18n.translate(key, **kwargs)


def open_insert_window(parent: tk.Widget, connection: Dict[str, str]):
    """Mở cửa sổ Insert."""
    InsertWindow(parent, connection)


def get_active_windows() -> List["InsertWindow"]:
    """Tra ve danh sach cua so Insert dang mo."""
    return [win for win in ACTIVE_WINDOWS if win.winfo_exists()]
