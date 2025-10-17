"""Man hinh xem lich su thao tac."""

from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText
from typing import Dict, List, Optional

from core import history, i18n
from screen.DB import insert as insert_screen
from screen.DB import update as update_screen

APP_TITLE_KEY = "common.app_title"


class HistoryWindow(tk.Toplevel):
    """Cua so hien thi danh sach lich su thao tac."""

    def __init__(self, parent: tk.Widget):
        """Khoi tao cua so lich su voi danh sach ban dau."""
        super().__init__(parent)
        self.parent = parent
        self.title(i18n.translate("history.title"))
        self.geometry("880x560")
        self.minsize(760, 480)
        self._set_icon()

        self.records: List[Dict[str, str]] = []
        self.filtered: List[Dict[str, str]] = []

        self.var_action = tk.StringVar(value="")
        self.var_search = tk.StringVar()

        self._build_ui()
        self._lang_listener = self._handle_language_change
        i18n.add_listener(self._lang_listener)
        self._apply_language()
        self._load_records()

        self.transient(parent)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self.destroy)

    def _build_ui(self) -> None:
        """Tao giao dien gom bo loc, tim kiem va bang treeview."""
        root = ttk.Frame(self, padding=8)
        root.pack(fill="both", expand=True)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(1, weight=1)

        frm_top = ttk.Frame(root)
        frm_top.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        frm_top.columnconfigure(3, weight=1)

        self.lbl_filter = ttk.Label(frm_top, text=self._t("history.filter.type"))
        self.lbl_filter.grid(row=0, column=0, sticky="w")
        self.cbo_action = ttk.Combobox(frm_top, state="readonly", textvariable=self.var_action, width=18)
        self.cbo_action.grid(row=0, column=1, sticky="w", padx=(6, 18))
        self.cbo_action.bind("<<ComboboxSelected>>", lambda _event: self._apply_filters())

        self.lbl_search = ttk.Label(frm_top, text=self._t("history.search.placeholder"))
        self.lbl_search.grid(row=0, column=2, sticky="w")
        self.ent_search = ttk.Entry(frm_top, textvariable=self.var_search)
        self.ent_search.grid(row=0, column=3, sticky="ew", padx=(6, 0))
        self.var_search.trace_add("write", lambda *_args: self._apply_filters())

        columns = ("timestamp", "action_type", "object_name", "row_count", "status", "message", "sql")
        self.tree = ttk.Treeview(root, columns=columns, show="headings", height=12)
        self.tree.grid(row=1, column=0, sticky="nsew")
        for col in columns:
            self.tree.heading(col, text=col.title())
        self.tree.column("timestamp", width=150, anchor="w")
        self.tree.column("action_type", width=120, anchor="w")
        self.tree.column("object_name", width=160, anchor="w")
        self.tree.column("row_count", width=80, anchor="center")
        self.tree.column("status", width=90, anchor="center")
        self.tree.column("message", width=220, anchor="w")
        self.tree.column("sql", width=260, anchor="w")
        self.tree.bind("<Double-1>", lambda _event: self._open_detail())

        scroll_y = ttk.Scrollbar(root, orient="vertical", command=self.tree.yview)
        scroll_y.grid(row=1, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=scroll_y.set)

        frm_bottom = ttk.Frame(root)
        frm_bottom.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        frm_bottom.columnconfigure(0, weight=1)
        frm_bottom.columnconfigure(1, weight=1)
        frm_bottom.columnconfigure(2, weight=1)
        frm_bottom.columnconfigure(3, weight=1)

        self.btn_refresh = ttk.Button(frm_bottom, command=self._load_records)
        self.btn_refresh.grid(row=0, column=0, sticky="ew", padx=4)
        self.btn_detail = ttk.Button(frm_bottom, command=self._open_detail)
        self.btn_detail.grid(row=0, column=1, sticky="ew", padx=4)
        self.btn_export = ttk.Button(frm_bottom, command=self._export_csv)
        self.btn_export.grid(row=0, column=2, sticky="ew", padx=4)
        self.btn_close = ttk.Button(frm_bottom, command=self.destroy)
        self.btn_close.grid(row=0, column=3, sticky="ew", padx=4)

    def _load_records(self) -> None:
        """Nap du lieu lich su tu co so du lieu va cap nhat bang."""
        self.records = history.get_actions()
        types = sorted({rec.get("action_type", "") for rec in self.records if rec.get("action_type")})
        type_options = [self._t("history.filter.all")] + types
        self.cbo_action["values"] = type_options
        if not self.var_action.get() and type_options:
            self.var_action.set(type_options[0])
        self._apply_filters()

    def _apply_filters(self) -> None:
        """Loc du lieu theo loai va tu khoa tim kiem."""
        selected = self.var_action.get()
        keyword = self.var_search.get().strip().lower()
        target_type = ""
        if selected and selected != self._t("history.filter.all"):
            target_type = selected
        filtered: List[Dict[str, str]] = []
        for record in self.records:
            if target_type and record.get("action_type") != target_type:
                continue
            if keyword:
                haystack = " ".join(
                    str(record.get(key, ""))
                    for key in ("timestamp", "action_type", "object_name", "status", "message", "sql_text")
                ).lower()
                if keyword not in haystack:
                    continue
            filtered.append(record)
        self.filtered = filtered
        self._refresh_tree()

    def _refresh_tree(self) -> None:
        """Cap nhat treeview theo danh sach loc hien tai."""
        self.tree.delete(*self.tree.get_children())
        for record in self.filtered:
            sql_preview = (record.get("sql_text") or "")[:120]
            if len(record.get("sql_text") or "") > 120:
                sql_preview += "..."
            self.tree.insert(
                "",
                "end",
                iid=str(record.get("id")),
                values=(
                    record.get("timestamp", ""),
                    record.get("action_type", ""),
                    record.get("object_name", ""),
                    record.get("row_count", ""),
                    record.get("status", ""),
                    record.get("message", ""),
                    sql_preview,
                ),
            )

    def _open_detail(self) -> None:
        """Mo hop thoai chi tiet cho ban ghi duoc chon."""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning(self._t(APP_TITLE_KEY), self._t("history.msg.no_selection"), parent=self)
            return
        item_id = selection[0]
        record = next((rec for rec in self.filtered if str(rec.get("id")) == item_id), None)
        if not record:
            messagebox.showwarning(self._t(APP_TITLE_KEY), self._t("history.msg.no_selection"), parent=self)
            return
        HistoryDetailDialog(self, record)

    def _export_csv(self) -> None:
        """Xuat danh sach lich su ra file CSV."""
        path = filedialog.asksaveasfilename(
            title=self._t("history.btn.export_csv"),
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv"), (self._t("backup.dialog.all_files"), "*.*")],
            parent=self,
        )
        if not path:
            return
        if history.export_csv(path):
            messagebox.showinfo(self._t(APP_TITLE_KEY), self._t("history.msg.export_success"), parent=self)
        else:
            messagebox.showerror(self._t(APP_TITLE_KEY), self._t("history.msg.export_error"), parent=self)

    def _handle_language_change(self, _lang: str) -> None:
        """Cap nhat giao dien khi doi ngon ngu."""
        self._apply_language()
        self._refresh_tree()

    def _apply_language(self) -> None:
        """Dat chu thich va tieu de theo ngon ngu."""
        self.title(self._t("history.title"))
        self.lbl_filter.config(text=self._t("history.filter.type"))
        self.lbl_search.config(text=self._t("history.search.placeholder"))
        self.btn_refresh.config(text=self._t("history.btn.refresh"))
        self.btn_detail.config(text=self._t("history.btn.detail"))
        self.btn_export.config(text=self._t("history.btn.export_csv"))
        self.btn_close.config(text=self._t("common.close"))
        headers = {
            "timestamp": self._t("history.column.time"),
            "action_type": self._t("history.column.type"),
            "object_name": self._t("history.column.object"),
            "row_count": self._t("history.column.rows"),
            "status": self._t("history.column.status"),
            "message": self._t("history.column.message"),
            "sql": self._t("history.column.sql"),
        }
        for key, text in headers.items():
            self.tree.heading(key, text=text)
        if self.cbo_action["values"]:
            values = [self._t("history.filter.all")] + [val for val in self.cbo_action["values"] if val != self._t("history.filter.all")]
            self.cbo_action["values"] = values
            if not self.var_action.get():
                self.var_action.set(values[0])
        self._apply_filters()

    def destroy(self) -> None:
        """Huy cua so va go listener ngon ngu."""
        if hasattr(self, "_lang_listener"):
            i18n.remove_listener(self._lang_listener)
        super().destroy()

    def _set_icon(self) -> None:
        """Gan icon neu ton tai."""
        try:
            self.iconbitmap("icons/logo.ico")
        except Exception:
            pass

    def _t(self, key: str, **kwargs) -> str:
        """Truy xuat chuoi i18n."""
        return i18n.translate(key, **kwargs)


class HistoryDetailDialog(tk.Toplevel):
    """Hop thoai hien thi chi tiet mot ban ghi lich su."""

    def __init__(self, parent: tk.Widget, record: Dict[str, str]):
        """Khoi tao hop thoai chi tiet voi du lieu truyen vao."""
        super().__init__(parent)
        self.parent = parent
        self.record = record
        self.title(i18n.translate("history.detail.title"))
        self.geometry("720x480")
        self.minsize(640, 420)
        self._set_icon()

        self._build_ui()
        self._lang_listener = self._handle_language_change
        i18n.add_listener(self._lang_listener)
        self._apply_language()
        self.transient(parent)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self.destroy)

    def _build_ui(self) -> None:
        """Tao layout gom thong diep va noi dung SQL."""
        root = ttk.Frame(self, padding=8)
        root.pack(fill="both", expand=True)
        root.rowconfigure(2, weight=1)
        root.columnconfigure(0, weight=1)

        self.lbl_message_title = ttk.Label(root, text=self._t("history.detail.message"))
        self.lbl_message_title.grid(row=0, column=0, sticky="w")
        self.lbl_message_value = ttk.Label(root, text=self.record.get("message", ""), wraplength=660)
        self.lbl_message_value.grid(row=1, column=0, sticky="w", pady=(2, 8))

        self.frm_sql = ttk.LabelFrame(root, padding=6)
        self.frm_sql.grid(row=2, column=0, sticky="nsew")
        self.frm_sql.rowconfigure(0, weight=1)
        self.frm_sql.columnconfigure(0, weight=1)

        self.txt_sql = ScrolledText(self.frm_sql, wrap="word")
        self.txt_sql.grid(row=0, column=0, sticky="nsew")
        self.txt_sql.insert(tk.END, self.record.get("sql_text", ""))
        self.txt_sql.configure(state="disabled")

        frm_buttons = ttk.Frame(root)
        frm_buttons.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        frm_buttons.columnconfigure(0, weight=1)
        frm_buttons.columnconfigure(1, weight=1)
        frm_buttons.columnconfigure(2, weight=1)
        frm_buttons.columnconfigure(3, weight=1)

        self.btn_copy = ttk.Button(frm_buttons, command=self._copy_sql)
        self.btn_copy.grid(row=0, column=0, sticky="ew", padx=4)
        self.btn_use_insert = ttk.Button(frm_buttons, command=self._use_insert)
        self.btn_use_insert.grid(row=0, column=1, sticky="ew", padx=4)
        self.btn_use_update = ttk.Button(frm_buttons, command=self._use_update)
        self.btn_use_update.grid(row=0, column=2, sticky="ew", padx=4)
        self.btn_close = ttk.Button(frm_buttons, command=self.destroy)
        self.btn_close.grid(row=0, column=3, sticky="ew", padx=4)

    def _copy_sql(self) -> None:
        """Copy toan bo SQL vao clipboard."""
        sql_text = self.record.get("sql_text", "")
        if not sql_text:
            return
        self.clipboard_clear()
        self.clipboard_append(sql_text)
        messagebox.showinfo(self._t(APP_TITLE_KEY), self._t("history.msg.clipboard"), parent=self)

    def _use_insert(self) -> None:
        """Dat SQL vao cua so Insert dang mo."""
        sql_text = self.record.get("sql_text", "")
        if not sql_text:
            return
        windows = insert_screen.get_active_windows()
        if not windows:
            messagebox.showwarning(self._t(APP_TITLE_KEY), self._t("history.msg.no_window"), parent=self)
            return
        target = windows[-1]
        target.set_sql_text(sql_text)

    def _use_update(self) -> None:
        """Dat SQL vao cua so Update dang mo."""
        sql_text = self.record.get("sql_text", "")
        if not sql_text:
            return
        windows = update_screen.get_active_windows()
        if not windows:
            messagebox.showwarning(self._t(APP_TITLE_KEY), self._t("history.msg.no_window"), parent=self)
            return
        target = windows[-1]
        target.set_sql_text(sql_text)

    def _handle_language_change(self, _lang: str) -> None:
        """Cap nhat giao dien khi doi ngon ngu."""
        self._apply_language()

    def _apply_language(self) -> None:
        """Cap nhat text cua cac thanh phan."""
        self.title(self._t("history.detail.title"))
        self.lbl_message_title.config(text=self._t("history.detail.message"))
        self.frm_sql.config(text=self._t("history.detail.sql"))
        self.btn_copy.config(text=self._t("history.detail.copy"))
        self.btn_use_insert.config(text=self._t("history.detail.use_insert"))
        self.btn_use_update.config(text=self._t("history.detail.use_update"))
        self.btn_close.config(text=self._t("common.close"))
        self.lbl_message_value.config(text=self.record.get("message", ""))

    def destroy(self) -> None:
        """Huy hop thoai chi tiet va go listener."""
        if hasattr(self, "_lang_listener"):
            i18n.remove_listener(self._lang_listener)
        super().destroy()

    def _set_icon(self) -> None:
        """Gan icon neu co san."""
        try:
            self.iconbitmap("icons/logo.ico")
        except Exception:
            pass

    def _t(self, key: str, **kwargs) -> str:
        """Tra cuu chuoi i18n."""
        return i18n.translate(key, **kwargs)
