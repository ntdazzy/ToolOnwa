"""
Data comparison window with two editable grids.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
from typing import List, Sequence, Tuple, Set

from tksheet import Sheet
from core import i18n


def _excel_column_name(idx: int) -> str:
    """Return Excel-style column label (A, B, ..., Z, AA...)."""
    label = ""
    while idx >= 0:
        idx, rem = divmod(idx, 26)
        label = chr(ord("A") + rem) + label
        idx -= 1
    return label


DIFF_ROW_BG = "#FFE0E4"
DIFF_CELL_FILL = "#DF0B0B"



class CompareGrid(ttk.Frame):
    """Spreadsheet-style grid backed by tksheet with cell-level highlighting."""

    def __init__(self, master: tk.Widget, *, title: str, columns: Sequence[str], default_rows: int):
        super().__init__(master, padding=6)
        self._title = ttk.Label(self, text=title, font=("TkDefaultFont", 10, "bold"))
        self._title.grid(row=0, column=0, sticky="w")
        self.columns: List[str] = list(columns)
        self.default_rows = default_rows
        self._partner: "CompareGrid | None" = None

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.sheet = Sheet(
            self,
            headers=self.columns,
            data=self._blank_data(self.default_rows),
            show_top_left=False,
            show_row_index=True,
            show_x_scrollbar=True,
            show_y_scrollbar=True,
            paste_can_expand_x=False,
            paste_can_expand_y=True,
            default_column_width=90,
            default_row_index_width=50,
            default_row_height=22,
        )
        self.sheet.enable_bindings(
            (
                "single_select",
                "drag_select",
                "column_select",
                "row_select",
                "column_width_resize",
                "row_height_resize",
                "copy",
                "cut",
                "paste",
                "undo",
                "redo",
                "edit_cell",
                "right_click_popup_menu",
                "rc_select",
            )
        )
        self.sheet.grid(row=1, column=0, sticky="nsew")

    def _blank_data(self, rows: int | None = None) -> List[List[str]]:
        count = rows if rows is not None else self.default_rows
        count = max(count, 0)
        return [["" for _ in self.columns] for _ in range(count)]

    def configure_columns(self, columns: Sequence[str]):
        self.columns = list(columns)
        self.sheet.headers(self.columns, reset_col_positions=True, redraw=False)
        data = self.sheet.get_sheet_data()
        adjusted = [
            (list(row) + ["" for _ in self.columns])[: len(self.columns)] if isinstance(row, list) else ["" for _ in self.columns]
            for row in data
        ]
        if not adjusted:
            adjusted = self._blank_data()
        self.sheet.set_sheet_data(adjusted, reset_highlights=True)

    def append_blank_rows(self, count: int):
        if count <= 0:
            return
        self.sheet.insert_rows(rows=count)

    def append_row(self):
        self.append_blank_rows(1)

    def set_partner(self, partner: "CompareGrid"):
        self._partner = partner
        if partner:
            self.sheet.MT.synced_scrolls.add(partner.sheet)

    def get_matrix(self) -> List[List[str]]:
        raw = self.sheet.get_sheet_data()
        return [[("" if cell is None else str(cell)) for cell in row] for row in raw]

    def clear(self, row_count: int | None = None):
        target = row_count if row_count is not None else self.default_rows
        self.sheet.set_sheet_data(self._blank_data(target), reset_highlights=True)

    def highlight_cells(self, cells: Set[tuple[int, int]]) -> None:
        self.clear_highlight()
        if not cells:
            return
        rows = sorted({row for row, _ in cells})
        if rows:
            self.sheet.highlight_rows(rows=rows, bg=DIFF_ROW_BG, redraw=False, overwrite=True)
        self.sheet.highlight_cells(cells=list(cells), bg=DIFF_CELL_FILL, redraw=True, overwrite=True)

    def clear_highlight(self):
        try:
            self.sheet.dehighlight_cells()
            self.sheet.dehighlight_rows()
        except Exception:
            pass


class CompareWindow(tk.Toplevel):
    """Window that compares two manual data snapshots."""

    DEFAULT_COLUMNS = 100
    DEFAULT_ROWS = 100

    def __init__(self, parent: tk.Widget, icon_path: str | None = None):
        super().__init__(parent)
        self.parent = parent
        self._icon_path = icon_path
        self.title(i18n.translate("compare.title"))
        self.geometry("1260x720")
        self.minsize(960, 600)
        self._set_icon()
        self.column_var = tk.IntVar(value=self.DEFAULT_COLUMNS)
        self.summary_var = tk.StringVar(value=i18n.translate("compare.summary.placeholder"))
        self._column_apply_after_id: str | None = None

        self._build_ui()
        self._apply_column_count()

    def _set_icon(self):
        if not self._icon_path:
            return
        try:
            self.iconbitmap(self._icon_path)
        except Exception:
            pass

    def _build_ui(self):
        controls = ttk.Frame(self, padding=10)
        controls.pack(fill="x")
        ttk.Label(controls, text=i18n.translate("compare.label.columns")).pack(side="left")
        spin = ttk.Spinbox(controls, from_=1, to=100, textvariable=self.column_var, width=5, command=self._on_column_spin)
        spin.pack(side="left", padx=(6, 12))
        spin.bind("<FocusOut>", self._commit_column_spin)
        spin.bind("<Return>", self._commit_column_spin)
        ttk.Button(controls, text=i18n.translate("compare.btn.add_rows"), command=lambda: self._add_rows(5)).pack(
            side="left"
        )
        ttk.Button(controls, text=i18n.translate("compare.btn.clear"), command=self._clear_all).pack(
            side="left", padx=(12, 0)
        )

        self.main_pane = ttk.Panedwindow(self, orient="horizontal")
        self.main_pane.pack(fill="both", expand=True, padx=10, pady=6)

        initial_columns = [_excel_column_name(i) for i in range(self.DEFAULT_COLUMNS)]
        self.left_grid = CompareGrid(
            self.main_pane,
            title=i18n.translate("compare.grid.left"),
            columns=initial_columns,
            default_rows=self.DEFAULT_ROWS,
        )
        self.right_grid = CompareGrid(
            self.main_pane,
            title=i18n.translate("compare.grid.right"),
            columns=list(initial_columns),
            default_rows=self.DEFAULT_ROWS,
        )
        self.left_grid.set_partner(self.right_grid)
        self.right_grid.set_partner(self.left_grid)
        self.main_pane.add(self.left_grid, weight=1)
        self.main_pane.add(self.right_grid, weight=1)

        action_row = ttk.Frame(self, padding=10)
        action_row.pack(fill="x")
        ttk.Button(action_row, text=i18n.translate("compare.btn.run"), command=self._compare).pack(side="left")
        ttk.Label(action_row, textvariable=self.summary_var).pack(side="left", padx=(12, 0))

    def _on_column_spin(self):
        if self._column_apply_after_id:
            self.after_cancel(self._column_apply_after_id)
        self._column_apply_after_id = self.after(350, self._apply_column_count)

    def _commit_column_spin(self, _event=None):
        if self._column_apply_after_id:
            self.after_cancel(self._column_apply_after_id)
            self._column_apply_after_id = None
        self._apply_column_count()

    def _apply_column_count(self):
        count = max(1, min(100, self.column_var.get()))
        self.column_var.set(count)
        if self._column_apply_after_id:
            self.after_cancel(self._column_apply_after_id)
            self._column_apply_after_id = None
        columns = [_excel_column_name(i) for i in range(count)]
        self.left_grid.configure_columns(columns)
        self.right_grid.configure_columns(columns)
        self.left_grid.clear(self.DEFAULT_ROWS)
        self.right_grid.clear(self.DEFAULT_ROWS)
        self.summary_var.set(i18n.translate("compare.summary.placeholder"))

    def _add_rows(self, count: int):
        self.left_grid.append_blank_rows(count)
        self.right_grid.append_blank_rows(count)

    def _clear_all(self):
        if messagebox.askyesno(i18n.translate("common.app_title"), i18n.translate("compare.msg.clear_confirm"), parent=self):
            self.left_grid.clear(self.DEFAULT_ROWS)
            self.right_grid.clear(self.DEFAULT_ROWS)
            self.summary_var.set(i18n.translate("compare.summary.placeholder"))

    def _compare(self):
        left_rows = self._trim_rows(self.left_grid.get_matrix())
        right_rows = self._trim_rows(self.right_grid.get_matrix())
        max_rows = max(len(left_rows), len(right_rows))
        max_cols = max(len(self.left_grid.columns), len(self.right_grid.columns))
        diff_positions: list[Tuple[int, int]] = []
        for r in range(max_rows):
            left_row = left_rows[r] if r < len(left_rows) else [""] * max_cols
            right_row = right_rows[r] if r < len(right_rows) else [""] * max_cols
            for c in range(max_cols):
                left_val = left_row[c] if c < len(left_row) else ""
                right_val = right_row[c] if c < len(right_row) else ""
                if str(left_val).strip() != str(right_val).strip():
                    diff_positions.append((r, c))
        total = len(diff_positions)
        max_left_cols = len(self.left_grid.columns)
        max_right_cols = len(self.right_grid.columns)
        diff_cells = {(r, c) for r, c in diff_positions if c < max_left_cols}
        diff_cells_right = {(r, c) for r, c in diff_positions if c < max_right_cols}
        self.left_grid.highlight_cells(diff_cells)
        self.right_grid.highlight_cells(diff_cells_right)
        if total == 0:
            self.summary_var.set(i18n.translate("compare.summary.same"))
        else:
            detail_text = self._format_diff_detail(diff_positions)
            base = i18n.translate("compare.summary.diff", count=total)
            if detail_text:
                base = f"{base} [{detail_text}]"
            self.summary_var.set(base)

    @staticmethod
    def _trim_rows(rows: List[List[str]]) -> List[List[str]]:
        def is_empty(row: List[str]) -> bool:
            return all(not str(cell).strip() for cell in row)

        trimmed = list(rows)
        while trimmed and is_empty(trimmed[-1]):
            trimmed.pop()
        return trimmed

    def _format_diff_detail(self, positions: list[Tuple[int, int]]) -> str:
        if not positions:
            return ""
        detail: dict[int, List[str]] = {}
        for row_idx, col_idx in positions:
            detail.setdefault(row_idx, []).append(_excel_column_name(col_idx))
        parts = []
        for row_idx in sorted(detail)[:5]:
            cols = ", ".join(detail[row_idx])
            parts.append(f"R{row_idx + 1}: {cols}")
        return "; ".join(parts)


def open_compare_window(parent: tk.Widget, icon_path: str | None = None):
    CompareWindow(parent, icon_path=icon_path)
