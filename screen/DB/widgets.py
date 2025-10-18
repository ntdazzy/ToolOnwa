# -*- coding: utf-8 -*-
"""
Bộ widget tái sử dụng cho các màn hình Insert/Update/Backup.
"""
from __future__ import annotations

import csv
import tkinter as tk
from dataclasses import dataclass
from tkinter import filedialog, messagebox, ttk
from typing import Any, Dict, Iterable, List, Optional, Sequence

from core import i18n


def _t(key: str, **kwargs) -> str:
    """Tra cứu chuỗi i18n phục vụ cho widget dùng chung."""
    return i18n.translate(key, **kwargs)


def _clipboard_set(widget: tk.Widget, text: str) -> None:
    """Ghi nội dung vào clipboard của widget chỉ định."""
    widget.clipboard_clear()
    widget.clipboard_append(text)


def _normalize_headers(headers: Sequence[str]) -> List[str]:
    """Chuẩn hóa danh sách header thành dạng chuỗi sạch."""
    return [str(h).strip() for h in headers]


_excel_style_initialized = False


def _ensure_excel_style(master: Optional[tk.Widget] = None) -> None:
    """Đảm bảo Treeview hiển thị theo phong cách dạng lưới giống Excel."""
    global _excel_style_initialized
    if _excel_style_initialized:
        return
    try:
        style = ttk.Style(master)
        try:
            if style.theme_use() == "default":
                style.theme_use("clam")
        except tk.TclError:
            pass
        base_config: Dict[str, Any] = {
            "background": "#FFFFFF",
            "fieldbackground": "#FFFFFF",
            "foreground": "#111827",
            "rowheight": 24,
        }
        border_config: Dict[str, Any] = {
            "borderwidth": 1,
            "relief": "solid",
            "bordercolor": "#CBD5F5",
            "lightcolor": "#CBD5F5",
            "darkcolor": "#CBD5F5",
        }
        style.configure("Excel.Treeview", **base_config, **border_config)
        style.configure(
            "Excel.Treeview.Heading",
            background="#F1F5F9",
            foreground="#0F172A",
            borderwidth=1,
            relief="solid",
        )
        try:
            style.map(
                "Excel.Treeview",
                background=[("selected", "#DBEAFE")],
                foreground=[("selected", "#0F172A")],
            )
            style.map(
                "Excel.Treeview.Heading",
                background=[("active", "#E2E8F0"), ("pressed", "#CBD5F5")],
            )
        except tk.TclError:
            pass
    finally:
        _excel_style_initialized = True


class LoadingPopup:
    """Popup hiển thị trạng thái đang xử lý với thanh tiến trình."""

    def __init__(self, parent: tk.Widget, message: str | None = None):
        """Khởi tạo popup và căn giữa theo cửa sổ cha."""
        self._parent = parent
        self._window = tk.Toplevel(parent)
        self._window.transient(parent)
        self._window.title(_t("widget.loading.title"))
        self._window.resizable(False, False)
        self._window.protocol("WM_DELETE_WINDOW", lambda: None)

        frame = ttk.Frame(self._window, padding=16)
        frame.pack(fill="both", expand=True)
        display_message = message or _t("widget.loading.message")
        ttk.Label(frame, text=display_message, anchor="center").pack(fill="x")
        self._progress = ttk.Progressbar(frame, mode="indeterminate", length=220)
        self._progress.pack(fill="x", pady=(12, 0))
        self._progress.start(12)

        try:
            parent.update_idletasks()
            self._window.update_idletasks()
            w = self._window.winfo_width()
            h = self._window.winfo_height()
            if w == 1 and h == 1:
                w = self._window.winfo_reqwidth()
                h = self._window.winfo_reqheight()
            x = parent.winfo_rootx() + (parent.winfo_width() - w) // 2
            y = parent.winfo_rooty() + (parent.winfo_height() - h) // 2
            self._window.geometry(f"+{x}+{y}")
        except Exception:
            pass

        try:
            self._window.grab_set()
        except Exception:
            pass

    def close(self):
        """Đóng popup và giải phóng tài nguyên."""
        try:
            if self._progress:
                self._progress.stop()
        except Exception:
            pass
        if self._window:
            try:
                self._window.grab_release()
            except Exception:
                pass
            try:
                self._window.destroy()
            except Exception:
                pass
        self._window = None
        self._progress = None


class EditableTreeview(ttk.Treeview):
    """Treeview cho phép chỉnh sửa trực tiếp và thao tác clipboard."""

    def __init__(self, master: tk.Widget, **kwargs):
        super().__init__(master, show="headings", selectmode="extended", **kwargs)
        self._editor: Optional[tk.Entry] = None
        self._editor_item: Optional[str] = None
        self._editor_column: Optional[str] = None
        self._current_item: Optional[str] = None
        self._current_column: Optional[str] = None

        self.bind("<Double-1>", self._on_double_click)
        self.bind("<Return>", self._on_return)
        self.bind("<Escape>", self._close_editor)
        self.bind("<Button-1>", self._on_click, add="+")
        self.bind("<ButtonRelease-1>", self._on_release, add="+")
        self.bind("<Control-c>", self._copy_selection)
        self.bind("<Control-a>", self._select_all)
        self.bind("<Control-v>", self._paste_clipboard)
        self.bind("<Tab>", self._on_tab, add="+")
        self.bind("<Shift-Tab>", self._on_shift_tab, add="+")
        self.bind("<ISO_Left_Tab>", self._on_shift_tab, add="+")
        self.bind("<Key>", self._on_key_press, add="+")
        self.bind("<<TreeviewSelect>>", self._on_tree_select, add="+")

        self._dragging = False
        self._last_click_region = ""
        self._editing_tag = "grid-row-editing"
        self._new_row_tag = "grid-row-new"
        self.tag_configure("grid-row-even", background="#FFFFFF")
        self.tag_configure("grid-row-odd", background="#F8FAFF")
        self.tag_configure(self._editing_tag, background="#E0ECFF")
        self.tag_configure(self._new_row_tag, background="#FEF3C7")

    # ---- editing -------------------------------------------------
    def _on_double_click(self, event):
        region = self.identify("region", event.x, event.y)
        if region != "cell":
            return
        row_id = self.identify_row(event.y)
        col_id = self.identify_column(event.x)
        if row_id:
            self._set_current_cell(row_id, col_id)
            self._open_editor(row_id, self._current_column or col_id)

    def _on_return(self, event):
        sel = self.selection()
        if not sel:
            return "break"
        row_id = sel[0]
        columns = list(self["columns"])
        column = self._current_column or (columns[0] if columns else None)
        if column:
            self._open_editor(row_id, column)
        return "break"

    def _on_click(self, event):
        region = self.identify("region", event.x, event.y)
        self._last_click_region = region
        if region == "cell":
            row_id = self.identify_row(event.y)
            col_id = self.identify_column(event.x)
            if row_id:
                self._set_current_cell(row_id, col_id)
        else:
            self._save_editor()

    def _on_release(self, _event):
        if self._last_click_region != "cell":
            self._save_editor()

    def _column_from_identifier(self, column_id: Optional[str]) -> Optional[str]:
        """Convert Treeview column identifier (#1) về tên cột."""
        if not column_id:
            return None
        columns = list(self["columns"])
        if column_id.startswith("#"):
            try:
                index = int(column_id[1:]) - 1
            except ValueError:
                return None
            if 0 <= index < len(columns):
                return columns[index]
            return None
        return column_id if column_id in columns else None

    def _set_current_cell(self, item: Optional[str], column_id: Optional[str]) -> None:
        """Ghi nhận vị trí ô hiện tại để phục vụ điều hướng."""
        if not item:
            return
        column_name = self._column_from_identifier(column_id)
        columns = list(self["columns"])
        if not column_name and columns:
            column_name = columns[0]
        self._current_item = item
        self._current_column = column_name
        try:
            self.selection_set(item)
            self.focus(item)
            self.see(item)
        except tk.TclError:
            pass

    def _focus_current_cell(self) -> None:
        if not self._current_item:
            return
        try:
            self.selection_set(self._current_item)
            self.focus(self._current_item)
            self.see(self._current_item)
        except tk.TclError:
            pass

    def _on_tree_select(self, _event):
        """Cập nhật ô hiện tại khi người dùng chọn dòng mới."""
        self._highlight_selection()
        sel = self.selection()
        if sel:
            self._current_item = sel[0]
            columns = list(self["columns"])
            if self._current_column not in columns and columns:
                self._current_column = columns[0]

    def _advance_cell(self, forward: bool, *, wrap: bool = True) -> bool:
        """Di chuyển sang ô kế tiếp / trước giống Excel."""
        columns = list(self["columns"])
        rows = list(self.get_children(""))
        if not columns or not rows:
            return False
        item = self._current_item if self._current_item in rows else (self.selection()[0] if self.selection() else rows[0])
        column = self._current_column if self._current_column in columns else columns[0]
        row_idx = rows.index(item)
        col_idx = columns.index(column)
        if forward:
            if col_idx < len(columns) - 1:
                col_idx += 1
            elif wrap and row_idx < len(rows) - 1:
                row_idx += 1
                col_idx = 0
            else:
                if not wrap:
                    return False
                col_idx = len(columns) - 1
        else:
            if col_idx > 0:
                col_idx -= 1
            elif wrap and row_idx > 0:
                row_idx -= 1
                col_idx = len(columns) - 1
            else:
                if not wrap:
                    return False
                col_idx = 0
        self._current_item = rows[row_idx]
        self._current_column = columns[col_idx]
        self._focus_current_cell()
        return True

    def _move_vertical(self, offset: int) -> bool:
        """Di chuyển lên/xuống theo số dòng offset."""
        if offset == 0:
            return False
        rows = list(self.get_children(""))
        if not rows:
            return False
        item = self._current_item if self._current_item in rows else (self.selection()[0] if self.selection() else rows[0])
        row_idx = rows.index(item)
        new_idx = min(max(row_idx + offset, 0), len(rows) - 1)
        if new_idx == row_idx:
            return False
        self._current_item = rows[new_idx]
        columns = list(self["columns"])
        if self._current_column not in columns and columns:
            self._current_column = columns[0]
        self._focus_current_cell()
        return True

    def _begin_edit_current_cell(self) -> None:
        if self._current_item and self._current_column:
            self._open_editor(self._current_item, self._current_column)

    def _on_tab(self, _event):
        if self._editor:
            return None
        self._save_editor()
        if self._advance_cell(True):
            self._focus_current_cell()
        return "break"

    def _on_shift_tab(self, _event):
        if self._editor:
            return None
        self._save_editor()
        if self._advance_cell(False):
            self._focus_current_cell()
        return "break"

    def _cycle_from_editor(self, forward: bool):
        self._save_editor()
        if self._advance_cell(forward):
            self._begin_edit_current_cell()
        return "break"

    def _move_editor_vertical(self, offset: int):
        self._save_editor()
        if self._move_vertical(offset):
            self._begin_edit_current_cell()
        return "break"

    def _on_key_press(self, event):
        if self._editor:
            return None
        keysym = event.keysym
        if keysym in {"Shift_L", "Shift_R", "Control_L", "Control_R", "Alt_L", "Alt_R"}:
            return None
        if keysym in {"Up", "Down"}:
            if self._move_vertical(-1 if keysym == "Up" else 1):
                return "break"
            return None
        if keysym in {"Left", "Right"}:
            if self._advance_cell(keysym == "Right", wrap=False):
                self._focus_current_cell()
                return "break"
            return None
        if keysym in {"Tab", "ISO_Left_Tab"}:
            return "break"
        char = event.char or ""
        if char and char.isprintable() and not (event.state & 0x0004) and not (event.state & 0x0008):
            columns = list(self["columns"])
            if not columns:
                return "break"
            if not self.selection():
                rows = self.get_children("")
                if not rows:
                    return "break"
                self.selection_set(rows[0])
                self._set_current_cell(rows[0], columns[0])
            if not self._current_column:
                self._current_column = columns[0]
            sel = self.selection()
            if not sel:
                return "break"
            self._begin_edit_current_cell()
            if self._editor:
                self._editor.delete(0, tk.END)
                self._editor.insert(0, char)
                self._editor.icursor(tk.END)
            return "break"
        return None

    def _open_editor(self, item: str, column: str):
        if not item or not column:
            return
        bbox = self.bbox(item, column)
        if not bbox:
            return
        self._set_current_cell(item, column)
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
        editor.bind("<Tab>", lambda e: self._cycle_from_editor(True))
        editor.bind("<Shift-Tab>", lambda e: self._cycle_from_editor(False))
        editor.bind("<ISO_Left_Tab>", lambda e: self._cycle_from_editor(False))
        editor.bind("<Down>", lambda e: self._move_editor_vertical(1))
        editor.bind("<Up>", lambda e: self._move_editor_vertical(-1))
        self._editor = editor
        self._editor_item = item
        self._editor_column = column
        self._flag_editing_row(item, True)

    def _save_editor(self):
        if not self._editor:
            return
        value = self._editor.get()
        item = self._editor_item
        column = self._editor_column
        if item and column:
            self.set(item, column, value)
            self._set_current_cell(item, column)
        self._close_editor()
        self.refresh_striping()

    def _close_editor(self, *_):
        item = self._editor_item
        if self._editor:
            self._editor.destroy()
        self._editor = None
        self._editor_item = None
        self._editor_column = None
        if item:
            self._clear_editing_tags(item)
        else:
            self.refresh_striping()

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
            self._append_row(values, mark_new=True)
        self.refresh_striping()
        return "break"

    # ---- data helpers ---------------------------------------------
    def configure_columns(self, columns: Sequence[str]):
        cols = _normalize_headers(columns)
        self["columns"] = cols
        for col in cols:
            self.heading(col, text=col, anchor="w")
            self.column(col, width=120, minwidth=80, stretch=True, anchor="w")
        self._close_editor()
        self.refresh_striping()

    def clear(self):
        self._close_editor()
        for item in self.get_children(""):
            self.delete(item)
        self.refresh_striping()

    def set_data(self, rows: Iterable[Dict[str, Any]]):
        self.clear()
        for row in rows:
            self._append_row(row, mark_new=False)
        self.refresh_striping()

    def append_dict(self, row: Dict[str, Any], *, mark_new: bool = True):
        self._append_row(row, mark_new=mark_new)
        self.refresh_striping()

    def _append_row(self, row: Dict[str, Any], *, mark_new: bool = True):
        iid = self.insert("", "end")
        if mark_new:
            tags = list(self.item(iid, "tags"))
            if self._new_row_tag not in tags:
                tags.append(self._new_row_tag)
                self.item(iid, tags=tags)
        for col in self["columns"]:
            val = row.get(col, "")
            self.set(iid, col, "" if val is None else str(val))
        return iid

    def refresh_striping(self):
        """Áp dụng màu nền xen kẽ giúp lưới dễ theo dõi."""
        editing_item = self._editor_item
        for idx, item in enumerate(self.get_children("")):
            if editing_item and item == editing_item:
                continue
            tags = [t for t in self.item(item, "tags") if t != self._editing_tag]
            tags = [t for t in tags if t not in ("grid-row-even", "grid-row-odd")]
            if self._new_row_tag not in tags:
                tags.append("grid-row-even" if idx % 2 else "grid-row-odd")
            self.item(item, tags=tags)

    def _flag_editing_row(self, item: str, editing: bool):
        """Đánh dấu hàng đang chỉnh sửa để giữ highlight ngay cả khi zebra chạy lại."""
        if not item:
            return
        tags = [t for t in self.item(item, "tags") if t not in ("grid-row-even", "grid-row-odd", self._editing_tag)]
        try:
            idx = self.index(item)
        except tk.TclError:
            idx = 0
        zebra = "grid-row-even" if idx % 2 else "grid-row-odd"
        tags.append(zebra)
        if editing:
            tags.append(self._editing_tag)
        self.item(item, tags=tags)

    def _clear_editing_tags(self, item: Optional[str] = None):
        if item:
            items = [item]
        else:
            items = list(self.get_children(""))
        for iid in items:
            tags = [t for t in self.item(iid, "tags") if t != self._editing_tag]
            tags = [t for t in tags if t not in ("grid-row-even", "grid-row-odd")]
            try:
                idx = self.index(iid)
            except tk.TclError:
                idx = 0
            if self._new_row_tag not in tags:
                tags.append("grid-row-even" if idx % 2 else "grid-row-odd")
            self.item(iid, tags=tags)

    def _highlight_selection(self):
        for item in self.selection():
            try:
                self.see(item)
            except tk.TclError:
                continue

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
            self._append_row(values, mark_new=True)
        self.refresh_striping()


class DataGrid(ttk.Frame):
    """
    Composite widget that wraps EditableTreeview with scrollbars and context menu.
    """

    def __init__(self, master: tk.Widget, **kwargs):
        super().__init__(master)
        _ensure_excel_style(self)
        self.tree = EditableTreeview(self, **kwargs)
        try:
            self.tree.configure(style="Excel.Treeview")
        except tk.TclError:
            pass

        vsb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(self, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscroll=vsb.set, xscroll=hsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._popup = tk.Menu(self, tearoff=False)
        self._configure_menu()

        self.tree.bind("<Button-3>", self._show_popup)
        self.tree.bind("<Delete>", lambda e: self._delete_selected() or "break")

    def _show_popup(self, event):
        """Hiển thị menu ngữ cảnh tại vị trí chuột."""
        try:
            self._popup.tk_popup(event.x_root, event.y_root)  # type: ignore[attr-defined]
        finally:
            self._popup.grab_release()

    def _delete_selected(self):
        """Xóa các dòng được chọn trong treeview."""
        sel = self.tree.selection()
        for item in sel:
            self.tree.delete(item)
        self.tree.refresh_striping()

    # proxied helpers
    def configure_columns(self, columns: Sequence[str]):
        self.tree.configure_columns(columns)

    def clear(self):
        self.tree.clear()

    def set_data(self, rows: Iterable[Dict[str, Any]]):
        self.tree.set_data(rows)

    def append_dict(self, row: Dict[str, Any], *, mark_new: bool = True):
        self.tree.append_dict(row, mark_new=mark_new)

    def get_all(self) -> List[Dict[str, Any]]:
        """Trả về toàn bộ dữ liệu hiện có trong lưới."""
        return self.tree.get_all()

    def import_csv_dialog(self):
        """Mở hộp thoại chọn CSV và nạp dữ liệu vào lưới."""
        path = filedialog.askopenfilename(
            title=_t("grid.dialog.open_csv"),
            filetypes=[(_t("backup.dialog.csv_files"), "*.csv"), (_t("backup.dialog.all_files"), "*.*")],
            parent=self,
        )
        if not path:
            return
        try:
            self.tree.import_csv(path)
        except Exception as exc:
            messagebox.showerror(
                _t("common.app_title"),
                _t("grid.msg.read_csv_error", error=str(exc)),
            )

    def export_csv_dialog(self):
        """Mở hộp thoại lưu CSV và ghi dữ liệu hiện có."""
        path = filedialog.asksaveasfilename(
            title=_t("grid.dialog.save_csv"),
            defaultextension=".csv",
            filetypes=[(_t("backup.dialog.csv_files"), "*.csv"), (_t("backup.dialog.all_files"), "*.*")],
            parent=self,
        )
        if not path:
            return
        try:
            self.tree.export_csv(path)
        except Exception as exc:
            messagebox.showerror(
                _t("common.app_title"),
                _t("grid.msg.write_csv_error", error=str(exc)),
            )

    def _configure_menu(self) -> None:
        """Cấu hình lại thực đơn ngữ cảnh theo ngôn ngữ hiện tại."""
        try:
            if self._popup.index("end") is not None:
                self._popup.delete(0, "end")
        except tk.TclError:
            pass
        self._popup.add_command(
            label=_t("grid.menu.copy_rows"),
            command=lambda: self.tree._copy_selection(include_headers=False),
        )
        self._popup.add_command(
            label=_t("grid.menu.copy_rows_header"),
            command=lambda: self.tree._copy_selection(include_headers=True),
        )
        self._popup.add_separator()
        self._popup.add_command(
            label=_t("grid.menu.copy_all"),
            command=lambda: self.tree.copy_all(include_headers=True),
        )
        self._popup.add_separator()
        self._popup.add_command(label=_t("grid.menu.paste"), command=self.tree._paste_clipboard)
        self._popup.add_command(
            label=_t("grid.menu.delete_rows"),
            command=self._delete_selected,
            accelerator="Del",
        )

    def apply_language(self) -> None:
        """Cập nhật lại ngôn ngữ cho menu ngữ cảnh."""
        self._configure_menu()


@dataclass
class DuplicateRow:
    pk_values: str
    data: Dict[str, Any]


class DuplicatePreviewDialog(tk.Toplevel):
    """Hiển thị dữ liệu trùng để người dùng xác nhận ghi đè."""

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
        self.title(_t("grid.duplicate.title"))
        self.geometry("900x520")
        self.minsize(720, 420)
        self.transient(parent)
        self.grab_set()

        self.result: Optional[bool] = None

        info = ttk.Label(
            self,
            text=_t("grid.duplicate.message"),
            anchor="w",
            wraplength=860,
        )
        info.pack(fill="x", padx=12, pady=(12, 6))

        header = ttk.Frame(self)
        header.pack(fill="x", padx=12, pady=(0, 6))
        ttk.Label(
            header,
            text=_t("grid.duplicate.table", table=table_name),
            font=("TkDefaultFont", 10, "bold"),
        ).pack(side="left")
        ttk.Label(header, text=_t("grid.duplicate.pk", keys=", ".join(pk_columns))).pack(side="right")

        main = ttk.Panedwindow(self, orient="vertical")
        main.pack(fill="both", expand=True, padx=12, pady=6)

        self.user_grid = self._create_tree(main, columns, title=_t("grid.duplicate.user_data"))
        self.db_grid = self._create_tree(main, columns, title=_t("grid.duplicate.database_data"))

        self._populate(self.user_grid, user_rows, db_rows, columns, pk_columns)
        self._populate(self.db_grid, db_rows, user_rows, columns, pk_columns)

        btns = ttk.Frame(self)
        btns.pack(fill="x", padx=12, pady=(0, 12))
        btns.columnconfigure(0, weight=1)
        ttk.Button(btns, text=_t("common.cancel"), command=self._cancel, width=12).grid(row=0, column=1, padx=6)
        ttk.Button(btns, text=_t("common.ok"), command=self._accept, width=12).grid(row=0, column=2, padx=6)

        self.protocol("WM_DELETE_WINDOW", self._cancel)

    def _create_tree(self, parent, columns, title):
        """Tạo treeview hiển thị dữ liệu với nhãn tiêu đề tương ứng."""
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
        """Đổ dữ liệu vào treeview và đánh dấu các dòng khác biệt."""
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
        """Tạo khóa tuple từ các cột khóa chính."""
        return tuple("" if row.get(pk) is None else str(row.get(pk)) for pk in pk_columns)

    def _accept(self):
        """Xác nhận ghi đè dữ liệu."""
        self.result = True
        self.destroy()

    def _cancel(self):
        """Hủy thao tác và đóng dialog."""
        self.result = False
        self.destroy()


class ColumnOrderDialog(tk.Toplevel):
    """Cho phép kéo thả để thay đổi thứ tự các cột."""

    def __init__(self, parent: tk.Widget, columns: Sequence[str]):
        super().__init__(parent)
        self.title(_t("grid.order.title"))
        self.geometry("360x460")
        self.minsize(340, 380)
        self.transient(parent)
        self.grab_set()

        self._initial = list(columns)
        self._columns = list(columns)
        self._flash_after_id: Optional[str] = None

        ttk.Label(self, text=_t("grid.order.hint")).pack(padx=12, pady=(12, 6), anchor="w")

        container = ttk.Frame(self)
        container.pack(fill="both", expand=True, padx=12, pady=(0, 6))
        container.columnconfigure(0, weight=1)
        container.rowconfigure(0, weight=1)

        self.listbox = tk.Listbox(container, selectmode=tk.SINGLE, activestyle="dotbox", exportselection=False)
        self.listbox.grid(row=0, column=0, sticky="nsew")
        self._populate_listbox()

        scrollbar = ttk.Scrollbar(container, orient="vertical", command=self.listbox.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.listbox.configure(yscrollcommand=scrollbar.set)

        move_panel = ttk.Frame(container)
        move_panel.grid(row=0, column=2, sticky="ns", padx=(6, 0))
        ttk.Button(move_panel, text=_t("grid.order.move_up"), command=lambda: self._move_selected(-1), width=14).pack(
            pady=(0, 8)
        )
        ttk.Button(move_panel, text=_t("grid.order.move_down"), command=lambda: self._move_selected(1), width=14).pack()

        self.listbox.bind("<ButtonPress-1>", self._on_press)
        self.listbox.bind("<B1-Motion>", self._on_motion)
        self.listbox.bind("<ButtonRelease-1>", self._on_release)
        self.listbox.bind("<Double-Button-1>", lambda _e: self._move_selected(1))
        self.listbox.bind("<Control-Up>", lambda _e: (self._move_selected(-1), "break"))
        self.listbox.bind("<Control-Down>", lambda _e: (self._move_selected(1), "break"))
        self.listbox.bind("<KeyPress-U>", lambda _e: (self._move_selected(-1), "break"))
        self.listbox.bind("<KeyPress-D>", lambda _e: (self._move_selected(1), "break"))

        btns = ttk.Frame(self)
        btns.pack(fill="x", padx=12, pady=(0, 12))
        ttk.Button(btns, text=_t("common.reset"), command=self._reset).pack(side="left")
        ttk.Button(btns, text=_t("common.cancel"), command=self._cancel).pack(side="right", padx=(6, 0))
        ttk.Button(btns, text=_t("common.ok"), command=self._accept).pack(side="right")

        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self._drag_index: Optional[int] = None

        self.result: Optional[List[str]] = None

    def _populate_listbox(self):
        """Đổ dữ liệu cột kèm số thứ tự vào listbox."""
        self.listbox.delete(0, tk.END)
        for idx, col in enumerate(self._columns, start=1):
            self.listbox.insert(tk.END, f"{idx}. {col}")

    def _on_press(self, event):
        """Ghi nhận vị trí dòng được kéo."""
        self._drag_index = self.listbox.nearest(event.y)

    def _on_motion(self, event):
        """Di chuyển dòng theo vị trí chuột khi kéo."""
        if self._drag_index is None:
            return
        new_index = self.listbox.nearest(event.y)
        if new_index == self._drag_index:
            return
        value = self._columns.pop(self._drag_index)
        self._columns.insert(new_index, value)
        self._populate_listbox()
        self.listbox.selection_clear(0, tk.END)
        self.listbox.selection_set(new_index)
        self._drag_index = new_index
        self._flash_row(new_index)

    def _on_release(self, _event):
        """Kết thúc thao tác kéo thả."""
        self._drag_index = None

    def _reset(self):
        """Khôi phục lại thứ tự cột ban đầu."""
        self._columns = list(self._initial)
        self._populate_listbox()
        if self._columns:
            self.listbox.selection_set(0)
            self._flash_row(0)

    def _accept(self):
        """Xác nhận và trả về danh sách cột theo thứ tự mới."""
        self.result = list(self._columns)
        self.destroy()

    def _cancel(self):
        """Đóng dialog và không thay đổi thứ tự cột."""
        self.result = None
        self.destroy()

    def _move_selected(self, offset: int):
        """Di chuyển phần tử được chọn lên/xuống."""
        if offset == 0 or not self._columns:
            return
        selection = self.listbox.curselection()
        if not selection:
            return
        index = selection[0]
        target = index + offset
        if target < 0 or target >= len(self._columns):
            return
        self._columns[index], self._columns[target] = self._columns[target], self._columns[index]
        self._populate_listbox()
        self.listbox.selection_set(target)
        self.listbox.see(target)
        self._flash_row(target)

    def _flash_row(self, index: int):
        """Tạo hiệu ứng highlight nhẹ tại vị trí mới."""
        if index < 0 or index >= len(self._columns):
            return
        if self._flash_after_id:
            try:
                self.after_cancel(self._flash_after_id)
            except Exception:
                pass
            finally:
                self._flash_after_id = None

        colors = ["#E0ECFF", "#FFFFFF", "#E0ECFF", "#FFFFFF"]

        def _animate(step: int = 0):
            if step >= len(colors):
                try:
                    self.listbox.itemconfig(index, background="")
                except Exception:
                    pass
                return
            try:
                self.listbox.itemconfig(index, background=colors[step])
            except Exception:
                return
            self._flash_after_id = self.after(70, _animate, step + 1)

        _animate()
