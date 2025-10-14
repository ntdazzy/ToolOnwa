"""
Backup and restore screens.
"""
from __future__ import annotations

import csv
import datetime as dt
import re
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText
from typing import Dict, List, Optional

from screen.DB import db_utils
from screen.DB.widgets import DataGrid


class BackupRestoreBase(tk.Toplevel):
    """
    Base class that provides table search/loading and connection management.
    """

    GEOMETRY = "520x640"

    def __init__(self, parent: tk.Widget, connection: Dict[str, str], title: str):
        super().__init__(parent)
        self.parent = parent
        self.conn_info = connection
        self.conn = None
        self.current_owner = connection.get("user", "").upper()
        self.title(title)
        self.geometry(self.GEOMETRY)
        self.minsize(480, 560)
        self.resizable(True, True)

        self._tables_all: List[str] = []
        self._columns: List[str] = []
        self._column_meta: Dict[str, dict] = {}
        self._current_table: Optional[str] = None

        self.var_search = tk.StringVar()
        self.var_selected_table = tk.StringVar()

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(120, self._connect_async)

    # ------------------------------------------------------------------
    def _build_ui(self):
        main = ttk.Frame(self, padding=8)
        main.pack(fill="both", expand=True)
        main.rowconfigure(1, weight=1)
        main.columnconfigure(0, weight=1)

        search_group = ttk.LabelFrame(main, text="Tìm kiếm", padding=6)
        search_group.grid(row=0, column=0, sticky="nsew", pady=(0, 6))
        search_group.columnconfigure(0, weight=1)

        ttk.Label(search_group, text="Table Name").grid(row=0, column=0, sticky="w")
        ent = ttk.Entry(search_group, textvariable=self.var_search)
        ent.grid(row=1, column=0, sticky="ew", pady=4)
        ent.bind("<KeyRelease>", lambda e: self._filter_tables())

        self.list_tables = tk.Listbox(search_group, height=8)
        self.list_tables.grid(row=2, column=0, sticky="nsew")
        self.list_tables.bind("<<ListboxSelect>>", self._handle_table_select)
        search_group.rowconfigure(2, weight=1)

        self.body = ttk.Frame(main)
        self.body.grid(row=1, column=0, sticky="nsew")
        self.body.columnconfigure(0, weight=1)
        self.body.rowconfigure(0, weight=1)

        self._build_body(self.body)

    def _build_body(self, parent: ttk.Frame):
        raise NotImplementedError

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
        self._tables_all = sorted(tables)
        self.list_tables.delete(0, tk.END)
        for tbl in self._tables_all:
            self.list_tables.insert(tk.END, tbl)
        if self._tables_all:
            self.list_tables.selection_set(0)
            self._handle_table_select()

    def _filter_tables(self):
        keyword = self.var_search.get().strip().upper()
        self.list_tables.delete(0, tk.END)
        for tbl in self._tables_all:
            if not keyword or keyword in tbl.upper():
                self.list_tables.insert(tk.END, tbl)

    def _handle_table_select(self, _event=None):
        selection = self.list_tables.curselection()
        if not selection:
            return
        table = self.list_tables.get(selection[0])
        if table == self._current_table:
            return
        self._current_table = table
        self.var_selected_table.set(table)
        self._load_table_metadata(table)

    def _load_table_metadata(self, table: str):
        if not self.conn:
            return
        try:
            columns = db_utils.fetch_table_columns(self.conn, table, self.current_owner)
        except Exception as exc:
            messagebox.showerror("Tool VIP", f"Lỗi đọc metadata: {exc}", parent=self)
            return
        self._columns = [c["column_name"] for c in columns]
        self._column_meta = {c["column_name"]: c for c in columns}
        self.on_table_ready(table)

    def on_table_ready(self, table: str):
        raise NotImplementedError

    # ------------------------------------------------------------------
    def _split_table(self, raw: str) -> tuple[str, str]:
        if "." in raw:
            owner, name = raw.split(".", 1)
            return owner.strip().upper(), name.strip().upper()
        return self.current_owner.upper(), raw.strip().upper()

    def _append_log(self, text: str):
        widget = getattr(self, "txt_log", None)
        if widget is None:
            return
        widget.insert(tk.END, text.strip() + "\n")
        widget.see(tk.END)

    def _on_close(self):
        try:
            if self.conn:
                self.conn.close()
        except Exception:
            pass
        self.destroy()

    # ------------------------------------------------------------------
    def _run_statements(self, sql_text: str) -> bool:
        if not self.conn:
            messagebox.showerror("Tool VIP", "Chưa kết nối database.", parent=self)
            return False
        statements = [stmt.strip() for stmt in re.split(r";\s*(?:\n|$)", sql_text) if stmt.strip()]
        if not statements:
            messagebox.showwarning("Tool VIP", "Không có câu lệnh để thực thi.", parent=self)
            return False
        try:
            cur = self.conn.cursor()
        except Exception as exc:
            messagebox.showerror("Tool VIP", f"Lỗi tạo cursor: {exc}", parent=self)
            return False

        try:
            for stmt in statements:
                self._append_log(f"> {stmt}")
                try:
                    cur.execute(stmt)
                except Exception as exc:
                    if self._should_ignore_drop(stmt, exc):
                        self._append_log("  (Bảng không tồn tại, bỏ qua DROP)")
                        continue
                    self.conn.rollback()
                    self._append_log(f"  ERROR: {exc}")
                    messagebox.showerror("Tool VIP", f"Lỗi thực thi: {exc}", parent=self)
                    return False
            self.conn.commit()
            self._append_log("Hoàn thành.")
            messagebox.showinfo("Tool VIP", "Thực thi thành công.", parent=self)
            return True
        finally:
            try:
                cur.close()
            except Exception:
                pass

    @staticmethod
    def _should_ignore_drop(statement: str, exc: Exception) -> bool:
        text = statement.strip().upper()
        if not text.startswith("DROP"):
            return False
        err = str(exc).upper()
        return "ORA-00942" in err or "TABLE OR VIEW DOES NOT EXIST" in err


class BackupWindow(BackupRestoreBase):
    """
    Backup screen: build backup table with optional SQL customisation.
    """

    def __init__(self, parent: tk.Widget, connection: Dict[str, str]):
        super().__init__(parent, connection, title="Backup Table")

    def _build_body(self, parent: ttk.Frame):
        parent.columnconfigure(0, weight=1)

        ttk.Label(parent, text="Bảng nguồn").grid(row=0, column=0, sticky="w")
        self.ent_source = ttk.Entry(parent, textvariable=self.var_selected_table, state="readonly")
        self.ent_source.grid(row=1, column=0, sticky="ew", pady=(0, 6))

        ttk.Label(parent, text="Tên bảng backup").grid(row=2, column=0, sticky="w")
        self.var_backup_name = tk.StringVar()
        self.ent_backup = ttk.Entry(parent, textvariable=self.var_backup_name)
        self.ent_backup.grid(row=3, column=0, sticky="ew", pady=(0, 10))

        sql_frame = ttk.LabelFrame(parent, text="SQL", padding=6)
        sql_frame.grid(row=4, column=0, sticky="nsew")
        sql_frame.columnconfigure(0, weight=1)
        sql_frame.rowconfigure(0, weight=1)

        self.txt_sql = ScrolledText(sql_frame, height=10, wrap="word")
        self.txt_sql.grid(row=0, column=0, sticky="nsew")

        btns = ttk.Frame(parent)
        btns.grid(row=5, column=0, sticky="ew", pady=6)
        btns.columnconfigure(0, weight=1)
        btns.columnconfigure(1, weight=1)
        ttk.Button(btns, text="Cập nhật SQL", command=self._fill_default_sql).grid(row=0, column=0, sticky="ew", padx=(0, 4))
        ttk.Button(btns, text="Thực thi", command=self._execute).grid(row=0, column=1, sticky="ew")

        log_frame = ttk.LabelFrame(parent, text="Log", padding=6)
        log_frame.grid(row=6, column=0, sticky="nsew")
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

        self.txt_log = ScrolledText(log_frame, height=8, wrap="word", state="normal")
        self.txt_log.grid(row=0, column=0, sticky="nsew")

        parent.rowconfigure(4, weight=1)
        parent.rowconfigure(6, weight=1)

    def on_table_ready(self, table: str):
        owner, name = self._split_table(table)
        default_name = f"{owner}.{name}_BK_{dt.datetime.now().strftime('%Y%m%d')}"
        self.var_backup_name.set(default_name)
        self._fill_default_sql()

    def _fill_default_sql(self):
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
        sql_text = self.txt_sql.get("1.0", tk.END)
        self._run_statements(sql_text)


class RestoreFromBackupWindow(BackupRestoreBase):
    """
    Restore data from an existing backup table.
    """

    def __init__(self, parent: tk.Widget, connection: Dict[str, str]):
        super().__init__(parent, connection, title="Restore From Backup Table")

    def _build_body(self, parent: ttk.Frame):
        parent.columnconfigure(0, weight=1)

        ttk.Label(parent, text="Bảng đích").grid(row=0, column=0, sticky="w")
        self.ent_target = ttk.Entry(parent, textvariable=self.var_selected_table, state="readonly")
        self.ent_target.grid(row=1, column=0, sticky="ew", pady=(0, 6))

        ttk.Label(parent, text="Bảng backup nguồn").grid(row=2, column=0, sticky="w")
        self.var_backup_name = tk.StringVar()
        self.ent_backup = ttk.Entry(parent, textvariable=self.var_backup_name)
        self.ent_backup.grid(row=3, column=0, sticky="ew", pady=(0, 10))

        sql_frame = ttk.LabelFrame(parent, text="SQL", padding=6)
        sql_frame.grid(row=4, column=0, sticky="nsew")
        sql_frame.columnconfigure(0, weight=1)
        sql_frame.rowconfigure(0, weight=1)

        self.txt_sql = ScrolledText(sql_frame, height=10, wrap="word")
        self.txt_sql.grid(row=0, column=0, sticky="nsew")

        btns = ttk.Frame(parent)
        btns.grid(row=5, column=0, sticky="ew", pady=6)
        btns.columnconfigure(0, weight=1)
        btns.columnconfigure(1, weight=1)
        ttk.Button(btns, text="Cập nhật SQL", command=self._fill_default_sql).grid(row=0, column=0, sticky="ew", padx=(0, 4))
        ttk.Button(btns, text="Thực thi", command=self._execute).grid(row=0, column=1, sticky="ew")

        log_frame = ttk.LabelFrame(parent, text="Log", padding=6)
        log_frame.grid(row=6, column=0, sticky="nsew")
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

        self.txt_log = ScrolledText(log_frame, height=8, wrap="word", state="normal")
        self.txt_log.grid(row=0, column=0, sticky="nsew")

        parent.rowconfigure(4, weight=1)
        parent.rowconfigure(6, weight=1)

    def on_table_ready(self, table: str):
        owner, name = self._split_table(table)
        pattern = f"{owner}.{name}_BK_{dt.datetime.now().strftime('%Y%m%d')}"
        self.var_backup_name.set(pattern)
        self._fill_default_sql()

    def _fill_default_sql(self):
        target = self.var_selected_table.get().strip()
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

    def _execute(self):
        sql_text = self.txt_sql.get("1.0", tk.END)
        self._run_statements(sql_text)


class RestoreFromCSVWindow(BackupRestoreBase):
    """
    Restore data into a table using CSV import.
    """

    GEOMETRY = "720x640"

    def __init__(self, parent: tk.Widget, connection: Dict[str, str]):
        self.imported_rows: List[Dict[str, str]] = []
        self.csv_headers: List[str] = []
        super().__init__(parent, connection, title="Restore From CSV")

    def _build_body(self, parent: ttk.Frame):
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(4, weight=1)

        ttk.Label(parent, text="Bảng đích").grid(row=0, column=0, sticky="w")
        self.ent_target = ttk.Entry(parent, textvariable=self.var_selected_table, state="readonly")
        self.ent_target.grid(row=1, column=0, sticky="ew", pady=(0, 6))

        actions = ttk.Frame(parent)
        actions.grid(row=2, column=0, sticky="ew", pady=(0, 4))
        actions.columnconfigure(0, weight=1)
        ttk.Button(actions, text="Import CSV", command=self._import_csv).grid(row=0, column=0, sticky="w")
        self.lbl_file = ttk.Label(actions, text="Chưa chọn file")
        self.lbl_file.grid(row=0, column=1, sticky="w", padx=(12, 0))

        preview_frame = ttk.LabelFrame(parent, text="Data preview", padding=4)
        preview_frame.grid(row=3, column=0, sticky="nsew", pady=(0, 6))
        preview_frame.columnconfigure(0, weight=1)
        preview_frame.rowconfigure(0, weight=1)

        self.preview_grid = DataGrid(preview_frame)
        self.preview_grid.grid(row=0, column=0, sticky="nsew")

        btns = ttk.Frame(parent)
        btns.grid(row=4, column=0, sticky="ew", pady=(0, 6))
        btns.columnconfigure(0, weight=1)
        btns.columnconfigure(1, weight=1)
        ttk.Button(btns, text="Xóa dữ liệu", command=self._clear_preview).grid(row=0, column=0, sticky="ew", padx=(0, 4))
        ttk.Button(btns, text="Thực thi", command=self._execute_restore).grid(row=0, column=1, sticky="ew")

        log_frame = ttk.LabelFrame(parent, text="Log", padding=6)
        log_frame.grid(row=5, column=0, sticky="nsew")
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

        self.txt_log = ScrolledText(log_frame, height=8, wrap="word", state="normal")
        self.txt_log.grid(row=0, column=0, sticky="nsew")

        parent.rowconfigure(3, weight=1)
        parent.rowconfigure(5, weight=1)

    def on_table_ready(self, table: str):
        if self._columns:
            self.preview_grid.configure_columns(self._columns)
        self.imported_rows.clear()
        self.preview_grid.clear()
        self.lbl_file.config(text="Chưa chọn file")

    def _import_csv(self):
        table = self.var_selected_table.get().strip()
        if not table:
            messagebox.showwarning("Tool VIP", "Vui lòng chọn bảng trước khi import.", parent=self)
            return
        path = filedialog.askopenfilename(
            title="Chọn file CSV",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            parent=self,
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                if not reader.fieldnames:
                    raise ValueError("Không tìm thấy header trong file.")
                headers = [h.strip() for h in reader.fieldnames]
                rows = [row for row in reader]
        except Exception as exc:
            messagebox.showerror("Tool VIP", f"Lỗi đọc CSV: {exc}", parent=self)
            return

        table_cols = [col.upper() for col in self._columns]
        csv_cols = [h.upper() for h in headers]
        missing = [col for col in table_cols if col not in csv_cols]
        extra = [col for col in csv_cols if col not in table_cols]
        if missing or extra:
            parts = []
            if missing:
                parts.append("Thiếu cột: " + ", ".join(missing))
            if extra:
                parts.append("Dư cột: " + ", ".join(extra))
            messagebox.showwarning("Tool VIP", "\n".join(parts), parent=self)

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
        self._append_log(f"Đã import {len(formatted_rows)} dòng từ {path}")

    def _clear_preview(self):
        self.imported_rows.clear()
        self.preview_grid.clear()
        self.lbl_file.config(text="Chưa chọn file")

    def _execute_restore(self):
        table = self.var_selected_table.get().strip()
        if not table:
            messagebox.showwarning("Tool VIP", "Chưa chọn bảng đích.", parent=self)
            return
        if not self.imported_rows:
            messagebox.showwarning("Tool VIP", "Chưa có dữ liệu để restore.", parent=self)
            return
        if not self.conn:
            messagebox.showerror("Tool VIP", "Chưa kết nối database.", parent=self)
            return
        if not messagebox.askyesno("Tool VIP", f"Restore {len(self.imported_rows)} dòng vào {table}?", parent=self):
            return

        owner, name = self._split_table(table)
        full_table = f"{owner}.{name}"
        col_list = ", ".join(self._columns)

        try:
            cur = self.conn.cursor()
        except Exception as exc:
            messagebox.showerror("Tool VIP", f"Lỗi cursor: {exc}", parent=self)
            return

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
            messagebox.showerror("Tool VIP", f"Lỗi restore: {exc}", parent=self)
            return
        finally:
            try:
                cur.close()
            except Exception:
                pass

        self._append_log("Restore CSV hoàn thành.")
        messagebox.showinfo("Tool VIP", "Restore CSV thành công.", parent=self)


def open_backup_window(parent: tk.Widget, connection: Dict[str, str]):
    BackupWindow(parent, connection)


def open_restore_from_backup_window(parent: tk.Widget, connection: Dict[str, str]):
    RestoreFromBackupWindow(parent, connection)


def open_restore_from_csv_window(parent: tk.Widget, connection: Dict[str, str]):
    RestoreFromCSVWindow(parent, connection)
