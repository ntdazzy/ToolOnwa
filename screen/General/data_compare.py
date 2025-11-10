"""
Data comparison window with two editable grids.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
from typing import List, Sequence, Tuple

from screen.DB.widgets import EditableTreeview
from core import i18n


class CompareGrid(ttk.Frame):
    """Wrapper around EditableTreeview with diff highlighting and scroll sync."""

    def __init__(self, master: tk.Widget, *, title: str, columns: Sequence[str]):
        super().__init__(master, padding=6)
        self._title = ttk.Label(self, text=title, font=("TkDefaultFont", 10, "bold"))
        self._title.grid(row=0, column=0, sticky="w")
        self.columns: List[str] = list(columns)
        self._partner: "CompareGrid | None" = None
        self._syncing = False
        self._diff_positions: list[Tuple[int, int]] = []

        self.tree = EditableTreeview(self, columns=self.columns, height=16)
        try:
            self.tree.configure(style="Excel.Treeview")
        except tk.TclError:
            pass
        self.tree.grid(row=1, column=0, sticky="nsew")

        self.vsb = ttk.Scrollbar(self, orient="vertical", command=self._on_vsb_scroll)
        self.hsb = ttk.Scrollbar(self, orient="horizontal", command=self._on_hsb_scroll)
        self.vsb.grid(row=1, column=1, sticky="ns")
        self.hsb.grid(row=2, column=0, sticky="ew")
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.tree.configure(yscrollcommand=self._on_tree_yview, xscrollcommand=self._on_tree_xview)

        base_bg = self._tree_background()
        self._overlay = tk.Canvas(
            self.tree,
            highlightthickness=0,
            bd=0,
            background=base_bg,
            takefocus=0,
        )
        self._overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
        self._bind_overlay_events()

        self.configure_columns(self.columns)
        self.tree.bind("<Configure>", lambda _e: self._redraw_highlight())

    def configure_columns(self, columns: Sequence[str]):
        self.columns = list(columns)
        self.tree.configure_columns(self.columns)
        for col in self.columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=110, minwidth=80, anchor="center", stretch=True)
        # ensure all rows have these columns
        self._redraw_highlight()

    def append_blank_rows(self, count: int):
        for _ in range(count):
            self.append_row()

    def append_row(self):
        values = {col: "" for col in self.columns}
        self.tree.append_dict(values, mark_new=False)

    def ensure_row_count(self, desired: int):
        current = len(self.tree.get_children())
        if current < desired:
            self.append_blank_rows(desired - current)

    def set_partner(self, partner: "CompareGrid"):
        self._partner = partner

    def get_matrix(self) -> List[List[str]]:
        rows = []
        for iid in self.tree.get_children():
            row = [self.tree.set(iid, col) for col in self.columns]
            rows.append(row)
        return rows

    def clear(self):
        self.tree.clear()
        self.clear_highlight()

    def _on_tree_yview(self, first: str, last: str):
        self.vsb.set(first, last)
        self._schedule_highlight()
        if self._partner and not self._syncing:
            try:
                self._partner._syncing = True
                self._partner.tree.yview_moveto(first)
            finally:
                self._partner._syncing = False

    def _on_tree_xview(self, first: str, last: str):
        self.hsb.set(first, last)
        self._schedule_highlight()
        if self._partner and not self._syncing:
            try:
                self._partner._syncing = True
                self._partner.tree.xview_moveto(first)
            finally:
                self._partner._syncing = False

    def _schedule_highlight(self):
        self.after_idle(self._redraw_highlight)

    def highlight_cells(self, positions: list[Tuple[int, int]]):
        self._diff_positions = positions
        self._redraw_highlight()

    def clear_highlight(self):
        self._diff_positions = []
        self._overlay.delete("diff")

    def _redraw_highlight(self):
        try:
            self._overlay.lift()
        except tk.TclError:
            pass
        self._overlay.delete("diff")
        if not self._diff_positions:
            return
        children = self.tree.get_children()
        for row_idx, col_idx in self._diff_positions:
            if row_idx >= len(children) or col_idx >= len(self.columns):
                continue
            iid = children[row_idx]
            col = self.columns[col_idx]
            bbox = self.tree.bbox(iid, col)
            if not bbox:
                continue
            x, y, width, height = bbox
            self._overlay.create_rectangle(
                x,
                y,
                x + width,
                y + height,
                fill="#FFD7D9",
                outline="#FF5E5E",
                width=1,
                stipple="gray25",
                tags="diff",
            )

    def _bind_overlay_events(self):
        def forward(seq):
            def _handler(event):
                kwargs = {"x": event.x, "y": event.y}
                if hasattr(event, "delta") and "MouseWheel" in seq:
                    kwargs["delta"] = event.delta
                self.tree.event_generate(seq, **kwargs)
                return "break"

            return _handler

        mouse_sequences = [
            "<Button-1>",
            "<Double-1>",
            "<B1-Motion>",
            "<ButtonRelease-1>",
            "<Button-2>",
            "<Button-3>",
            "<MouseWheel>",
            "<Shift-MouseWheel>",
            "<Control-MouseWheel>",
            "<Button-4>",
            "<Button-5>",
        ]
        for seq in mouse_sequences:
            self._overlay.bind(seq, forward(seq), add="+")

    def _tree_background(self) -> str:
        try:
            style_name = self.tree.cget("style") or "Treeview"
        except tk.TclError:
            style_name = "Treeview"
        style = ttk.Style(self.tree)
        bg = style.lookup(style_name, "background") or style.lookup(style_name, "fieldbackground")
        if not bg:
            bg = "#FFFFFF"
        return bg

    def _on_vsb_scroll(self, *args):
        self.tree.yview(*args)
        self._schedule_highlight()

    def _on_hsb_scroll(self, *args):
        self.tree.xview(*args)
        self._schedule_highlight()


class CompareWindow(tk.Toplevel):
    """Window that compares two manual data snapshots."""

    DEFAULT_COLUMNS = 8
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
        spin = ttk.Spinbox(controls, from_=1, to=50, textvariable=self.column_var, width=5)
        spin.pack(side="left", padx=(6, 12))
        ttk.Button(controls, text=i18n.translate("compare.btn.apply_columns"), command=self._apply_column_count).pack(
            side="left", padx=(0, 12)
        )
        ttk.Button(controls, text=i18n.translate("compare.btn.add_rows"), command=lambda: self._add_rows(5)).pack(
            side="left"
        )
        ttk.Button(controls, text=i18n.translate("compare.btn.clear"), command=self._clear_all).pack(
            side="left", padx=(12, 0)
        )

        self.main_pane = ttk.Panedwindow(self, orient="horizontal")
        self.main_pane.pack(fill="both", expand=True, padx=10, pady=6)

        self.left_grid = CompareGrid(
            self.main_pane,
            title=i18n.translate("compare.grid.left"),
            columns=[f"C{i+1}" for i in range(self.DEFAULT_COLUMNS)],
        )
        self.right_grid = CompareGrid(
            self.main_pane,
            title=i18n.translate("compare.grid.right"),
            columns=[f"C{i+1}" for i in range(self.DEFAULT_COLUMNS)],
        )
        self.left_grid.set_partner(self.right_grid)
        self.right_grid.set_partner(self.left_grid)
        self.main_pane.add(self.left_grid, weight=1)
        self.main_pane.add(self.right_grid, weight=1)

        action_row = ttk.Frame(self, padding=10)
        action_row.pack(fill="x")
        ttk.Button(action_row, text=i18n.translate("compare.btn.run"), command=self._compare).pack(side="left")
        ttk.Label(action_row, textvariable=self.summary_var).pack(side="left", padx=(12, 0))

    def _apply_column_count(self):
        count = max(1, min(50, self.column_var.get()))
        columns = [f"C{i+1}" for i in range(count)]
        self.left_grid.configure_columns(columns)
        self.right_grid.configure_columns(columns)
        self.left_grid.clear()
        self.right_grid.clear()
        self.summary_var.set(i18n.translate("compare.summary.placeholder"))
        self.left_grid.append_blank_rows(self.DEFAULT_ROWS)
        self.right_grid.append_blank_rows(self.DEFAULT_ROWS)

    def _add_rows(self, count: int):
        self.left_grid.append_blank_rows(count)
        self.right_grid.append_blank_rows(count)

    def _clear_all(self):
        if messagebox.askyesno(i18n.translate("common.app_title"), i18n.translate("compare.msg.clear_confirm"), parent=self):
            self.left_grid.clear()
            self.right_grid.clear()
            self.left_grid.clear_highlight()
            self.right_grid.clear_highlight()
            self.summary_var.set(i18n.translate("compare.summary.placeholder"))
            self.left_grid.append_blank_rows(self.DEFAULT_ROWS)
            self.right_grid.append_blank_rows(self.DEFAULT_ROWS)

    def _compare(self):
        left_rows = self._trim_rows(self.left_grid.get_matrix())
        right_rows = self._trim_rows(self.right_grid.get_matrix())
        max_rows = max(len(left_rows), len(right_rows))
        max_cols = len(self.left_grid.columns)
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
        self.left_grid.highlight_cells(diff_positions)
        self.right_grid.highlight_cells(diff_positions)
        if total == 0:
            self.summary_var.set(i18n.translate("compare.summary.same"))
        else:
            self.summary_var.set(i18n.translate("compare.summary.diff", count=total))

    @staticmethod
    def _trim_rows(rows: List[List[str]]) -> List[List[str]]:
        def is_empty(row: List[str]) -> bool:
            return all(not str(cell).strip() for cell in row)

        trimmed = list(rows)
        while trimmed and is_empty(trimmed[-1]):
            trimmed.pop()
        return trimmed


def open_compare_window(parent: tk.Widget, icon_path: str | None = None):
    CompareWindow(parent, icon_path=icon_path)
