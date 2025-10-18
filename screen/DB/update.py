"""
Màn hình Update hỗ trợ xem và cập nhật dữ liệu.
"""
from __future__ import annotations

import re
import threading
import tkinter as tk
from tkinter import messagebox, ttk
from tkinter.scrolledtext import ScrolledText
from typing import Any, Dict, List, Optional

from screen.DB import db_utils
from screen.DB.widgets import ColumnOrderDialog, DataGrid, LoadingPopup
from screen.DB.template_dialog import TemplateLibraryDialog, TemplateSaveDialog
from core import history, i18n, templates

APP_TITLE_KEY = "common.app_title"

ACTIVE_WINDOWS: List["UpdateWindow"] = []


class UpdateWindow(tk.Toplevel):
    def __init__(self, parent: tk.Widget, connection: Dict[str, str]):
        """Khởi tạo cửa sổ Update với dữ liệu kết nối đã chọn."""
        super().__init__(parent)
        self.parent = parent
        self.conn_info = connection
        self.conn = None
        self.current_owner = connection.get("user", "").upper()
        self.title(self._t("update.title"))
        self.geometry("1180x760")
        self.minsize(960, 620)
        self.resizable(True, True)
        self._set_icon()

        self._table_items: List[Dict[str, str]] = []
        self._table_view: List[Dict[str, str]] = []
        self._active_table: Optional[Dict[str, str]] = None
        self._columns: List[str] = []
        self._column_meta: Dict[str, dict] = {}
        self._pk_columns: List[str] = []
        self._cached_rows: List[Dict[str, str]] = []
        self._draft_history_id: Optional[int] = None
        self._draft_history_sql: str = ""
        self._loader: Optional[LoadingPopup] = None
        self._current_table_label: str = "..."
        self._metadata_cache: Dict[str, Dict[str, Any]] = {}
        self._metadata_token: int = 0

        ACTIVE_WINDOWS.append(self)

        self._build_ui()
        self._set_controls_enabled(False)
        self._lang_listener = self._handle_language_change
        i18n.add_listener(self._lang_listener)
        self._apply_language()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(100, self._connect_async)

    # ------------------------------------------------------------------
    def _build_ui(self):
        """Xây dựng bố cục chính của màn hình Update."""
        self.frm_main = ttk.Frame(self, padding=8)
        self.frm_main.pack(fill="both", expand=True)
        self.frm_main.rowconfigure(1, weight=1)
        self.frm_main.columnconfigure(0, weight=1)

        self.frm_top = ttk.Frame(self.frm_main)
        self.frm_top.grid(row=0, column=0, sticky="ew")
        for idx in range(3):
            self.frm_top.columnconfigure(idx, weight=0)
        self.frm_top.columnconfigure(0, weight=1)

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
        self.btn_import_csv = ttk.Button(self.btn_bar, text=self._t("update.btn.import_csv"), command=self.grid.import_csv_dialog)
        self.btn_import_csv.pack(side="left", padx=4)
        self.btn_export_csv = ttk.Button(self.btn_bar, text=self._t("update.btn.export_csv"), command=self.grid.export_csv_dialog)
        self.btn_export_csv.pack(side="left", padx=4)
        self.btn_add_row = ttk.Button(self.btn_bar, text=self._t("update.btn.add_row"), command=lambda: self.grid.append_dict({}))
        self.btn_add_row.pack(side="left", padx=4)

        self.frm_condition = ttk.LabelFrame(
            self.frm_main,
            text=self._t("update.section.condition"),
            padding=6,
        )
        self.frm_condition.grid(row=2, column=0, sticky="ew", pady=(0, 6))
        self.frm_condition.columnconfigure(0, weight=1)
        self.txt_condition = ScrolledText(self.frm_condition, height=3, wrap="word")
        self.txt_condition.grid(row=0, column=0, sticky="ew")

        self.frm_sql = ttk.LabelFrame(
            self.frm_main,
            text=self._t("update.section.sql", table=self._current_table_label),
            padding=6,
        )
        self.frm_sql.grid(row=3, column=0, sticky="nsew")
        self.frm_sql.rowconfigure(0, weight=1)
        self.frm_sql.columnconfigure(0, weight=1)

        self.txt_sql = ScrolledText(self.frm_sql, height=8, wrap="word")
        self.txt_sql.grid(row=0, column=0, sticky="nsew")

    def _build_search(self, parent: ttk.Frame):
        """Tạo khu vực tìm kiếm danh sách bảng."""
        self.grp_search = ttk.LabelFrame(parent, text=self._t("update.section.search"), padding=6)
        self.grp_search.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.grp_search.columnconfigure(0, weight=1)

        self.lbl_table_name = ttk.Label(self.grp_search, text=self._t("update.label.table_name"))
        self.lbl_table_name.grid(row=0, column=0, sticky="w")

        self.var_search = tk.StringVar()
        self.ent_search = ttk.Entry(self.grp_search, textvariable=self.var_search)
        self.ent_search.grid(row=1, column=0, sticky="ew", pady=4)
        self.ent_search.bind("<KeyRelease>", lambda _event: self._filter_tables())

        self.list_tables = tk.Listbox(self.grp_search, height=10)
        self.list_tables.grid(row=2, column=0, sticky="nsew", pady=(0, 4))
        self.list_tables.bind("<<ListboxSelect>>", lambda _event: self._on_select_table())
        self.grp_search.rowconfigure(2, weight=1)

    def _build_actions(self, parent: ttk.Frame):
        """Khoi tao cac nut thao tac chinh."""
        self.grp_actions = ttk.LabelFrame(parent, text=self._t("update.section.actions"), padding=6)
        self.grp_actions.grid(row=0, column=1, sticky="n", padx=(0, 8))

        self.btn_build_sql = ttk.Button(self.grp_actions, text=self._t("update.btn.build_sql"), command=self._generate_sql)
        self.btn_build_sql.grid(row=0, column=0, sticky="ew", pady=4)

        self.btn_save_template = ttk.Button(self.grp_actions, text=self._t("update.btn.save_template"), command=self._save_template)
        self.btn_save_template.grid(row=1, column=0, sticky="ew", pady=4)

        self.btn_select_template = ttk.Button(self.grp_actions, text=self._t("update.btn.select_template"), command=self._open_template_library)
        self.btn_select_template.grid(row=2, column=0, sticky="ew", pady=4)

        self.btn_copy = ttk.Button(self.grp_actions, text=self._t("common.copy"), command=self._copy_sql)
        self.btn_copy.grid(row=3, column=0, sticky="ew", pady=4)

        self.btn_reorder = ttk.Button(self.grp_actions, text=self._t("update.btn.reorder"), command=self._change_column_order)
        self.btn_reorder.grid(row=4, column=0, sticky="ew", pady=4)

        self.btn_execute = ttk.Button(self.grp_actions, text=self._t("update.btn.execute"), command=self._execute)
        self.btn_execute.grid(row=5, column=0, sticky="ew", pady=4)

        self.btn_clear = ttk.Button(self.grp_actions, text=self._t("update.btn.clear"), command=self._clear)
        self.btn_clear.grid(row=6, column=0, sticky="ew", pady=4)


    def _build_connection(self, parent: ttk.Frame):
        """Hiển thị thông tin kết nối đang sử dụng."""
        self.grp_connection = ttk.LabelFrame(parent, text=self._t("update.section.connection"), padding=6, width=240)
        self.grp_connection.grid(row=0, column=2, sticky="n")

        self.lbl_conn_user = ttk.Label(self.grp_connection, text=self._t("main.label.user_id"))
        self.lbl_conn_user.grid(row=0, column=0, sticky="w", pady=2)
        self.ent_conn_user = ttk.Entry(self.grp_connection)
        self.ent_conn_user.insert(0, self.conn_info.get("user", ""))
        self.ent_conn_user.configure(state="readonly")
        self.ent_conn_user.grid(row=0, column=1, sticky="ew", pady=2, padx=(6, 0))

        self.lbl_conn_alias = ttk.Label(self.grp_connection, text=self._t("main.label.data_source"))
        self.lbl_conn_alias.grid(row=1, column=0, sticky="w", pady=2)
        self.ent_conn_alias = ttk.Entry(self.grp_connection)
        self.ent_conn_alias.insert(0, self.conn_info.get("alias", ""))
        self.ent_conn_alias.configure(state="readonly")
        self.ent_conn_alias.grid(row=1, column=1, sticky="ew", pady=2, padx=(6, 0))

        self.lbl_conn_host = ttk.Label(self.grp_connection, text=self._t("update.label.host"))
        self.lbl_conn_host.grid(row=2, column=0, sticky="w", pady=2)
        self.ent_conn_host = ttk.Entry(self.grp_connection)
        self.ent_conn_host.insert(0, self.conn_info.get("host", ""))
        self.ent_conn_host.configure(state="readonly")
        self.ent_conn_host.grid(row=2, column=1, sticky="ew", pady=2, padx=(6, 0))

        self.lbl_conn_port = ttk.Label(self.grp_connection, text=self._t("update.label.port"))
        self.lbl_conn_port.grid(row=3, column=0, sticky="w", pady=2)
        self.ent_conn_port = ttk.Entry(self.grp_connection)
        self.ent_conn_port.insert(0, self.conn_info.get("port", ""))
        self.ent_conn_port.configure(state="readonly")
        self.ent_conn_port.grid(row=3, column=1, sticky="ew", pady=2, padx=(6, 0))

        self.grp_connection.columnconfigure(1, weight=1)

    # ------------------------------------------------------------------
    def _connect_async(self):
        """Kết nối cơ sở dữ liệu ở luồng nền và tải danh sách bảng."""
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
        """Hiển thị lỗi và đóng cửa sổ khi không thể khởi tạo."""
        self._hide_loading()
        messagebox.showerror(self._t(APP_TITLE_KEY), msg, parent=self)
        self.destroy()

    def _init_tables(self, tables: List[str]):
        """Tải danh sách bảng truy cập được vào listbox."""
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
            self._columns = []
            self._column_meta.clear()
            self._pk_columns = []
            self.grid.clear()
            self.grid.configure_columns([])
            self.txt_sql.delete("1.0", tk.END)
            self.txt_condition.delete("1.0", tk.END)
            self._current_table_label = "..."
            self._set_sql_label("...")
            self._set_controls_enabled(False)

    # ------------------------------------------------------------------
    def _filter_tables(self):
        """Lọc danh sách bảng theo từ khóa đang nhập."""
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
            self._columns = []
            self._column_meta.clear()
            self._pk_columns = []
            self.grid.clear()
            self.grid.configure_columns([])
            self.txt_sql.delete("1.0", tk.END)
            self.txt_condition.delete("1.0", tk.END)
            self._current_table_label = "..."
            self._set_sql_label("...")
            self._set_controls_enabled(False)

    def _on_select_table(self, _event=None):
        """Xử lý khi chọn bảng mới trong danh sách."""
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
        """Nạp thông tin cột và khóa chính của bảng đang chọn (có cache & popup)."""
        if not self.conn:
            return
        table_key = item["full"]
        self._columns = []
        self._column_meta.clear()
        self._pk_columns = []
        self._cached_rows.clear()
        self.grid.clear()
        self.grid.configure_columns([])
        self.txt_sql.delete("1.0", tk.END)
        self.txt_condition.delete("1.0", tk.END)
        self._set_sql_label(item["display"])
        self._set_controls_enabled(False)

        cached = self._metadata_cache.get(table_key)
        if cached:
            self._metadata_token += 1
            token = self._metadata_token
            self._hide_loading()
            self._apply_table_metadata(item, cached["columns"], cached["pk"], token)
            return

        self._metadata_token += 1
        token = self._metadata_token
        self._hide_loading()
        self._show_loading(self._t("common.loading_columns", table=item["display"]))

        def worker():
            try:
                columns = db_utils.fetch_table_columns(self.conn, table_key, self.current_owner)
                pk_cols = db_utils.fetch_primary_keys(self.conn, table_key, self.current_owner)
            except Exception as exc:
                self.after(0, lambda: self._handle_metadata_error(item, exc, token))
                return
            self._metadata_cache[table_key] = {"columns": columns, "pk": pk_cols}
            self.after(0, lambda: self._apply_table_metadata(item, columns, pk_cols, token))

        threading.Thread(target=worker, daemon=True).start()

    def _apply_table_metadata(
        self,
        item: Dict[str, str],
        columns: List[Dict[str, Any]],
        pk_cols: List[str],
        token: Optional[int] = None,
    ):
        """Áp dụng metadata đã tải vào lưới."""
        if token is not None and token != self._metadata_token:
            return
        if not self._active_table or self._active_table["full"] != item["full"]:
            return
        self._hide_loading()
        self._columns = [col["column_name"] for col in columns]
        self._column_meta = {col["column_name"]: col for col in columns}
        self._pk_columns = pk_cols
        if self._columns:
            self.grid.configure_columns(self._columns)
        self.grid.clear()
        if self._columns:
            self.grid.append_dict({})
        self._cached_rows.clear()
        self._set_sql_label(item["display"])
        self._set_controls_enabled(True)

    def _handle_metadata_error(self, item: Dict[str, str], exc: Exception, token: Optional[int]):
        """Xử lý khi tải metadata xảy ra lỗi."""
        if token is not None and token != self._metadata_token:
            return
        if not self._active_table or self._active_table["full"] != item["full"]:
            return
        self._hide_loading()
        self._set_controls_enabled(True)
        self._set_sql_label("...")
        self._columns = []
        self._column_meta.clear()
        self._pk_columns = []
        self._cached_rows.clear()
        messagebox.showerror(
            self._t(APP_TITLE_KEY),
            self._t("update.msg.metadata_error", error=str(exc)),
            parent=self,
        )

    def _set_sql_label(self, table_display: str):
        """Cập nhật tiêu đề khung SQL theo tên bảng hiện tại."""
        self._current_table_label = table_display or "..."
        if hasattr(self, "frm_sql"):
            self.frm_sql.configure(text=self._t("update.section.sql", table=self._current_table_label))

    def _set_controls_enabled(self, enabled: bool):
        """Bật/tắt nhóm nút thao tác phụ thuộc metadata."""
        state = "normal" if enabled else "disabled"
        buttons = [
            getattr(self, "btn_build_sql", None),
            getattr(self, "btn_save_template", None),
            getattr(self, "btn_select_template", None),
            getattr(self, "btn_copy", None),
            getattr(self, "btn_reorder", None),
            getattr(self, "btn_execute", None),
            getattr(self, "btn_clear", None),
            getattr(self, "btn_import_csv", None),
            getattr(self, "btn_export_csv", None),
            getattr(self, "btn_add_row", None),
        ]
        for widget in buttons:
            if widget is None:
                continue
            try:
                widget.config(state=state)
            except tk.TclError:
                continue
        try:
            self.grid.tree.configure(state="normal" if enabled else "disabled")
        except tk.TclError:
            pass

    # ------------------------------------------------------------------
    def _generate_sql(self):
        """Sinh câu lệnh UPDATE dựa trên dữ liệu trong lưới."""
        rows = self.grid.get_all()
        if not rows:
            messagebox.showwarning(self._t(APP_TITLE_KEY), self._t("update.msg.no_data_generate"), parent=self)
            return
        if not self._columns:
            messagebox.showwarning(self._t(APP_TITLE_KEY), self._t("update.msg.no_table"), parent=self)
            return
        table = self._current_table()
        if not table:
            messagebox.showwarning(self._t(APP_TITLE_KEY), self._t("update.msg.no_table"), parent=self)
            return
        set_columns = [col for col in self._columns if col not in self._pk_columns]
        if not set_columns:
            messagebox.showwarning(self._t(APP_TITLE_KEY), self._t("update.msg.no_columns_update"), parent=self)
            return
        condition_template = self._condition_template()
        owner, table_name = self._split_table(table)
        sql_lines: List[str] = []
        for row in rows:
            set_parts = []
            for col in set_columns:
                meta = self._column_meta.get(col, {})
                literal = db_utils.format_sql_literal(row.get(col), meta)
                set_parts.append(f"{col} = {literal}")
            where_parts = []
            for pk in self._pk_columns:
                meta = self._column_meta.get(pk, {})
                literal = db_utils.format_sql_literal(row.get(pk), meta)
                where_parts.append(f"{pk} = {literal}")
            extra = self._render_condition(condition_template, row)
            sql = f"UPDATE {owner}.{table_name} SET " + ", ".join(set_parts)
            if where_parts:
                sql += " WHERE " + " AND ".join(where_parts)
                if extra:
                    sql += " AND (" + extra + ")"
            elif extra:
                sql += " WHERE " + extra
            sql_lines.append(sql + ";")
        sql_text = "\n".join(sql_lines)
        self.txt_sql.delete("1.0", tk.END)
        self.txt_sql.insert(tk.END, sql_text)
        self._record_history_draft(table, sql_text, len(rows))

    def _record_history_draft(self, table: str, sql_text: str, row_count: int) -> None:
        """Ghi log du thao SQL update."""
        trimmed = (sql_text or "").strip()
        self._draft_history_sql = trimmed
        if not trimmed:
            self._draft_history_id = None
            return
        try:
            action_id = history.log_action(
                "update_sql",
                table or "",
                row_count,
                "draft",
                message=(f"Draft update for {table}" if table else "Draft update SQL"),
                sql_text=trimmed,
            )
            self._draft_history_id = action_id
        except Exception:
            self._draft_history_id = None

    def _copy_sql(self):
        """Copy câu SQL đang hiển thị vào clipboard."""
        data = self.txt_sql.get("1.0", tk.END).strip()
        if not data:
            return
        self.clipboard_clear()
        self.clipboard_append(data)
        messagebox.showinfo(self._t(APP_TITLE_KEY), self._t("update.msg.copy_done"), parent=self)

    def _save_template(self):
        """Luu cau SQL update hien tai vao thu vien template."""
        sql_text = self.txt_sql.get("1.0", tk.END).strip()
        if not sql_text:
            messagebox.showwarning(self._t(APP_TITLE_KEY), self._t("template.save.message_no_sql"), parent=self)
            return
        default_name = self._current_table() or self._current_table_label or "UPDATE_SQL"
        dlg = TemplateSaveDialog(self, default_type="update", default_name=default_name)
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
        """Mo thu vien template update."""
        dlg = TemplateLibraryDialog(self, template_type="update")
        self.wait_window(dlg)
        record = getattr(dlg, "result", None)
        if record and record.get("content"):
            self.set_sql_text(record["content"])

    def set_sql_text(self, sql_text: str) -> None:
        """Cap nhat noi dung SQL va dua cua so len truoc."""
        self.txt_sql.delete("1.0", tk.END)
        self.txt_sql.insert(tk.END, sql_text)
        self._draft_history_sql = (sql_text or "").strip()
        self._draft_history_id = None
        self.lift()
        self.focus_force()

    def _change_column_order(self):
        """Thay đổi thứ tự cột hiển thị trên lưới."""
        if not self._columns:
            messagebox.showwarning(self._t(APP_TITLE_KEY), self._t("update.msg.no_columns_update"), parent=self)
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

    def _clear(self):
        """Xóa dữ liệu trên lưới và vùng SQL."""
        if not messagebox.askyesno(self._t(APP_TITLE_KEY), self._t("update.msg.clear_confirm"), parent=self):
            return
        self.grid.clear()
        self.grid.append_dict({})
        self.txt_sql.delete("1.0", tk.END)
        self.txt_condition.delete("1.0", tk.END)
        self._cached_rows.clear()
        self._draft_history_id = None
        self._draft_history_sql = ""

    def _execute(self):
        """Thuc thi cau UPDATE truoc tiep len co so du lieu."""
        table = self._current_table()
        if not table:
            messagebox.showwarning(self._t(APP_TITLE_KEY), self._t("update.msg.no_table"), parent=self)
            return
        rows = self.grid.get_all()
        if not rows:
            messagebox.showwarning(self._t(APP_TITLE_KEY), self._t("update.msg.no_data_execute"), parent=self)
            return
        if not self.conn:
            msg = self._t("update.msg.not_connected")
            self._log_history_status("failed", msg, len(rows), self.txt_sql.get("1.0", tk.END).strip(), table)
            messagebox.showerror(self._t(APP_TITLE_KEY), msg, parent=self)
            return
        if not messagebox.askyesno(self._t(APP_TITLE_KEY), self._t("update.msg.confirm_execute"), parent=self):
            return
        set_columns = [col for col in self._columns if col not in self._pk_columns]
        if not set_columns:
            messagebox.showwarning(self._t(APP_TITLE_KEY), self._t("update.msg.no_columns_update"), parent=self)
            return
        row_count = len(rows)
        sql_text_trim = (self.txt_sql.get("1.0", tk.END) or "").strip()
        condition_template = self._condition_template()
        owner, table_name = self._split_table(table)

        try:
            cur = self.conn.cursor()
        except Exception as exc:
            msg = self._t("update.msg.cursor_error", error=str(exc))
            self._log_history_status("failed", msg, row_count, sql_text_trim, table)
            messagebox.showerror(self._t(APP_TITLE_KEY), msg, parent=self)
            return

        try:
            for row in rows:
                set_clause = ", ".join(f"{col} = :{col}" for col in set_columns)
                if not self._pk_columns and not condition_template:
                    raise ValueError(self._t("update.msg.where_missing_no_pk"))
                where_parts = []
                binds = {}
                for col in set_columns:
                    binds[col] = self._convert_value(row.get(col), self._column_meta.get(col))
                for pk in self._pk_columns:
                    value = row.get(pk)
                    if value in (None, ""):
                        raise ValueError(self._t("update.msg.pk_missing", column=pk))
                    binds[f"PK_{pk}"] = self._convert_value(value, self._column_meta.get(pk))
                    where_parts.append(f"{pk} = :PK_{pk}")
                extra = self._render_condition(condition_template, row)
                sql = f"UPDATE {owner}.{table_name} SET {set_clause}"
                if where_parts:
                    sql += " WHERE " + " AND ".join(where_parts)
                    if extra:
                        sql += " AND (" + extra + ")"
                else:
                    if not extra:
                        raise ValueError(self._t("update.msg.where_missing"))
                    sql += " WHERE " + extra
                cur.execute(sql, binds)
            self.conn.commit()
        except Exception as exc:
            self.conn.rollback()
            msg = self._t("update.msg.update_error", error=str(exc))
            self._log_history_status("failed", msg, row_count, sql_text_trim, table)
            messagebox.showerror(self._t(APP_TITLE_KEY), msg, parent=self)
            return
        finally:
            try:
                cur.close()
            except Exception:
                pass
        self._log_history_status("success", self._t("update.msg.update_success"), row_count, sql_text_trim, table)
        messagebox.showinfo(self._t(APP_TITLE_KEY), self._t("update.msg.update_success"), parent=self)

    def _condition_template(self) -> str:
        """Lấy mẫu điều kiện bổ sung người dùng nhập vào."""
        return self.txt_condition.get("1.0", tk.END).strip()

    def _render_condition(self, template: str, row: Dict[str, str]) -> str:
        """Thay thế placeholder trong điều kiện bổ sung bằng giá trị thực tế."""
        if not template:
            return ""

        def repl(match):
            col = match.group(1).strip().upper()
            meta = self._column_meta.get(col, {})
            return db_utils.format_sql_literal(row.get(col), meta)

        pattern = re.compile(r"\{\{([A-Za-z0-9_]+)\}\}")
        rendered = pattern.sub(repl, template)
        return rendered

    def _convert_value(self, value, meta):
        """Chuyển đổi giá trị theo metadata để bind tham số chính xác."""
        if value in (None, ""):
            return None
        data_type = (meta or {}).get("data_type", "").upper() if meta else ""
        if data_type in db_utils.NUMERIC_TYPES:
            try:
                return float(value) if "." in str(value) else int(value)
            except Exception:
                return value
        return value

    # ------------------------------------------------------------------
    def _split_table(self, raw: str) -> tuple[str, str]:
        """Tách owner và tên bảng, mặc định owner hiện tại nếu thiếu."""
        return db_utils.split_owner_table(raw, self.current_owner)

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

    def _log_history_status(self, status: str, message: str, row_count: int, sql_text: str, table: Optional[str]) -> None:
        """Cap nhat lich su update voi trang thai chon."""
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
                        "update_execute",
                        table or "",
                        row_count,
                        status,
                        message=message,
                        sql_text=sql_text,
                    )
            else:
                history.log_action(
                    "update_execute",
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
        """Hiển thị popup tiến trình với thông điệp nhất định."""
        if self._loader:
            return
        self._loader = LoadingPopup(self, message)

    def _hide_loading(self):
        """Đóng popup tiến trình khi hoàn tất."""
        if not self._loader:
            return
        self._loader.close()
        self._loader = None

    def destroy(self):
        """Hủy cửa sổ và gỡ listener ngôn ngữ."""
        if hasattr(self, "_lang_listener"):
            i18n.remove_listener(self._lang_listener)
        super().destroy()

    def _handle_language_change(self, _lang: str) -> None:
        """Cập nhật giao diện khi đổi ngôn ngữ."""
        self._apply_language()

    def _apply_language(self) -> None:
        """Áp dụng chuỗi đa ngôn ngữ cho toàn bộ widget."""
        self.title(self._t("update.title"))
        if hasattr(self, "grp_search"):
            self.grp_search.configure(text=self._t("update.section.search"))
        if hasattr(self, "lbl_table_name"):
            self.lbl_table_name.configure(text=self._t("update.label.table_name"))
        if hasattr(self, "grp_actions"):
            self.grp_actions.configure(text=self._t("update.section.actions"))
        if hasattr(self, "btn_build_sql"):
            self.btn_build_sql.configure(text=self._t("update.btn.build_sql"))
        if hasattr(self, "btn_save_template"):
            self.btn_save_template.configure(text=self._t("update.btn.save_template"))
        if hasattr(self, "btn_select_template"):
            self.btn_select_template.configure(text=self._t("update.btn.select_template"))
        if hasattr(self, "btn_copy"):
            self.btn_copy.configure(text=self._t("common.copy"))
        if hasattr(self, "btn_reorder"):
            self.btn_reorder.configure(text=self._t("update.btn.reorder"))
        if hasattr(self, "btn_execute"):
            self.btn_execute.configure(text=self._t("update.btn.execute"))
        if hasattr(self, "btn_clear"):
            self.btn_clear.configure(text=self._t("update.btn.clear"))
        if hasattr(self, "btn_import_csv"):
            self.btn_import_csv.configure(text=self._t("update.btn.import_csv"))
        if hasattr(self, "btn_export_csv"):
            self.btn_export_csv.configure(text=self._t("update.btn.export_csv"))
        if hasattr(self, "btn_add_row"):
            self.btn_add_row.configure(text=self._t("update.btn.add_row"))
        if hasattr(self, "grp_connection"):
            self.grp_connection.configure(text=self._t("update.section.connection"))
        if hasattr(self, "lbl_conn_user"):
            self.lbl_conn_user.configure(text=self._t("main.label.user_id"))
        if hasattr(self, "lbl_conn_alias"):
            self.lbl_conn_alias.configure(text=self._t("main.label.data_source"))
        if hasattr(self, "lbl_conn_host"):
            self.lbl_conn_host.configure(text=self._t("update.label.host"))
        if hasattr(self, "lbl_conn_port"):
            self.lbl_conn_port.configure(text=self._t("update.label.port"))
        if hasattr(self, "frm_condition"):
            self.frm_condition.configure(text=self._t("update.section.condition"))
        if hasattr(self, "frm_sql"):
            self.frm_sql.configure(text=self._t("update.section.sql", table=self._current_table_label))
        if hasattr(self, "grid"):
            self.grid.apply_language()

    def _t(self, key: str, **kwargs) -> str:
        """Truy xuất chuỗi theo ngôn ngữ hiện tại."""
        return i18n.translate(key, **kwargs)

    def _set_icon(self) -> None:
        """Áp dụng biểu tượng ứng dụng nếu có."""
        try:
            self.iconbitmap("icons/logo.ico")
        except Exception:
            pass


def open_update_window(parent: tk.Widget, connection: Dict[str, str]):
    """Mở cửa sổ Update."""
    UpdateWindow(parent, connection)


def get_active_windows() -> List["UpdateWindow"]:
    """Tra ve danh sach cua so Update dang mo."""
    return [win for win in ACTIVE_WINDOWS if win.winfo_exists()]
