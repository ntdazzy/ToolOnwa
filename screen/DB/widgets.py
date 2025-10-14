# -*- coding: utf-8 -*-
"""
Reusable Tk widgets for Insert/Update screens.
"""
from __future__ import annotations

import csv
import tkinter as tk
from dataclasses import dataclass
from tkinter import filedialog, messagebox, ttk
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence


def _clipboard_set(widget: tk.Widget, text: str) -> None:
    widget.clipboard_clear()
    widget.clipboard_append(text)


def _normalize_headers(headers: Sequence[str]) -> List[str]:
    return [str(h).strip() for h in headers]


class EditableTreeview(ttk.Treeview):
    """
    Treeview with in-place editing and clipboard support.
    """

    def __init__(self, master: tk.Widget, **kwargs):
        super().__init__(master, show="headings", selectmode="extended", **kwargs)
        self._editor: Optional[tk.Entry] = None
        self._editor_item: Optional[str] = None
        self._editor_column: Optional[str] = None

        self.bind("<Double-1>", self._on_double_click)
        self.bind("<Return>", self._on_return)
        self.bind("<Escape>", self._close_editor)
        self.bind("<Button-1>", self._on_click, add="+")
        self.bind("<ButtonRelease-1>", self._on_release, add="+")
        self.bind("<Control-c>", self._copy_selection)
        self.bind("<Control-a>", self._select_all)
        self.bind("<Control-v>", self._paste_clipboard)

        self._dragging = False
        self._last_click_region = ""

    # ---- editing -------------------------------------------------
    def _on_double_click(self, event):
        region = self.identify("region", event.x, event.y)
        if region != "cell":
            return
        row_id = self.identify_row(event.y)
        col_id = self.identify_column(event.x)
        self._open_editor(row_id, col_id)

    def _on_return(self, event):
        sel = self.selection()
        if not sel:
            return "break"
        row_id = sel[0]
        col_id = self.focus_column() or self["columns"][0]
        self._open_editor(row_id, col_id)
        return "break"

    def _on_click(self, event):
        region = self.identify("region", event.x, event.y)
        self._last_click_region = region
        if region != "cell":
            self._close_editor()

    def _on_release(self, _event):
        if self._last_click_region != "cell":
            self._close_editor()

    def _open_editor(self, item: str, column: str):
        if not item or not column:
            return
        bbox = self.bbox(item, column)
        if not bbox:
            return
        self._close_editor()
        x, y, w, h = bbox
        value = self.set(item, column)
        editor = tk.Entry(self)
        editor.insert(0, value)
        editor.select_range(0, tk.END)
        editor.focus()
        editor.place(x=x, y=y, width=w, height=h)
        editor.bind("<Return>", lambda e: self._save_editor())
        editor.bind("<Escape>", lambda e: self._close_editor())
        editor.bind("<FocusOut>", lambda e: self._save_editor())
        self._editor = editor
        self._editor_item = item
        self._editor_column = column

    def _save_editor(self):
        if not self._editor:
            return
        value = self._editor.get()
        if self._editor_item and self._editor_column:
            self.set(self._editor_item, self._editor_column, value)
        self._close_editor()

    def _close_editor(self, *_):
        if self._editor:
            self._editor.destroy()
        self._editor = None
        self._editor_item = None
        self._editor_column = None

    # ---- clipboard ------------------------------------------------
    def _select_all(self, _event):
        self.selection_set(self.get_children(""))
        return "break"

    def _copy_selection(self, _event=None, include_headers: bool = False):
        items = self.selection()
        if not items:
            return "break"
        data = []
        headers = self["columns"]
        if include_headers:
            data.append("\t".join(headers))
        for item in items:
            row = [self.set(item, col) for col in headers]
            data.append("\t".join(row))
        _clipboard_set(self, "\n".join(data))
        return "break"

    def copy_all(self, include_headers: bool = True):
        headers = self["columns"]
        data = []
        if include_headers:
            data.append("\t".join(headers))
        for item in self.get_children(""):
            row = [self.set(item, col) for col in headers]
            data.append("\t".join(row))
        _clipboard_set(self, "\n".join(data))

    def _paste_clipboard(self, _event=None):
        try:
            text = self.clipboard_get()
        except tk.TclError:
            return "break"
        if not text:
            return "break"
        rows = [line for line in text.splitlines() if line.strip()]
        if not rows:
            return "break"
        headers = self["columns"]
        first = rows[0].split("\t")
        use_header = False
        if len(first) == len(headers) and all(h.upper() == c.strip().upper() for h, c in zip(headers, first)):
            use_header = True
        start_idx = 1 if use_header else 0
        for row_text in rows[start_idx:]:
            parts = row_text.split("\t")
            values = {}
            for idx, col in enumerate(headers):
                values[col] = parts[idx] if idx < len(parts) else ""
            self._append_row(values)
        return "break"

    # ---- data helpers ---------------------------------------------
    def configure_columns(self, columns: Sequence[str]):
        cols = _normalize_headers(columns)
        self["columns"] = cols
        for col in cols:
            self.heading(col, text=col, anchor="w")
            self.column(col, width=120, minwidth=80, stretch=True, anchor="w")
        self._close_editor()

    def clear(self):
        self._close_editor()
        for item in self.get_children(""):
            self.delete(item)

    def set_data(self, rows: Iterable[Dict[str, Any]]):
        self.clear()
        for idx, row in enumerate(rows):
            values = [str(row.get(col, "")) if row.get(col) is not None else "" for col in self["columns"]]
            self.insert("", "end", iid=f"row{idx}", values=values)

    def append_dict(self, row: Dict[str, Any]):
        self._append_row(row)

    def _append_row(self, row: Dict[str, Any]):
        iid = self.insert("", "end")
        for col in self["columns"]:
            val = row.get(col, "")
            self.set(iid, col, "" if val is None else str(val))

    def get_all(self) -> List[Dict[str, Any]]:
        result = []
        for item in self.get_children(""):
            row = {col: self.set(item, col) for col in self["columns"]}
            if all(value == "" for value in row.values()):
                continue
            result.append(row)
        return result

    def export_csv(self, path: str):
        headers = list(self["columns"])
        with open(path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            for item in self.get_children(""):
                writer.writerow([self.set(item, col) for col in headers])

    def import_csv(self, path: str, has_header: bool = True):
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            rows = list(reader)
        if not rows:
            return
        if has_header:
            header = rows[0]
            if len(header) == len(self["columns"]):
                for col, head in zip(self["columns"], header):
                    self.heading(col, text=head or col)
            data_rows = rows[1:]
        else:
            data_rows = rows
        self.clear()
        for idx, data_row in enumerate(data_rows):
            values = {}
            for col_index, col in enumerate(self["columns"]):
                values[col] = data_row[col_index] if col_index < len(data_row) else ""
            self._append_row(values)


class DataGrid(ttk.Frame):
    """
    Composite widget that wraps EditableTreeview with scrollbars and context menu.
    """

    def __init__(self, master: tk.Widget, **kwargs):
        super().__init__(master)
        self.tree = EditableTreeview(self, **kwargs)

        vsb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(self, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscroll=vsb.set, xscroll=hsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._popup = tk.Menu(self, tearoff=False)
        self._popup.add_command(label="Copy row(s)", command=lambda: self.tree._copy_selection(include_headers=False))
        self._popup.add_command(label="Copy row(s) + header", command=lambda: self.tree._copy_selection(include_headers=True))
        self._popup.add_separator()
        self._popup.add_command(label="Copy all", command=lambda: self.tree.copy_all(include_headers=True))
        self._popup.add_separator()
        self._popup.add_command(label="Paste", command=self.tree._paste_clipboard)
        self._popup.add_command(
            label="Delete row(s)", command=self._delete_selected, accelerator="Del"
        )

        self.tree.bind("<Button-3>", self._show_popup)
        self.tree.bind("<Delete>", lambda e: self._delete_selected() or "break")

    def _show_popup(self, event):
        try:
            self._popup.tk_popup(event.x_root, event.y_root)  # type: ignore[attr-defined]
        finally:
            self._popup.grab_release()

    def _delete_selected(self):
        sel = self.tree.selection()
        for item in sel:
            self.tree.delete(item)

    # proxied helpers
    def configure_columns(self, columns: Sequence[str]):
        self.tree.configure_columns(columns)

    def clear(self):
        self.tree.clear()

    def set_data(self, rows: Iterable[Dict[str, Any]]):
        self.tree.set_data(rows)

    def append_dict(self, row: Dict[str, Any]):
        self.tree.append_dict(row)

    def get_all(self) -> List[Dict[str, Any]]:
        return self.tree.get_all()

    def import_csv_dialog(self):
        path = filedialog.askopenfilename(
            title="Chọn file CSV", filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if not path:
            return
        try:
            self.tree.import_csv(path)
        except Exception as exc:
            messagebox.showerror("Tool VIP", f"Lỗi đọc file CSV: {exc}")

    def export_csv_dialog(self):
        path = filedialog.asksaveasfilename(
            title="Lưu file CSV",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            self.tree.export_csv(path)
        except Exception as exc:
            messagebox.showerror("Tool VIP", f"Lỗi ghi file CSV: {exc}")


@dataclass
class DuplicateRow:
    pk_values: str
    data: Dict[str, Any]


class DuplicatePreviewDialog(tk.Toplevel):
    """
    Shows duplicates between user data and database data for confirmation.
    """

    def __init__(
        self,
        parent: tk.Widget,
        *,
        table_name: str,
        columns: Sequence[str],
        pk_columns: Sequence[str],
        user_rows: Sequence[Dict[str, Any]],
        db_rows: Sequence[Dict[str, Any]],
    ):
        super().__init__(parent)
        self.title("Cảnh báo dữ liệu trùng")
        self.geometry("900x520")
        self.minsize(720, 420)
        self.transient(parent)
        self.grab_set()

        self.result: Optional[bool] = None

        info = ttk.Label(
            self,
            text="Đã có dữ liệu trùng khóa chính. Bạn có muốn ghi đè dữ liệu trong database không?",
            anchor="w",
            wraplength=860,
        )
        info.pack(fill="x", padx=12, pady=(12, 6))

        header = ttk.Frame(self)
        header.pack(fill="x", padx=12, pady=(0, 6))
        ttk.Label(header, text=f"Table: {table_name}", font=("TkDefaultFont", 10, "bold")).pack(side="left")
        ttk.Label(header, text=f"Khóa chính: {', '.join(pk_columns)}").pack(side="right")

        main = ttk.Panedwindow(self, orient="vertical")
        main.pack(fill="both", expand=True, padx=12, pady=6)

        self.user_grid = self._create_tree(main, columns, title="Data của bạn")
        self.db_grid = self._create_tree(main, columns, title="Database")

        self._populate(self.user_grid, user_rows, db_rows, columns, pk_columns)
        self._populate(self.db_grid, db_rows, user_rows, columns, pk_columns)

        btns = ttk.Frame(self)
        btns.pack(fill="x", padx=12, pady=(0, 12))
        btns.columnconfigure(0, weight=1)
        ttk.Button(btns, text="Cancel", command=self._cancel, width=12).grid(row=0, column=1, padx=6)
        ttk.Button(btns, text="OK", command=self._accept, width=12).grid(row=0, column=2, padx=6)

        self.protocol("WM_DELETE_WINDOW", self._cancel)

    def _create_tree(self, parent, columns, title):
        frame = ttk.Labelframe(parent, text=title, padding=6)
        parent.add(frame, weight=1)
        tree = EditableTreeview(frame, height=8)
        tree.configure_columns(columns)
        tree.grid(row=0, column=0, sticky="nsew")
        vsb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscroll=vsb.set)
        vsb.grid(row=0, column=1, sticky="ns")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        tree.configure(selectmode="browse")
        tree.bind("<Double-1>", lambda e: "break")  # read-only
        tree.bind("<Return>", lambda e: "break")
        tree.bind("<Key>", lambda e: "break")
        return tree

    def _populate(self, tree: EditableTreeview, rows, other_rows, columns, pk_columns):
        other_lookup = {self._pk_key(pk_columns, row): row for row in other_rows}
        for idx, row in enumerate(rows):
            values = []
            tags = []
            key = self._pk_key(pk_columns, row)
            other_row = other_lookup.get(key)
            diff_cols = []
            for col in columns:
                cur_val = row.get(col, "")
                oth_val = "" if other_row is None else other_row.get(col, "")
                cur_val_str = "" if cur_val is None else str(cur_val)
                oth_val_str = "" if oth_val is None else str(oth_val)
                display = cur_val_str
                if other_row is None:
                    pass
                elif cur_val_str != oth_val_str:
                    diff_cols.append(col)
                values.append(display)
            iid = tree.insert("", "end", iid=f"{tree}_{idx}", values=values)
            if diff_cols:
                tree.tag_configure("diff", background="#ffe4b5")
                tree.item(iid, tags=("diff",))

    @staticmethod
    def _pk_key(pk_columns, row):
        return tuple("" if row.get(pk) is None else str(row.get(pk)) for pk in pk_columns)

    def _accept(self):
        self.result = True
        self.destroy()

    def _cancel(self):
        self.result = False
        self.destroy()


class ColumnOrderDialog(tk.Toplevel):
    """
    Allows reordering of column names via drag and drop.
    """

    def __init__(self, parent: tk.Widget, columns: Sequence[str]):
        super().__init__(parent)
        self.title("Thay đổi vị trí cột")
        self.geometry("320x420")
        self.minsize(300, 360)
        self.transient(parent)
        self.grab_set()

        self._initial = list(columns)
        self._columns = list(columns)

        ttk.Label(self, text="Kéo thả để thay đổi vị trí cột").pack(padx=12, pady=(12, 6), anchor="w")

        self.listbox = tk.Listbox(self, selectmode=tk.SINGLE, activestyle="none")
        self.listbox.pack(fill="both", expand=True, padx=12, pady=6)
        for col in self._columns:
            self.listbox.insert(tk.END, col)

        self.listbox.bind("<ButtonPress-1>", self._on_press)
        self.listbox.bind("<B1-Motion>", self._on_motion)
        self.listbox.bind("<ButtonRelease-1>", self._on_release)

        btns = ttk.Frame(self)
        btns.pack(fill="x", padx=12, pady=(0, 12))
        ttk.Button(btns, text="Reset", command=self._reset).pack(side="left")
        ttk.Button(btns, text="Cancel", command=self._cancel).pack(side="right", padx=(6, 0))
        ttk.Button(btns, text="OK", command=self._accept).pack(side="right")

        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self._drag_index: Optional[int] = None

        self.result: Optional[List[str]] = None

    def _on_press(self, event):
        self._drag_index = self.listbox.nearest(event.y)

    def _on_motion(self, event):
        if self._drag_index is None:
            return
        new_index = self.listbox.nearest(event.y)
        if new_index == self._drag_index:
            return
        value = self.listbox.get(self._drag_index)
        self.listbox.delete(self._drag_index)
        self.listbox.insert(new_index, value)
        self.listbox.selection_clear(0, tk.END)
        self.listbox.selection_set(new_index)
        self._drag_index = new_index

    def _on_release(self, _event):
        self._drag_index = None

    def _reset(self):
        self.listbox.delete(0, tk.END)
        for col in self._initial:
            self.listbox.insert(tk.END, col)

    def _accept(self):
        self.result = [self.listbox.get(idx) for idx in range(self.listbox.size())]
        self.destroy()

    def _cancel(self):
        self.result = None
        self.destroy()
