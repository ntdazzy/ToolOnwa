"""Cac hop thoai quan ly template SQL dung chung cho Insert/Update."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from tkinter.scrolledtext import ScrolledText
from typing import Dict, List, Optional

from core import i18n, templates

APP_TITLE_KEY = "common.app_title"
TEMPLATE_TYPES = ["insert", "update", "sql"]


class TemplateSaveDialog(tk.Toplevel):
    """Hop thoai thu thap thong tin khi luu mot template moi."""

    def __init__(self, parent: tk.Widget, default_type: str, default_name: str = "", default_description: str = ""):
        """Khoi tao hop thoai voi gia tri mac dinh."""
        super().__init__(parent)
        self.parent = parent
        self.default_type = default_type if default_type in TEMPLATE_TYPES else "sql"
        self.result: Optional[Dict[str, str]] = None

        self.title(i18n.translate("template.save.title"))
        self.geometry("360x220")
        self.resizable(False, False)
        self._set_icon()

        self.var_name = tk.StringVar(value=default_name)
        self.var_desc = tk.StringVar(value=default_description)
        self.var_type = tk.StringVar(value=self.default_type)

        self._build_ui()
        self._lang_listener = self._handle_language_change
        i18n.add_listener(self._lang_listener)
        self._apply_language()
        self.transient(parent)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)

    def _build_ui(self):
        """Tao giao dien gom cac truong nhap va nut dieu khien."""
        frm = ttk.Frame(self, padding=10)
        frm.pack(fill="both", expand=True)
        frm.columnconfigure(1, weight=1)

        self.lbl_name = ttk.Label(frm)
        self.lbl_name.grid(row=0, column=0, sticky="w")
        self.ent_name = ttk.Entry(frm, textvariable=self.var_name)
        self.ent_name.grid(row=0, column=1, sticky="ew", pady=4, padx=(8, 0))

        self.lbl_desc = ttk.Label(frm)
        self.lbl_desc.grid(row=1, column=0, sticky="w")
        self.ent_desc = ttk.Entry(frm, textvariable=self.var_desc)
        self.ent_desc.grid(row=1, column=1, sticky="ew", pady=4, padx=(8, 0))

        self.lbl_type = ttk.Label(frm)
        self.lbl_type.grid(row=2, column=0, sticky="w")
        self.cbo_type = ttk.Combobox(frm, state="readonly", textvariable=self.var_type, values=TEMPLATE_TYPES)
        self.cbo_type.grid(row=2, column=1, sticky="ew", pady=4, padx=(8, 0))

        btn_frame = ttk.Frame(frm)
        btn_frame.grid(row=3, column=0, columnspan=2, pady=(12, 0), sticky="e")

        self.btn_save = ttk.Button(btn_frame, command=self._on_save)
        self.btn_save.pack(side="right", padx=(8, 0))
        self.btn_cancel = ttk.Button(btn_frame, command=self._on_cancel)
        self.btn_cancel.pack(side="right")

        self.ent_name.focus_set()

    def _apply_language(self):
        """Cap nhat chu thich theo ngon ngu hien tai."""
        self.title(i18n.translate("template.save.title"))
        self.lbl_name.config(text=i18n.translate("template.save.name"))
        self.lbl_desc.config(text=i18n.translate("template.save.description"))
        self.lbl_type.config(text=i18n.translate("template.save.type"))
        self.btn_save.config(text=i18n.translate("common.ok"))
        self.btn_cancel.config(text=i18n.translate("common.cancel"))

    def _handle_language_change(self, _lang: str) -> None:
        """Cap nhat giao dien khi doi ngon ngu."""
        self._apply_language()

    def _on_save(self):
        """Xu ly su kien bam nut luu template."""
        name = self.var_name.get().strip()
        if not name:
            messagebox.showwarning(i18n.translate(APP_TITLE_KEY), i18n.translate("template.save.message_missing"), parent=self)
            return
        description = self.var_desc.get().strip()
        tpl_type = self.var_type.get()
        if tpl_type not in TEMPLATE_TYPES:
            tpl_type = "sql"
        self.result = {"name": name, "description": description, "type": tpl_type}
        self.destroy()

    def _on_cancel(self):
        """Dong hop thoai khi huy bo."""
        self.result = None
        self.destroy()

    def destroy(self):
        """Huy toplevel va bo listener ngon ngu."""
        if hasattr(self, "_lang_listener"):
            i18n.remove_listener(self._lang_listener)
        super().destroy()

    def _set_icon(self) -> None:
        """Ap dung bieu tuong neu ton tai."""
        try:
            self.iconbitmap("icons/logo.ico")
        except Exception:
            pass


class TemplateLibraryDialog(tk.Toplevel):
    """Hop thoai quan ly va chon template san co."""

    def __init__(self, parent: tk.Widget, template_type: Optional[str] = None):
        """Khoi tao hop thoai thu vien template."""
        super().__init__(parent)
        self.parent = parent
        self.template_type = template_type
        self.result: Optional[Dict[str, str]] = None
        self._records: List[Dict[str, str]] = []

        self.title(i18n.translate("template.dialog.title"))
        self.geometry("600x420")
        self.minsize(520, 360)
        self._set_icon()

        self._build_ui()
        self._lang_listener = self._handle_language_change
        i18n.add_listener(self._lang_listener)
        self._apply_language()
        self._load_templates()

        self.transient(parent)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self):
        """Cau hinh treeview, preview va thanh nut."""
        root = ttk.Frame(self, padding=8)
        root.pack(fill="both", expand=True)
        root.rowconfigure(0, weight=1)
        root.columnconfigure(0, weight=1)

        columns = ("name", "type", "description", "created")
        self.tree = ttk.Treeview(root, columns=columns, show="headings", height=8)
        self.tree.grid(row=0, column=0, sticky="nsew")
        for col in columns:
            self.tree.heading(col, text=col.title())
            self.tree.column(col, width=120 if col != "description" else 200, anchor="w")

        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.tree.bind("<Double-1>", lambda _event: self._apply())

        scrollbar = ttk.Scrollbar(root, orient="vertical", command=self.tree.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=scrollbar.set)

        preview_frame = ttk.LabelFrame(root, padding=6)
        preview_frame.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=(6, 0))
        preview_frame.rowconfigure(0, weight=1)
        preview_frame.columnconfigure(0, weight=1)
        self.preview_frame = preview_frame

        self.txt_preview = ScrolledText(preview_frame, height=6, wrap="word", state="disabled")
        self.txt_preview.grid(row=0, column=0, sticky="nsew")

        btns = ttk.Frame(root)
        btns.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        btns.columnconfigure(0, weight=1)
        btns.columnconfigure(1, weight=1)
        btns.columnconfigure(2, weight=1)
        btns.columnconfigure(3, weight=1)

        self.btn_refresh = ttk.Button(btns, command=self._load_templates)
        self.btn_refresh.grid(row=0, column=0, padx=4, sticky="ew")
        self.btn_apply = ttk.Button(btns, command=self._apply)
        self.btn_apply.grid(row=0, column=1, padx=4, sticky="ew")
        self.btn_copy = ttk.Button(btns, command=self._copy)
        self.btn_copy.grid(row=0, column=2, padx=4, sticky="ew")
        self.btn_delete = ttk.Button(btns, command=self._delete)
        self.btn_delete.grid(row=0, column=3, padx=4, sticky="ew")

        self.btn_close = ttk.Button(root, command=self._on_close)
        self.btn_close.grid(row=3, column=0, columnspan=2, pady=(10, 0), sticky="e")

    def _apply_language(self):
        """Cap nhat text hiển thị theo ngon ngu."""
        self.title(i18n.translate("template.dialog.title"))
        self.preview_frame.config(text=i18n.translate("template.dialog.preview"))
        self.btn_refresh.config(text=i18n.translate("history.btn.refresh"))
        self.btn_apply.config(text=i18n.translate("template.dialog.btn.apply"))
        self.btn_copy.config(text=i18n.translate("template.dialog.btn.copy"))
        self.btn_delete.config(text=i18n.translate("template.dialog.btn.delete"))
        self.btn_close.config(text=i18n.translate("template.dialog.btn.close"))
        headers = {
            "name": i18n.translate("template.dialog.column.name"),
            "type": i18n.translate("template.dialog.column.type"),
            "description": i18n.translate("template.dialog.column.description"),
            "created": i18n.translate("template.dialog.column.created"),
        }
        for col, text in headers.items():
            self.tree.heading(col, text=text)

    def _handle_language_change(self, _lang: str) -> None:
        """Lang nghe su thay doi ngon ngu."""
        self._apply_language()

    def _load_templates(self):
        """Nap danh sach template va cap nhat treeview."""
        self.tree.delete(*self.tree.get_children())
        if self.template_type:
            self._records = templates.list_templates(self.template_type)
        else:
            self._records = templates.list_templates()
        if not self._records:
            self._update_preview(None)
            return
        for item in self._records:
            self.tree.insert(
                "",
                "end",
                iid=item["id"],
                values=(
                    item.get("name", ""),
                    item.get("type", ""),
                    item.get("description", ""),
                    item.get("created_at", ""),
                ),
            )
        first = self.tree.get_children()
        if first:
            self.tree.selection_set(first[0])
            self._update_preview(self._records[0])

    def _on_select(self, _event=None):
        """Xu ly khi nguoi dung chon mot dong."""
        sel = self.tree.selection()
        if not sel:
            self._update_preview(None)
            return
        tpl_id = sel[0]
        record = next((r for r in self._records if r.get("id") == tpl_id), None)
        self._update_preview(record)

    def _update_preview(self, record: Optional[Dict[str, str]]):
        """Hien thi noi dung template trong o preview."""
        self.txt_preview.configure(state="normal")
        self.txt_preview.delete("1.0", tk.END)
        if record:
            self.txt_preview.insert(tk.END, record.get("content", ""))
        self.txt_preview.configure(state="disabled")

    def _apply(self):
        """Tra ket qua template duoc chon va dong hop thoai."""
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning(i18n.translate(APP_TITLE_KEY), i18n.translate("template.dialog.no_selection"), parent=self)
            return
        tpl_id = sel[0]
        record = next((r for r in self._records if r.get("id") == tpl_id), None)
        if not record:
            messagebox.showinfo(i18n.translate(APP_TITLE_KEY), i18n.translate("template.dialog.empty"), parent=self)
            return
        self.result = record
        self.destroy()

    def _copy(self):
        """Copy noi dung template vao clipboard."""
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning(i18n.translate(APP_TITLE_KEY), i18n.translate("template.dialog.no_selection"), parent=self)
            return
        record = next((r for r in self._records if r.get("id") == sel[0]), None)
        if not record:
            return
        self.clipboard_clear()
        self.clipboard_append(record.get("content", ""))
        messagebox.showinfo(i18n.translate(APP_TITLE_KEY), i18n.translate("history.msg.clipboard"), parent=self)

    def _delete(self):
        """Xoa template dang chon sau khi xac nhan."""
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning(i18n.translate(APP_TITLE_KEY), i18n.translate("template.dialog.no_selection"), parent=self)
            return
        tpl_id = sel[0]
        record = next((r for r in self._records if r.get("id") == tpl_id), None)
        if not record:
            return
        if not messagebox.askyesno(
            i18n.translate(APP_TITLE_KEY),
            i18n.translate("template.dialog.confirm_delete"),
            parent=self,
        ):
            return
        templates.remove_template(tpl_id)
        self._load_templates()

    def _on_close(self):
        """Dong hop thoai thu vien template."""
        self.result = None
        self.destroy()

    def destroy(self):
        """Huy toplevel va bo listener ngon ngu."""
        if hasattr(self, "_lang_listener"):
            i18n.remove_listener(self._lang_listener)
        super().destroy()

    def _set_icon(self) -> None:
        """Ap dung bieu tuong neu co."""
        try:
            self.iconbitmap("icons/logo.ico")
        except Exception:
            pass
