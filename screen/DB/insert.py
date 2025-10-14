"""
Insert screen implementation.
"""
from __future__ import annotations

import threading
import tkinter as tk
from tkinter import messagebox, ttk
from tkinter.scrolledtext import ScrolledText
from typing import Dict, List, Optional

from screen.DB import db_utils
from screen.DB.widgets import ColumnOrderDialog, DataGrid, DuplicatePreviewDialog


class InsertWindow(tk.Toplevel):
    def __init__(self, parent: tk.Widget, connection: Dict[str, str]):
        super().__init__(parent)
        self.parent = parent
        self.conn_info = connection
        self.conn = None
        self.current_owner = connection.get("user", "").upper()
        self.title("Insert")
        self.geometry("1180x720")
        self.minsize(960, 600)
        self.resizable(True, True)

        self._tables_all: List[str] = []
        self._columns: List[str] = []
        self._column_meta: Dict[str, dict] = {}
        self._pk_columns: List[str] = []
        self._generated_rows: List[Dict[str, str]] = []

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
        top.columnconfigure(0, weight=1)
        top.columnconfigure(1, weight=0)
        top.columnconfigure(2, weight=0)

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

        bottom = ttk.LabelFrame(main, text="Insert into ...", padding=6)
        bottom.grid(row=2, column=0, sticky="nsew")
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
        ttk.Button(grp, text="Tạo câu Insert", command=self._generate_sql).grid(row=0, column=0, sticky="ew", pady=4)
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
        self._generated_rows.clear()
        self._set_sql_label(table)

    def _set_sql_label(self, table: str):
        frame: ttk.LabelFrame = self.txt_sql.master  # type: ignore[assignment]
        frame.configure(text=f"Insert into {table}")

    # ------------------------------------------------------------------
    def _generate_sql(self):
        rows = self.grid.get_all()
        if not rows:
            messagebox.showwarning("Tool VIP", "Không có dữ liệu để tạo insert.", parent=self)
            return
        if not self._columns:
            messagebox.showwarning("Tool VIP", "Chưa chọn bảng.", parent=self)
            return
        table = self._current_table()
        if not table:
            messagebox.showwarning("Tool VIP", "Chưa chọn bảng.", parent=self)
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
        self.txt_sql.delete("1.0", tk.END)
        self.txt_sql.insert(tk.END, "\n".join(sql_lines))
        self._generated_rows = formatted_rows

    def _copy_sql(self):
        data = self.txt_sql.get("1.0", tk.END).strip()
        if not data:
            return
        self.clipboard_clear()
        self.clipboard_append(data)
        messagebox.showinfo("Tool VIP", "Đã copy câu insert.", parent=self)

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
            self._generated_rows = current_rows

    def _clear(self):
        if not messagebox.askyesno("Tool VIP", "Bạn có muốn reset dữ liệu không?", parent=self):
            return
        self.grid.clear()
        self.grid.append_dict({})
        self.txt_sql.delete("1.0", tk.END)
        self._generated_rows.clear()

    def _execute(self):
        table = self._current_table()
        if not table:
            messagebox.showwarning("Tool VIP", "Chưa chọn bảng.", parent=self)
            return
        rows = self.grid.get_all()
        if not rows:
            messagebox.showwarning("Tool VIP", "Không có dữ liệu để insert.", parent=self)
            return
        if not messagebox.askyesno("Tool VIP", "Thực thi insert?", parent=self):
            return
        if not self.conn:
            messagebox.showerror("Tool VIP", "Chưa kết nối database.", parent=self)
            return
        pk_cols = self._pk_columns
        pk_missing = [row for row in rows if any(not row.get(pk) for pk in pk_cols)]
        if pk_cols and pk_missing:
            if not messagebox.askyesno(
                "Tool VIP",
                "Một số dòng thiếu giá trị khóa chính, vẫn tiếp tục insert?",
                parent=self,
            ):
                return
        duplicates = {}
        try:
            if pk_cols:
                keys = []
                for row in rows:
                    if any(row.get(pk) == "" for pk in pk_cols):
                        continue
                    keys.append([row.get(pk) for pk in pk_cols])
                duplicates = db_utils.fetch_rows_by_pk(self.conn, table, self.current_owner, pk_cols, keys)
        except Exception as exc:
            messagebox.showerror("Tool VIP", f"Lỗi kiểm tra trùng: {exc}", parent=self)
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
                messagebox.showerror("Tool VIP", f"Lỗi xóa dữ liệu cũ: {exc}", parent=self)
                return

        try:
            ordered_rows = []
            for row in rows:
                ordered_rows.append([row.get(col) if row.get(col) != "" else None for col in self._columns])
            db_utils.insert_rows(self.conn, table, self.current_owner, self._columns, ordered_rows)
        except Exception as exc:
            messagebox.showerror("Tool VIP", f"Lỗi insert: {exc}", parent=self)
            return
        messagebox.showinfo("Tool VIP", "Insert thành công.", parent=self)

    # ------------------------------------------------------------------
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


def open_insert_window(parent: tk.Widget, connection: Dict[str, str]):
    InsertWindow(parent, connection)
