"""
Update screen implementation.
"""
from __future__ import annotations

import re
import threading
import tkinter as tk
from tkinter import messagebox, ttk
from tkinter.scrolledtext import ScrolledText
from typing import Dict, List, Optional

from screen.DB import db_utils
from screen.DB.widgets import ColumnOrderDialog, DataGrid


class UpdateWindow(tk.Toplevel):
    def __init__(self, parent: tk.Widget, connection: Dict[str, str]):
        super().__init__(parent)
        self.parent = parent
        self.conn_info = connection
        self.conn = None
        self.current_owner = connection.get("user", "").upper()
        self.title("Update")
        self.geometry("1180x760")
        self.minsize(960, 620)
        self.resizable(True, True)

        self._tables_all: List[str] = []
        self._columns: List[str] = []
        self._column_meta: Dict[str, dict] = {}
        self._pk_columns: List[str] = []
        self._cached_rows: List[Dict[str, str]] = []

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(100, self._connect_async)

    # ------------------------------------------------------------------
    def _build_ui(self):
        main = ttk.Frame(self, padding=8)
        main.pack(fill="both", expand=True)
        main.rowconfigure(1, weight=1)
        main.columnconfigure(0, weight=1)

        top = ttk.Frame(main)
        top.grid(row=0, column=0, sticky="ew")
        for idx in range(3):
            top.columnconfigure(idx, weight=0)
        top.columnconfigure(0, weight=1)

        self._build_search(top)
        self._build_actions(top)
        self._build_connection(top)

        middle = ttk.Frame(main)
        middle.grid(row=1, column=0, sticky="nsew", pady=(8, 6))
        middle.rowconfigure(0, weight=1)
        middle.columnconfigure(0, weight=1)

        self.grid = DataGrid(middle)
        self.grid.grid(row=0, column=0, sticky="nsew")

        btn_bar = ttk.Frame(middle)
        btn_bar.grid(row=1, column=0, sticky="e", pady=(6, 0))
        ttk.Button(btn_bar, text="Import CSV", command=self.grid.import_csv_dialog).pack(side="left", padx=4)
        ttk.Button(btn_bar, text="Export CSV", command=self.grid.export_csv_dialog).pack(side="left", padx=4)
        ttk.Button(btn_bar, text="Thêm dòng trống", command=lambda: self.grid.append_dict({})).pack(side="left", padx=4)

        cond_frame = ttk.LabelFrame(main, text="Điều kiện UPDATE bổ sung (dùng {{COLUMN}} để lấy giá trị dòng)", padding=6)
        cond_frame.grid(row=2, column=0, sticky="ew", pady=(0, 6))
        cond_frame.columnconfigure(0, weight=1)
        self.txt_condition = ScrolledText(cond_frame, height=3, wrap="word")
        self.txt_condition.grid(row=0, column=0, sticky="ew")

        bottom = ttk.LabelFrame(main, text="Update ...", padding=6)
        bottom.grid(row=3, column=0, sticky="nsew")
        bottom.rowconfigure(0, weight=1)
        bottom.columnconfigure(0, weight=1)

        self.txt_sql = ScrolledText(bottom, height=8, wrap="word")
        self.txt_sql.grid(row=0, column=0, sticky="nsew")

    def _build_search(self, parent: ttk.Frame):
        grp = ttk.LabelFrame(parent, text="Tìm kiếm", padding=6)
        grp.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        grp.columnconfigure(0, weight=1)
        ttk.Label(grp, text="Table Name").grid(row=0, column=0, sticky="w")
        self.var_search = tk.StringVar()
        ent = ttk.Entry(grp, textvariable=self.var_search)
        ent.grid(row=1, column=0, sticky="ew", pady=4)
        ent.bind("<KeyRelease>", lambda e: self._filter_tables())
        self.list_tables = tk.Listbox(grp, height=10)
        self.list_tables.grid(row=2, column=0, sticky="nsew", pady=(0, 4))
        self.list_tables.bind("<<ListboxSelect>>", lambda e: self._on_select_table())
        grp.rowconfigure(2, weight=1)

    def _build_actions(self, parent: ttk.Frame):
        grp = ttk.LabelFrame(parent, text="Chức năng", padding=6)
        grp.grid(row=0, column=1, sticky="n", padx=(0, 8))
        ttk.Button(grp, text="Tạo câu Update", command=self._generate_sql).grid(row=0, column=0, sticky="ew", pady=4)
        ttk.Button(grp, text="Copy", command=self._copy_sql).grid(row=1, column=0, sticky="ew", pady=4)
        ttk.Button(grp, text="Thay đổi vị trí cột", command=self._change_column_order).grid(row=2, column=0, sticky="ew", pady=4)
        ttk.Button(grp, text="Thực thi", command=self._execute).grid(row=3, column=0, sticky="ew", pady=4)
        ttk.Button(grp, text="Clear", command=self._clear).grid(row=4, column=0, sticky="ew", pady=4)

    def _build_connection(self, parent: ttk.Frame):
        grp = ttk.LabelFrame(parent, text="Thông Tin Kết Nối", padding=6, width=240)
        grp.grid(row=0, column=2, sticky="n")
        labels = {
            "User ID": self.conn_info.get("user", ""),
            "Data Source": self.conn_info.get("alias", ""),
            "Host": self.conn_info.get("host", ""),
            "Port": self.conn_info.get("port", ""),
        }
        for idx, (label, value) in enumerate(labels.items()):
            ttk.Label(grp, text=label).grid(row=idx, column=0, sticky="w", pady=2)
            ent = ttk.Entry(grp)
            ent.insert(0, value)
            ent.configure(state="readonly")
            ent.grid(row=idx, column=1, sticky="ew", pady=2, padx=(6, 0))
        grp.columnconfigure(1, weight=1)

    # ------------------------------------------------------------------
    def _connect_async(self):
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
                msg = f"Lỗi kết nối: {exc}"
                self.after(0, lambda m=msg: self._show_error(m))
                return
            self.after(0, lambda: self._init_tables(tables))

        threading.Thread(target=worker, daemon=True).start()

    def _show_error(self, msg: str):
        messagebox.showerror("Tool VIP", msg, parent=self)
        self.destroy()

    def _init_tables(self, tables: List[str]):
        self._tables_all = tables
        self.list_tables.delete(0, tk.END)
        for tbl in tables:
            self.list_tables.insert(tk.END, tbl)
        if tables:
            self.list_tables.selection_set(0)
            self._on_select_table()

    # ------------------------------------------------------------------
    def _filter_tables(self):
        keyword = self.var_search.get().strip().upper()
        self.list_tables.delete(0, tk.END)
        for tbl in self._tables_all:
            if not keyword or keyword in tbl.upper():
                self.list_tables.insert(tk.END, tbl)

    def _on_select_table(self):
        selection = self.list_tables.curselection()
        if not selection:
            return
        index = selection[0]
        table = self.list_tables.get(index)
        if not table:
            return
        self._load_table_metadata(table)

    def _load_table_metadata(self, table: str):
        if not self.conn:
            return
        try:
            columns = db_utils.fetch_table_columns(self.conn, table, self.current_owner)
            pk_cols = db_utils.fetch_primary_keys(self.conn, table, self.current_owner)
        except Exception as exc:
            messagebox.showerror("Tool VIP", f"Lỗi đọc metadata: {exc}", parent=self)
            return
        self._columns = [col["column_name"] for col in columns]
        self._column_meta = {col["column_name"]: col for col in columns}
        self._pk_columns = pk_cols
        self.grid.configure_columns(self._columns)
        self.grid.clear()
        self.grid.append_dict({})
        self._cached_rows.clear()
        self._set_sql_label(table)

    def _set_sql_label(self, table: str):
        frame: ttk.LabelFrame = self.txt_sql.master  # type: ignore[assignment]
        frame.configure(text=f"Update {table}")

    # ------------------------------------------------------------------
    def _generate_sql(self):
        rows = self.grid.get_all()
        if not rows:
            messagebox.showwarning("Tool VIP", "Không có dữ liệu để tạo update.", parent=self)
            return
        if not self._columns:
            messagebox.showwarning("Tool VIP", "Chưa chọn bảng.", parent=self)
            return
        table = self._current_table()
        if not table:
            messagebox.showwarning("Tool VIP", "Chưa chọn bảng.", parent=self)
            return
        set_columns = [col for col in self._columns if col not in self._pk_columns]
        if not set_columns:
            messagebox.showwarning("Tool VIP", "Bảng không có cột nào để update (chỉ gồm khóa chính).", parent=self)
            return
        condition_template = self._condition_template()

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
                if literal == "NULL":
                    messagebox.showwarning("Tool VIP", f"Khóa chính {pk} bị trống.", parent=self)
                    return
                where_parts.append(f"{pk} = {literal}")
            extra = self._render_condition(condition_template, row)
            if extra:
                where_parts.append(extra)
            if not where_parts:
                messagebox.showwarning("Tool VIP", "Thiếu điều kiện WHERE.", parent=self)
                return
            sql_lines.append(f"UPDATE {table} SET {', '.join(set_parts)} WHERE {' AND '.join(where_parts)};")
        self.txt_sql.delete("1.0", tk.END)
        self.txt_sql.insert(tk.END, "\n".join(sql_lines))
        self._cached_rows = rows

    def _copy_sql(self):
        data = self.txt_sql.get("1.0", tk.END).strip()
        if not data:
            return
        self.clipboard_clear()
        self.clipboard_append(data)
        messagebox.showinfo("Tool VIP", "Đã copy câu update.", parent=self)

    def _change_column_order(self):
        if not self._columns:
            messagebox.showwarning("Tool VIP", "Chưa có cột để thay đổi.", parent=self)
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
            self._cached_rows = current_rows

    def _clear(self):
        if not messagebox.askyesno("Tool VIP", "Bạn có muốn reset dữ liệu không?", parent=self):
            return
        self.grid.clear()
        self.grid.append_dict({})
        self.txt_sql.delete("1.0", tk.END)
        self.txt_condition.delete("1.0", tk.END)
        self._cached_rows.clear()

    def _execute(self):
        table = self._current_table()
        if not table:
            messagebox.showwarning("Tool VIP", "Chưa chọn bảng.", parent=self)
            return
        rows = self.grid.get_all()
        if not rows:
            messagebox.showwarning("Tool VIP", "Không có dữ liệu để update.", parent=self)
            return
        if not self.conn:
            messagebox.showerror("Tool VIP", "Chưa kết nối database.", parent=self)
            return
        if not messagebox.askyesno("Tool VIP", "Thực thi update?", parent=self):
            return
        set_columns = [col for col in self._columns if col not in self._pk_columns]
        if not set_columns:
            messagebox.showwarning("Tool VIP", "Không có cột nào để update.", parent=self)
            return
        condition_template = self._condition_template()
        owner, table_name = self._split_table(table)

        try:
            cur = self.conn.cursor()
        except Exception as exc:
            messagebox.showerror("Tool VIP", f"Lỗi cursor: {exc}", parent=self)
            return

        try:
            for row in rows:
                set_clause = ", ".join(f"{col} = :{col}" for col in set_columns)
                if not self._pk_columns and not condition_template:
                    raise ValueError("Thiếu điều kiện WHERE. Bảng không có khóa chính, cần nhập điều kiện.")
                where_parts = []
                binds = {}
                for col in set_columns:
                    binds[col] = self._convert_value(row.get(col), self._column_meta.get(col))
                for pk in self._pk_columns:
                    value = row.get(pk)
                    if value in (None, ""):
                        raise ValueError(f"Khóa chính {pk} bị trống.")
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
                        raise ValueError("Thiếu điều kiện WHERE.")
                    sql += " WHERE " + extra
                cur.execute(sql, binds)
            self.conn.commit()
        except Exception as exc:
            self.conn.rollback()
            messagebox.showerror("Tool VIP", f"Lỗi update: {exc}", parent=self)
            return
        finally:
            try:
                cur.close()
            except Exception:
                pass
        messagebox.showinfo("Tool VIP", "Update thành công.", parent=self)

    # ------------------------------------------------------------------
    def _condition_template(self) -> str:
        return self.txt_condition.get("1.0", tk.END).strip()

    def _render_condition(self, template: str, row: Dict[str, str]) -> str:
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
        if "." in raw:
            owner, name = raw.split(".", 1)
            return owner.strip().upper(), name.strip().upper()
        return self.current_owner.upper(), raw.strip().upper()

    def _current_table(self) -> Optional[str]:
        selection = self.list_tables.curselection()
        if not selection:
            return None
        return self.list_tables.get(selection[0])

    def _on_close(self):
        try:
            if self.conn:
                self.conn.close()
        except Exception:
            pass
        self.destroy()


def open_update_window(parent: tk.Widget, connection: Dict[str, str]):
    UpdateWindow(parent, connection)
