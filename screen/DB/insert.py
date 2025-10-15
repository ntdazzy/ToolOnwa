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
from screen.DB.widgets import ColumnOrderDialog, DataGrid, DuplicatePreviewDialog, LoadingPopup
from core import i18n

APP_TITLE = "Tool VIP"


class InsertWindow(tk.Toplevel):
    def __init__(self, parent: tk.Widget, connection: Dict[str, str]):
        super().__init__(parent)
        self.parent = parent
        self.conn_info = connection
        self.conn = None
        self.current_owner = connection.get("user", "").upper()
        self.title(i18n.translate("insert.title"))
        self.geometry("1180x720")
        self.minsize(960, 600)
        self.resizable(True, True)

        self._table_items: List[Dict[str, str]] = []
        self._table_view: List[Dict[str, str]] = []
        self._active_table: Optional[Dict[str, str]] = None
        self._columns: List[str] = []
        self._column_meta: Dict[str, dict] = {}
        self._pk_columns: List[str] = []
        self._generated_rows: List[Dict[str, str]] = []
        self._loader: Optional[LoadingPopup] = None

        self._build_ui()
        self._lang_listener = self._handle_language_change
        i18n.add_listener(self._lang_listener)
        self._apply_language()
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
        for index in range(3):
            top.columnconfigure(index, weight=0 if index else 1)

        self._build_search(top)
        self._build_actions(top)
        self._build_connection(top)

        middle = ttk.Frame(main)
        middle.grid(row=1, column=0, sticky="nsew", pady=(8, 6))
        middle.rowconfigure(0, weight=1)
        middle.columnconfigure(0, weight=1)

        self.grid = DataGrid(middle)
        self.grid.grid(row=0, column=0, sticky="nsew")

        self.btn_bar = ttk.Frame(middle)
        self.btn_bar.grid(row=1, column=0, sticky="e", pady=(6, 0))
        ttk.Button(self.btn_bar, text=self._t("insert.btn.import_csv"), command=self.grid.import_csv_dialog).pack(side="left", padx=4)
        ttk.Button(self.btn_bar, text=self._t("insert.btn.export_csv"), command=self.grid.export_csv_dialog).pack(side="left", padx=4)
        ttk.Button(self.btn_bar, text=self._t("insert.btn.add_row"), command=lambda: self.grid.append_dict({})).pack(side="left", padx=4)

        self.frm_sql = ttk.LabelFrame(main, text=self._t("insert.section.sql", table="..."), padding=6)
        self.frm_sql.grid(row=2, column=0, sticky="nsew")
        self.frm_sql.rowconfigure(0, weight=1)
        self.frm_sql.columnconfigure(0, weight=1)

        self.txt_sql = ScrolledText(self.frm_sql, height=8, wrap="word")
        self.txt_sql.grid(row=0, column=0, sticky="nsew")


    def _build_search(self, parent: ttk.Frame):
        self.grp_search = ttk.LabelFrame(parent, text=self._t("insert.section.search"), padding=6)
        self.grp_search.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.grp_search.columnconfigure(0, weight=1)

        self.lbl_table_name = ttk.Label(self.grp_search, text=self._t("insert.label.table_name"))
        self.lbl_table_name.grid(row=0, column=0, sticky="w")
        self.var_search = tk.StringVar()
        entry = ttk.Entry(self.grp_search, textvariable=self.var_search)
        entry.grid(row=1, column=0, sticky="ew", pady=4)
        entry.bind("<KeyRelease>", lambda _event: self._filter_tables())
        self.list_tables = tk.Listbox(self.grp_search, height=10)
        self.list_tables.grid(row=2, column=0, sticky="nsew", pady=(0, 4))
        self.list_tables.bind("<<ListboxSelect>>", self._on_select_table)
        self.grp_search.rowconfigure(2, weight=1)



    def _build_actions(self, parent: ttk.Frame):
        self.grp_actions = ttk.LabelFrame(parent, text=self._t("insert.section.actions"), padding=6)
        self.grp_actions.grid(row=0, column=1, sticky="n", padx=(0, 8))
        self.btn_build_sql = ttk.Button(self.grp_actions, text=self._t("insert.btn.build_sql"), command=self._generate_sql)
        self.btn_build_sql.grid(row=0, column=0, sticky="ew", pady=4)
        self.btn_copy = ttk.Button(self.grp_actions, text=self._t("common.copy"), command=self._copy_sql)
        self.btn_copy.grid(row=1, column=0, sticky="ew", pady=4)
        self.btn_reorder = ttk.Button(self.grp_actions, text=self._t("insert.btn.reorder"), command=self._change_column_order)
        self.btn_reorder.grid(row=2, column=0, sticky="ew", pady=4)
        self.btn_execute = ttk.Button(self.grp_actions, text=self._t("insert.btn.execute"), command=self._execute)
        self.btn_execute.grid(row=3, column=0, sticky="ew", pady=4)
        self.btn_clear = ttk.Button(self.grp_actions, text=self._t("insert.btn.clear"), command=self._clear)
        self.btn_clear.grid(row=4, column=0, sticky="ew", pady=4)



    def _build_connection(self, parent: ttk.Frame):
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
                msg = f"{self._t("insert.msg.metadata_error", error=str(exc))}"
                self.after(0, lambda m=msg: self._show_error(m))
                return
            self.after(0, lambda: self._init_tables(tables))

        self._show_loading(self._t("common.loading_tables"))
        threading.Thread(target=worker, daemon=True).start()


    def _show_error(self, msg: str):
        self._hide_loading()
        messagebox.showerror(APP_TITLE, msg, parent=self)
        self.destroy()

    def _init_tables(self, tables: List[str]):
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
            self.frm_sql.config(text=self._t("insert.section.sql", table="..."))

    # ------------------------------------------------------------------
    def _filter_tables(self):
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

    def _on_select_table(self, _event=None):
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
        if not self.conn:
            return
        try:
            columns = db_utils.fetch_table_columns(self.conn, item["full"], self.current_owner)
            pk_cols = db_utils.fetch_primary_keys(self.conn, item["full"], self.current_owner)
        except Exception as exc:
            messagebox.showerror(APP_TITLE, self._t("insert.msg.metadata_error", error=str(exc)), parent=self)
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
        self.frm_sql.config(text=self._t("insert.section.sql", table=table_display))

    # ------------------------------------------------------------------
    def _generate_sql(self):
        rows = self.grid.get_all()
        if not rows:
            messagebox.showwarning(APP_TITLE, self._t("insert.msg.no_data_generate"), parent=self)
            return
        if not self._columns:
            messagebox.showwarning(APP_TITLE, self._t("insert.msg.no_table"), parent=self)
            return
        table = self._current_table()
        if not table:
            messagebox.showwarning(APP_TITLE, self._t("insert.msg.no_table"), parent=self)
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
        self.txt_sql.insert(tk.END, "".join(sql_lines))
        self._generated_rows = formatted_rows


    def _copy_sql(self):
        data = self.txt_sql.get("1.0", tk.END).strip()
        if not data:
            return
        self.clipboard_clear()
        self.clipboard_append(data)
        messagebox.showinfo(APP_TITLE, self._t("insert.msg.copy_done"), parent=self)


    def _change_column_order(self):
        if not self._columns:
            messagebox.showwarning(APP_TITLE, self._t("insert.msg.no_columns_update"), parent=self)
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
        if not messagebox.askyesno(APP_TITLE, self._t("insert.msg.clear_confirm"), parent=self):
            return
        self.grid.clear()
        self.grid.append_dict({})
        self.txt_sql.delete("1.0", tk.END)
        self._generated_rows.clear()


    def _execute(self):
        table = self._current_table()
        if not table:
            messagebox.showwarning(APP_TITLE, self._t("insert.msg.no_table"), parent=self)
            return
        rows = self.grid.get_all()
        if not rows:
            messagebox.showwarning(APP_TITLE, self._t("insert.msg.no_data_execute"), parent=self)
            return
        if not messagebox.askyesno(APP_TITLE, self._t("insert.msg.confirm_execute"), parent=self):
            return
        if not self.conn:
            messagebox.showerror(APP_TITLE, self._t("insert.msg.not_connected"), parent=self)
            return
        pk_cols = self._pk_columns
        pk_missing = [row for row in rows if any(not row.get(pk) for pk in pk_cols)]
        if pk_cols and pk_missing:
            if not messagebox.askyesno(APP_TITLE, self._t("insert.msg.pk_missing_confirm"), parent=self):
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
            messagebox.showerror(APP_TITLE, self._t("insert.msg.check_duplicates_error", error=str(exc)), parent=self)
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
                messagebox.showerror(APP_TITLE, self._t("insert.msg.delete_old_error", error=str(exc)), parent=self)
                return

        try:
            ordered_rows = []
            for row in rows:
                ordered_rows.append([row.get(col) if row.get(col) != "" else None for col in self._columns])
            db_utils.insert_rows(self.conn, table, self.current_owner, self._columns, ordered_rows)
        except Exception as exc:
            messagebox.showerror(APP_TITLE, self._t("insert.msg.insert_error", error=str(exc)), parent=self)
            return
        messagebox.showinfo(APP_TITLE, self._t("insert.msg.insert_success"), parent=self)


    # ------------------------------------------------------------------
    def _current_table(self) -> Optional[str]:
        if not self._active_table:
            return None
        return self._active_table["full"]

    def _on_close(self):
        self._hide_loading()
        try:
            if self.conn:
                self.conn.close()
        except Exception:
            pass
        self.destroy()

    def destroy(self):
        if hasattr(self, "_lang_listener"):
            i18n.remove_listener(self._lang_listener)
        super().destroy()

    def _show_loading(self, message: str):
        if self._loader:
            return
        self._loader = LoadingPopup(self, message)

    def _hide_loading(self):
        if not self._loader:
            return
        self._loader.close()
        self._loader = None

    def _handle_language_change(self, _lang: str) -> None:
        self._apply_language()

    def _apply_language(self) -> None:
        self.title(self._t("insert.title"))
        if hasattr(self, "grp_search"):
            self.grp_search.config(text=self._t("insert.section.search"))
        if hasattr(self, "lbl_table_name"):
            self.lbl_table_name.config(text=self._t("insert.label.table_name"))
        if hasattr(self, "grp_actions"):
            self.grp_actions.config(text=self._t("insert.section.actions"))
        if hasattr(self, "btn_build_sql"):
            self.btn_build_sql.config(text=self._t("insert.btn.build_sql"))
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
        if hasattr(self, "btn_bar"):
            for child, key in [
                (self.btn_bar.winfo_children()[0], "insert.btn.import_csv"),
                (self.btn_bar.winfo_children()[1], "insert.btn.export_csv"),
                (self.btn_bar.winfo_children()[2], "insert.btn.add_row"),
            ]:
                child.config(text=self._t(key))
        current_display = self._active_table["display"] if self._active_table else "..."
        if hasattr(self, "frm_sql"):
            self.frm_sql.config(text=self._t("insert.section.sql", table=current_display))

    def _t(self, key: str, **kwargs) -> str:
        return i18n.translate(key, **kwargs)


def open_insert_window(parent: tk.Widget, connection: Dict[str, str]):
    InsertWindow(parent, connection)
