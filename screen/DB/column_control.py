"""
Màn hình Thêm/Xóa cột cho phép backup bảng, drop-create và đẩy dữ liệu với cột mới.
"""
from __future__ import annotations

import dataclasses
import datetime as dt
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
from tkinter.scrolledtext import ScrolledText

from screen.DB import db_utils
from screen.DB.backup import BackupRestoreBase
from core import i18n

APP_TITLE_KEY = "common.app_title"


def _t(key: str, **kwargs) -> str:
    return i18n.translate(key, **kwargs)


@dataclass
class ColumnConfig:
    """Trạng thái một cột trong danh sách chỉnh sửa."""

    name: str
    source: str  # "base" hoặc "new"
    removed: bool = False
    data_type: Optional[str] = None
    data_length: Optional[int] = None
    data_precision: Optional[int] = None
    data_scale: Optional[int] = None
    nullable: bool = True
    custom_type: Optional[str] = None
    default_value: Optional[str] = None
    values: List[str] = field(default_factory=list)

    def effective_type(self) -> str:
        if self.source == "new":
            return (self.custom_type or "").strip()
        return (self.data_type or "").strip()

    def clone(self) -> "ColumnConfig":
        return dataclasses.replace(self, values=list(self.values or []))


ACTIVE_WINDOWS: List["ColumnControlWindow"] = []


def open_column_control_window(parent: tk.Widget, connection: Dict[str, str]):
    """Mở cửa sổ Column Control và gỡ khỏi danh sách khi đóng."""
    win = ColumnControlWindow(parent, connection)
    ACTIVE_WINDOWS.append(win)

    def _cleanup(event):
        if event.widget is win and win in ACTIVE_WINDOWS:
            ACTIVE_WINDOWS.remove(win)

    win.bind("<Destroy>", _cleanup, add="+")
    return win


class ColumnControlWindow(BackupRestoreBase):
    """Màn hình Thêm/Xóa cột theo mô tả nghiệp vụ."""

    GEOMETRY = "1200x760"

    COLOR_NEW = "#fff6bf"
    COLOR_REMOVED = "#ffd6d6"

    def __init__(self, parent: tk.Widget, connection: Dict[str, str]):
        self.var_backup_table = tk.StringVar()
        self.var_backup_name = self.var_backup_table  # để dùng chung helper base
        self.var_sql_file = tk.StringVar()
        self.var_column_type = tk.StringVar()
        self.var_column_default = tk.StringVar()

        self._column_order: List[str] = []
        self._column_state: Dict[str, ColumnConfig] = {}
        self._selected_column: Optional[str] = None
        self._sql_file_path: Optional[str] = None
        self._sql_file_content: str = ""
        self._sql_file_valid: bool = False
        self._generated_sql: str = ""
        self._sql_override: Optional[str] = None
        self._history_action_type = "column_control"

        super().__init__(parent, connection, title_key="column_ctrl.title")

    # ------------------------------------------------------------------
    # region UI build
    def _build_ui(self):
        """Tùy biến layout theo thiết kế mới."""
        self.frm_main = ttk.Frame(self, padding=8)
        self.frm_main.pack(fill="both", expand=True)
        self.frm_main.columnconfigure(0, weight=1)
        self.frm_main.rowconfigure(0, weight=2)
        self.frm_main.rowconfigure(1, weight=3)
        self.frm_main.rowconfigure(2, weight=0)
        self.frm_main.rowconfigure(3, weight=2)

        top_sections = ttk.Frame(self.frm_main)
        top_sections.grid(row=0, column=0, sticky="nsew")
        top_sections.columnconfigure(0, weight=1)
        top_sections.columnconfigure(1, weight=3)
        top_sections.columnconfigure(2, weight=2)
        top_sections.rowconfigure(0, weight=1)

        # Khối tìm kiếm (bên trái)
        self.grp_search = ttk.LabelFrame(top_sections, text=_t("column_ctrl.section.search"), padding=8)
        self.grp_search.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self.grp_search.columnconfigure(0, weight=1)
        self.grp_search.rowconfigure(2, weight=1)

        self.lbl_table = ttk.Label(self.grp_search, text=_t("column_ctrl.label.table_name"))
        self.lbl_table.grid(row=0, column=0, sticky="w")
        self.ent_search = ttk.Entry(self.grp_search, textvariable=self.var_search)
        self.ent_search.grid(row=1, column=0, sticky="ew", pady=(2, 6))
        self.ent_search.bind("<KeyRelease>", lambda _e: self._filter_tables())

        self.list_tables = tk.Listbox(self.grp_search, height=12)
        self.list_tables.grid(row=2, column=0, sticky="nsew")
        self.list_tables.bind("<<ListboxSelect>>", self._handle_table_select)

        self.lbl_backup_table = ttk.Label(self.grp_search, text=_t("column_ctrl.label.backup_table"))
        self.lbl_backup_table.grid(row=3, column=0, sticky="w", pady=(6, 0))
        self.ent_backup = ttk.Entry(self.grp_search, textvariable=self.var_backup_table)
        self.ent_backup.grid(row=4, column=0, sticky="ew")

        self.grp_columns = ttk.LabelFrame(top_sections, text=_t("column_ctrl.section.columns"), padding=8)
        self.grp_columns.grid(row=0, column=1, sticky="nsew", padx=(0, 8))
        self.grp_columns.rowconfigure(0, weight=1)
        self.grp_columns.columnconfigure(0, weight=1)

        columns_frame = ttk.Frame(self.grp_columns)
        columns_frame.grid(row=0, column=0, sticky="nsew")
        columns_frame.rowconfigure(0, weight=1)
        columns_frame.columnconfigure(0, weight=1)

        self.lst_columns = tk.Listbox(columns_frame, height=12, exportselection=False)
        self.lst_columns.grid(row=0, column=0, sticky="nsew")
        self.lst_columns.bind("<<ListboxSelect>>", self._on_column_select)

        scroll_cols = ttk.Scrollbar(columns_frame, orient="vertical", command=self.lst_columns.yview)
        scroll_cols.grid(row=0, column=1, sticky="ns")
        self.lst_columns.configure(yscrollcommand=scroll_cols.set)

        btns = ttk.Frame(self.grp_columns)
        btns.grid(row=0, column=1, sticky="nsw")
        self._btn_move_up = ttk.Button(btns, text="↑", width=4, command=self._move_column_up)
        self._btn_move_up.grid(row=0, column=0, pady=2)
        self._btn_move_down = ttk.Button(btns, text="↓", width=4, command=self._move_column_down)
        self._btn_move_down.grid(row=1, column=0, pady=2)
        self._btn_add = ttk.Button(btns, text="+", width=4, command=self._add_column)
        self._btn_add.grid(row=2, column=0, pady=2)
        self._btn_remove = ttk.Button(btns, text="-", width=4, command=self._remove_column)
        self._btn_remove.grid(row=3, column=0, pady=2)
        self._btn_restore = ttk.Button(btns, text="✓", width=4, command=self._restore_column)
        self._btn_restore.grid(row=4, column=0, pady=2)

        self.grp_data = ttk.LabelFrame(top_sections, text=_t("column_ctrl.section.data"), padding=8)
        self.grp_data.grid(row=0, column=2, sticky="nsew")
        self.grp_data.columnconfigure(1, weight=1)
        self.grp_data.rowconfigure(3, weight=1)

        self.lbl_column_type = ttk.Label(self.grp_data, text=_t("column_ctrl.label.column_type"))
        self.lbl_column_type.grid(row=0, column=0, sticky="w")
        self.cmb_column_type = ttk.Combobox(self.grp_data, textvariable=self.var_column_type, values=self._default_column_types())
        self.cmb_column_type.grid(row=0, column=1, sticky="ew", pady=(0, 6))

        self.lbl_default_value = ttk.Label(self.grp_data, text=_t("column_ctrl.label.default_value"))
        self.lbl_default_value.grid(row=1, column=0, sticky="w")
        self.ent_default_value = ttk.Entry(self.grp_data, textvariable=self.var_column_default)
        self.ent_default_value.grid(row=1, column=1, sticky="ew", pady=(0, 6))

        self.lbl_values = ttk.Label(self.grp_data, text=_t("column_ctrl.label.values"))
        self.lbl_values.grid(row=2, column=0, sticky="w")
        self.txt_values = ScrolledText(self.grp_data, height=5, width=30, wrap="word")
        self.txt_values.grid(row=3, column=0, columnspan=2, sticky="nsew")
        self.lbl_value_hint = ttk.Label(self.grp_data, text=_t("column_ctrl.label.value_hint"))
        self.lbl_value_hint.grid(row=4, column=0, columnspan=2, sticky="w", pady=(4, 0))

        # SQL section
        self.grp_sql = ttk.LabelFrame(self.frm_main, text=_t("column_ctrl.section.sql"), padding=8)
        self.grp_sql.grid(row=1, column=0, sticky="nsew", pady=(8, 0))
        self.grp_sql.columnconfigure(0, weight=1)
        self.grp_sql.rowconfigure(0, weight=1)

        self.txt_sql = ScrolledText(self.grp_sql, height=10, wrap="word")
        self.txt_sql.grid(row=0, column=0, sticky="nsew")

        # Buttons row
        self.frm_buttons = ttk.Frame(self.frm_main)
        self.frm_buttons.grid(row=2, column=0, sticky="ew", pady=8)
        self.frm_buttons.columnconfigure(0, weight=1)
        self.frm_buttons.columnconfigure(1, weight=0)

        left_btns = ttk.Frame(self.frm_buttons)
        left_btns.grid(row=0, column=0, sticky="w")
        self.btn_choose_sql = ttk.Button(left_btns, text=_t("column_ctrl.btn.choose_sql"), command=self._choose_sql_file)
        self.btn_choose_sql.pack(side="left", padx=(0, 6))
        self.btn_generate_sql = ttk.Button(left_btns, text=_t("column_ctrl.btn.generate_sql"), command=self._generate_sql_from_columns)
        self.btn_generate_sql.pack(side="left", padx=(0, 6))
        self.btn_reset = ttk.Button(left_btns, text=_t("column_ctrl.btn.reset"), command=self._reset_changes)
        self.btn_reset.pack(side="left")

        right_btns = ttk.Frame(self.frm_buttons)
        right_btns.grid(row=0, column=1, sticky="e")
        self.btn_update_sql = ttk.Button(right_btns, text=_t("column_ctrl.btn.update_sql"), command=self._lock_manual_sql)
        self.btn_update_sql.pack(side="left", padx=(0, 6))
        self.btn_execute = ttk.Button(right_btns, text=_t("column_ctrl.btn.execute"), command=self._execute_script)
        self.btn_execute.pack(side="left")

        self.lbl_sql_file = ttk.Label(self.frm_buttons, textvariable=self.var_sql_file, foreground="#555555")
        self.lbl_sql_file.grid(row=1, column=0, sticky="w", pady=(4, 0))

        # Log section
        self.grp_log = ttk.LabelFrame(self.frm_main, text=_t("column_ctrl.section.log"), padding=8)
        self.grp_log.grid(row=3, column=0, sticky="nsew")
        self.grp_log.columnconfigure(0, weight=1)
        self.grp_log.rowconfigure(0, weight=1)

        self.txt_log = ScrolledText(self.grp_log, height=6, wrap="word")
        self.txt_log.grid(row=0, column=0, sticky="nsew")
        self.txt_log.bind("<Key>", self._block_log_edit, add="+")

        self._set_initial_state()

    # endregion UI build

    def _default_column_types(self) -> Sequence[str]:
        return [
            "VARCHAR2(10)",
            "VARCHAR2(50)",
            "VARCHAR2(255)",
            "NUMBER",
            "NUMBER(10)",
            "NUMBER(10,2)",
            "DATE",
            "TIMESTAMP",
            "CLOB",
            "NCLOB",
        ]

    def _set_initial_state(self) -> None:
        self._column_order.clear()
        self._column_state.clear()
        self.lst_columns.delete(0, tk.END)
        self.var_backup_table.set("")
        self._selected_column = None
        self._sql_file_path = None
        self._sql_file_content = ""
        self._sql_file_valid = False
        self._sql_override = None
        self._generated_sql = ""
        self._write_sql_text("")
        self.var_column_type.set("")
        self.var_column_default.set("")
        self.txt_values.delete("1.0", tk.END)
        self._set_column_controls_state(False)
        self._set_data_controls_state(False)
        self._set_generation_controls(False)
        self._set_sql_controls_state(False)
        self._update_file_label()

    def _clear_sql_state(self) -> None:
        self._sql_override = None
        self._generated_sql = ""
        self._write_sql_text("")

    def _write_sql_text(self, text: str) -> None:
        widget = self.txt_sql
        previous_state = str(widget.cget("state"))
        widget.configure(state="normal")
        widget.delete("1.0", tk.END)
        if text:
            widget.insert("1.0", text.rstrip() + "\n")
        widget.configure(state=previous_state)

    def _block_log_edit(self, event):
        if event.state & 0x4 and event.keysym.lower() in ("c", "a"):
            return None
        if event.keysym in ("Left", "Right", "Up", "Down", "Home", "End"):
            return None
        if event.keysym in ("Prior", "Next"):
            return None
        return "break"

    def _set_column_controls_state(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        for widget in (self.lst_columns, self._btn_move_up, self._btn_move_down, self._btn_add, self._btn_remove, self._btn_restore):
            try:
                widget.configure(state=state)
            except tk.TclError:
                pass

    def _set_data_controls_state(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        for widget in (self.cmb_column_type, self.ent_default_value, self.txt_values):
            try:
                widget.configure(state=state)
            except tk.TclError:
                pass

    def _set_sql_controls_state(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        for widget in (self.btn_update_sql, self.btn_execute, self.txt_sql):
            try:
                widget.configure(state=state)
            except tk.TclError:
                pass

    def _set_generation_controls(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        for widget in (self.btn_generate_sql, self.btn_reset, self.btn_choose_sql):
            try:
                widget.configure(state=state)
            except tk.TclError:
                pass

    def _update_file_label(self) -> None:
        label = _t("column_ctrl.label.sql_file_none")
        if self._sql_file_path:
            label = Path(self._sql_file_path).name
        self.var_sql_file.set(label)

    # ------------------------------------------------------------------
    # region Column management
    def on_metadata_loading(self, loading: bool) -> None:
        super().on_metadata_loading(loading)
        if loading:
            self._set_column_controls_state(False)
            self._set_data_controls_state(False)
            self._set_generation_controls(False)
            self._set_sql_controls_state(False)
        elif self._active_table:
            self._set_column_controls_state(True)
            self._set_generation_controls(True)

    def _reset_state_for_table(self) -> None:
        self._column_order.clear()
        self._column_state.clear()
        self.lst_columns.delete(0, tk.END)
        self._selected_column = None
        self.var_column_type.set("")
        self.var_column_default.set("")
        self.txt_values.delete("1.0", tk.END)
        self._sql_file_path = None
        self._sql_file_content = ""
        self._sql_file_valid = False
        self._sql_override = None
        self._generated_sql = ""
        self._update_file_label()
        self._write_sql_text("")

    def on_table_ready(self, table: str):
        self._reset_state_for_table()
        if not table:
            self.var_backup_table.set("")
            self._set_column_controls_state(False)
            self._set_generation_controls(False)
            self._set_data_controls_state(False)
            self._set_sql_controls_state(False)
            return
        owner, name = self._split_table(table)
        backup_name = f"{name}_BK_{dt.datetime.now().strftime('%Y%m%d')}"
        self.var_backup_table.set(backup_name)
        for col in self._columns:
            meta = self._column_meta.get(col, {})
            cfg = ColumnConfig(
                name=col,
                source="base",
                data_type=str(meta.get("data_type") or ""),
                data_length=meta.get("data_length"),
                data_precision=meta.get("data_precision"),
                data_scale=meta.get("data_scale"),
                nullable=bool(meta.get("nullable", True)),
            )
            self._column_state[col] = cfg
        self._column_order = list(self._columns)
        self._refresh_column_list()
        self._set_column_controls_state(True)
        self._set_generation_controls(True)
        self._set_sql_controls_state(False)
        self._append_log(_t("column_ctrl.log.table_ready", table=f"{owner}.{name}", backup=backup_name))

    def _refresh_column_list(self) -> None:
        selected = self._selected_column
        self.lst_columns.delete(0, tk.END)
        base_bg = self.lst_columns.cget("bg")
        for idx, name in enumerate(self._column_order):
            self.lst_columns.insert(tk.END, name)
            cfg = self._column_state.get(name)
            if not cfg:
                continue
            if cfg.source == "new" and not cfg.removed:
                self.lst_columns.itemconfig(idx, background=self.COLOR_NEW)
            elif cfg.removed:
                self.lst_columns.itemconfig(idx, background=self.COLOR_REMOVED)
            else:
                self.lst_columns.itemconfig(idx, background=base_bg)
        if selected and selected in self._column_order:
            new_index = self._column_order.index(selected)
            self.lst_columns.selection_clear(0, tk.END)
            self.lst_columns.selection_set(new_index)
            self.lst_columns.see(new_index)
        else:
            self.lst_columns.selection_clear(0, tk.END)
            self._selected_column = None
            self._update_data_section_state()

    def _selected_config(self) -> Optional[ColumnConfig]:
        if not self._selected_column:
            return None
        return self._column_state.get(self._selected_column)

    def _on_column_select(self, _event=None):
        self._persist_current_column_values()
        selection = self.lst_columns.curselection()
        if not selection:
            self._selected_column = None
            self._update_data_section_state()
            return
        index = selection[0]
        if index >= len(self._column_order):
            return
        self._selected_column = self._column_order[index]
        self._populate_data_fields()
        self._update_data_section_state()

    def _populate_data_fields(self) -> None:
        cfg = self._selected_config()
        if not cfg or cfg.source != "new" or cfg.removed:
            self.var_column_type.set("")
            self.var_column_default.set("")
            self.txt_values.delete("1.0", tk.END)
            return
        self.var_column_type.set(cfg.effective_type())
        self.var_column_default.set(cfg.default_value or "")
        self.txt_values.delete("1.0", tk.END)
        for value in cfg.values:
            self.txt_values.insert(tk.END, value + "\n")

    def _update_data_section_state(self) -> None:
        has_new = any(cfg.source == "new" and not cfg.removed for cfg in self._column_state.values())
        cfg = self._selected_config()
        allow_edit = bool(has_new and cfg and cfg.source == "new" and not cfg.removed)
        self._set_data_controls_state(allow_edit)

    def _persist_current_column_values(self) -> None:
        if not self._selected_column:
            return
        cfg = self._column_state.get(self._selected_column)
        if not cfg or cfg.source != "new" or cfg.removed:
            return
        cfg.custom_type = self.var_column_type.get().strip().upper() or cfg.custom_type
        cfg.default_value = self.var_column_default.get().strip()
        values = [line.strip() for line in self.txt_values.get("1.0", tk.END).splitlines() if line.strip()]
        cfg.values = values

    def _move_column_up(self):
        self._persist_current_column_values()
        if not self._selected_column:
            return
        idx = self._column_order.index(self._selected_column)
        if idx == 0:
            return
        self._column_order[idx - 1], self._column_order[idx] = self._column_order[idx], self._column_order[idx - 1]
        self._refresh_column_list()

    def _move_column_down(self):
        self._persist_current_column_values()
        if not self._selected_column:
            return
        idx = self._column_order.index(self._selected_column)
        if idx == len(self._column_order) - 1:
            return
        self._column_order[idx + 1], self._column_order[idx] = self._column_order[idx], self._column_order[idx + 1]
        self._refresh_column_list()

    def _add_column(self):
        self._persist_current_column_values()
        name = simpledialog.askstring(_t(APP_TITLE_KEY), _t("column_ctrl.dialog.new_column"), parent=self)
        if not name:
            return
        norm = name.strip().upper()
        if not norm:
            return
        if norm in self._column_state:
            messagebox.showwarning(_t(APP_TITLE_KEY), _t("column_ctrl.msg.column_exists", column=norm), parent=self)
            return
        cfg = ColumnConfig(name=norm, source="new", custom_type="VARCHAR2(50)", default_value="")
        self._column_state[norm] = cfg
        self._column_order.append(norm)
        self._selected_column = norm
        self._refresh_column_list()
        self._populate_data_fields()
        self._update_data_section_state()

    def _remove_column(self):
        self._persist_current_column_values()
        cfg = self._selected_config()
        if not cfg:
            return
        if cfg.source == "new":
            # xóa hẳn cột mới
            if cfg.name in self._column_state:
                del self._column_state[cfg.name]
            if cfg.name in self._column_order:
                self._column_order.remove(cfg.name)
            self._selected_column = None
        else:
            cfg.removed = True
        self._refresh_column_list()
        self._update_data_section_state()

    def _restore_column(self):
        self._persist_current_column_values()
        cfg = self._selected_config()
        if not cfg:
            return
        if cfg.source == "new":
            # bỏ cột mới
            self._remove_column()
            return
        cfg.removed = False
        self._refresh_column_list()
        self._update_data_section_state()

    # endregion Column management

    # ------------------------------------------------------------------
    # region SQL generation & execution
    def _collect_final_columns(self) -> List[ColumnConfig]:
        if not self._column_order:
            raise ValueError(_t("column_ctrl.msg.no_columns"))
        result: List[ColumnConfig] = []
        for name in self._column_order:
            cfg = self._column_state.get(name)
            if not cfg or cfg.removed:
                continue
            clone = cfg.clone()
            if clone.source == "new":
                clone.custom_type = (clone.custom_type or "").strip().upper()
                if not clone.custom_type:
                    raise ValueError(_t("column_ctrl.msg.type_required", column=clone.name))
            result.append(clone)
        if not result:
            raise ValueError(_t("column_ctrl.msg.no_columns"))
        return result

    def _collect_new_columns(self) -> List[ColumnConfig]:
        return [cfg.clone() for cfg in self._column_state.values() if cfg.source == "new" and not cfg.removed]

    def _generate_sql_from_columns(self):
        if not self._active_table:
            messagebox.showwarning(_t(APP_TITLE_KEY), _t("column_ctrl.msg.select_table_first"), parent=self)
            return
        self._persist_current_column_values()
        try:
            script = self._compose_script()
        except ValueError as exc:
            messagebox.showerror(_t(APP_TITLE_KEY), str(exc), parent=self)
            return
        self._generated_sql = script
        self._sql_override = None
        self._write_sql_text(script)
        self._set_sql_controls_state(True)
        self._append_log(_t("column_ctrl.log.sql_generated"))

    def _compose_script(self) -> str:
        columns = self._collect_final_columns()
        parts = []
        parts.append(self._build_backup_sql())
        ddl_part = ""
        if self._sql_file_path and self._sql_file_content:
            ddl_part = self._sql_file_content.strip()
            if not self._sql_file_valid:
                raise ValueError(_t("column_ctrl.msg.invalid_sql_file"))
            self._append_log(_t("column_ctrl.log.use_file_sql", path=Path(self._sql_file_path).name))
        else:
            ddl_part = self._build_drop_create_sql(columns)
        data_part = self._build_insert_sql(columns)
        for block in (ddl_part, data_part):
            if block.strip():
                parts.append(block.strip())
        text = "\n\n".join(part.strip() for part in parts if part.strip())
        if not text:
            raise ValueError(_t("column_ctrl.msg.empty_sql"))
        return text

    def _build_backup_sql(self) -> str:
        backup_raw = self.var_backup_table.get().strip()
        table = self._active_table["table"]
        if not backup_raw:
            raise ValueError(_t("column_ctrl.msg.backup_name_required"))
        _, bk_name = self._split_table(backup_raw)
        full_backup = bk_name
        sql = (
            f"/* DROP TABLE {full_backup} */\n"
            f"DROP TABLE {full_backup} CASCADE CONSTRAINTS PURGE;\n"
            f"/* CREATE TABLE {full_backup} AS BACKUP */\n"
            f"CREATE TABLE {full_backup} AS\n"
            f"SELECT * FROM {table};"
        )
        self._append_log(_t("column_ctrl.log.backup_ready", backup=full_backup))
        return sql

    def _build_drop_create_sql(self, columns: Sequence[ColumnConfig]) -> str:
        target = self._active_table["table"]
        lines = []
        for cfg in columns:
            lines.append(f"    {cfg.name} {self._format_column_definition(cfg)}")
        cols_text = ",\n".join(lines)
        sql = (
            f"/* DROP TABLE {target} */\n"
            f"DROP TABLE {target} CASCADE CONSTRAINTS PURGE;\n"
            f"/* CREATE TABLE {target} */\n"
            f"CREATE TABLE {target}\n(\n{cols_text}\n);\n"
        )
        self._append_log(_t("column_ctrl.log.auto_ddl"))
        self._append_log(sql)
        return sql

    def _build_insert_sql(self, columns: Sequence[ColumnConfig]) -> str:
        backup_raw = self.var_backup_table.get().strip()
        target = self._active_table["table"]
        if not backup_raw:
            raise ValueError(_t("column_ctrl.msg.backup_name_required"))
        _, bk_name = self._split_table(backup_raw)
        full_backup = bk_name
        select_parts = []
        column_names = []
        for cfg in columns:
            column_names.append(cfg.name)
            if cfg.source == "new":
                select_parts.append(f"{self._expression_for_new_column(cfg)} AS {cfg.name}")
            else:
                select_parts.append(f"bk.{cfg.name}")
        columns_text = ", ".join(column_names)
        select_text = ",\n    ".join(select_parts)
        sql = (
            f"INSERT INTO {target} ({columns_text})\n"
            f"SELECT \n    {select_text}\n"
            f"FROM {full_backup} bk;"
        )
        self._append_log(_t("column_ctrl.log.insert_ready", columns=len(columns)))
        return sql

    def _format_column_definition(self, cfg: ColumnConfig) -> str:
        data_type = cfg.effective_type()
        if cfg.source == "base":
            data_type = self._format_type_from_meta(cfg)
        definition = data_type
        default_literal = ""
        if cfg.source == "new" and cfg.default_value:
            default_literal = f" DEFAULT {self._format_literal(cfg.default_value, data_type)}"
        null_clause = "" if cfg.source == "new" else (" NOT NULL" if not cfg.nullable else "")
        return f"{data_type}{default_literal}{null_clause}"

    def _format_type_from_meta(self, cfg: ColumnConfig) -> str:
        dtype = (cfg.data_type or "").upper()
        if dtype in {"VARCHAR2", "NVARCHAR2", "CHAR", "NCHAR"} and cfg.data_length:
            return f"{dtype}({cfg.data_length})"
        if dtype in db_utils.NUMERIC_TYPES:
            if cfg.data_precision and cfg.data_scale is not None:
                return f"{dtype}({cfg.data_precision},{cfg.data_scale})"
            if cfg.data_precision:
                return f"{dtype}({cfg.data_precision})"
        if dtype == "NUMBER" and cfg.data_scale is not None and cfg.data_precision is None:
            return f"{dtype}(38,{cfg.data_scale})"
        return dtype or "VARCHAR2(50)"

    def _expression_for_new_column(self, cfg: ColumnConfig) -> str:
        data_type = cfg.effective_type() or "VARCHAR2(50)"
        values = cfg.values or []
        default_literal = self._format_literal(cfg.default_value, data_type)
        if not values:
            return default_literal

        literals = [self._format_literal(val, data_type) for val in values]
        if len(literals) == 1:
            return literals[0]

        cases = [f"        WHEN {idx} THEN {literal}" for idx, literal in enumerate(literals)]
        cases_text = "\n".join(cases)
        return (
            f"(CASE TRUNC(DBMS_RANDOM.VALUE(0, {len(literals)}))\n"
            f"{cases_text}\n"
            f"        ELSE {default_literal}\n"
            f"    END)"
        )

    def _format_literal(self, value: Optional[str], data_type: str) -> str:
        if value is None:
            return "' '"
        raw = value
        trimmed = raw.strip()
        if trimmed.upper() == "NULL":
            return "NULL"
        if trimmed == "":
            return "' '"
        meta = {"data_type": data_type.upper()}
        return db_utils.format_sql_literal(trimmed, meta)

    def _lock_manual_sql(self):
        text = self.txt_sql.get("1.0", tk.END).strip()
        if not text:
            messagebox.showwarning(_t(APP_TITLE_KEY), _t("column_ctrl.msg.empty_sql"), parent=self)
            return
        self._sql_override = text
        self._append_log(_t("column_ctrl.log.manual_sql"))
        messagebox.showinfo(_t(APP_TITLE_KEY), _t("column_ctrl.msg.sql_locked"), parent=self)

    def _execute_script(self):
        text = self._sql_override or self._generated_sql or self.txt_sql.get("1.0", tk.END).strip()
        if not text:
            messagebox.showwarning(_t(APP_TITLE_KEY), _t("column_ctrl.msg.empty_sql"), parent=self)
            return
        self._append_log(_t("column_ctrl.log.execute"))
        if self._run_statements(text):
            self._append_log(_t("column_ctrl.log.execute_done"))

    # endregion SQL generation & execution

    # ------------------------------------------------------------------
    # region File handling & reset
    def _choose_sql_file(self):
        if not self._active_table:
            messagebox.showwarning(_t(APP_TITLE_KEY), _t("column_ctrl.msg.select_table_first"), parent=self)
            return
        path = filedialog.askopenfilename(
            parent=self,
            title=_t("column_ctrl.dialog.sql_file"),
            filetypes=[(_t("column_ctrl.filter.sql"), "*.sql"), (_t("column_ctrl.filter.all"), "*.*")],
        )
        if not path:
            return
        try:
            content = Path(path).read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = Path(path).read_text(encoding="cp932", errors="ignore")
        except Exception as exc:
            messagebox.showerror(_t(APP_TITLE_KEY), _t("column_ctrl.msg.read_sql_error", error=str(exc)), parent=self)
            return
        self._sql_file_path = path
        self._sql_file_content = content
        valid, warning = self._validate_sql_file(content)
        self._sql_file_valid = valid
        self._update_file_label()
        if warning:
            messagebox.showwarning(_t(APP_TITLE_KEY), warning, parent=self)
        if valid:
            self._sync_columns_from_create(content)
        self._write_sql_text(content)
        self._generated_sql = content
        self._sql_override = None
        self._set_sql_controls_state(True)
        self._append_log(_t("column_ctrl.log.file_loaded", path=os.path.basename(path)))

    def _validate_sql_file(self, content: str) -> tuple[bool, Optional[str]]:
        drop_tables = len(re.findall(r"\bDROP\s+TABLE\b", content, flags=re.IGNORECASE))
        create_ok = bool(re.search(r"CREATE\s+TABLE", content, flags=re.IGNORECASE))
        valid = drop_tables >= 1 and create_ok
        warning = None if valid else _t("column_ctrl.msg.file_structure_warning")
        return valid, warning

    def _sync_columns_from_create(self, sql_text: str) -> None:
        body = self._extract_create_body(sql_text)
        if not body:
            return
        entries = self._split_create_columns(body)
        if not entries:
            return
        new_order: List[str] = []
        for entry in entries:
            name = entry["name"]
            cfg = self._column_state.get(name)
            if cfg:
                cfg.removed = False
            else:
                cfg = ColumnConfig(name=name, source="new", custom_type=entry["type"], default_value=entry.get("default"))
                self._column_state[name] = cfg
            new_order.append(name)
        for name, cfg in self._column_state.items():
            if name not in new_order and cfg.source == "base":
                cfg.removed = True
        previous_order = list(self._column_order)
        self._column_order = list(new_order) + [name for name in previous_order if name not in new_order]
        self._refresh_column_list()
        self._update_data_section_state()
        self._append_log(_t("column_ctrl.log.sync_from_file"))

    def _extract_create_body(self, sql_text: str) -> Optional[str]:
        sanitized = re.sub(r"/\*.*?\*/", "", sql_text, flags=re.DOTALL)
        match = re.search(r"CREATE\s+TABLE\s+[^\(]+\(", sanitized, flags=re.IGNORECASE)
        if not match:
            return None
        start = match.end()
        depth = 1
        idx = start
        while idx < len(sanitized):
            ch = sanitized[idx]
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    return sanitized[start:idx]
            idx += 1
        return None

    def _split_create_columns(self, body: str) -> List[Dict[str, str]]:
        no_line_comments = []
        for line in body.splitlines():
            idx = line.find("--")
            if idx != -1:
                no_line_comments.append(line[:idx])
            else:
                no_line_comments.append(line)
        cleaned = "\n".join(no_line_comments)

        parts: List[str] = []
        token: List[str] = []
        depth = 0
        for ch in cleaned:
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth = max(0, depth - 1)
            if ch == "," and depth == 0:
                part = "".join(token).strip()
                if part:
                    parts.append(part)
                token = []
            else:
                token.append(ch)
        remainder = "".join(token).strip()
        if remainder:
            parts.append(remainder)
        allowed_types = {
            "VARCHAR2",
            "NVARCHAR2",
            "CHAR",
            "NCHAR",
            "NUMBER",
            "INTEGER",
            "INT",
            "SMALLINT",
            "FLOAT",
            "REAL",
            "DECIMAL",
            "NUMERIC",
            "DATE",
            "TIMESTAMP",
            "CLOB",
            "NCLOB",
            "BLOB",
            "RAW",
            "LONG",
        }
        results: List[Dict[str, str]] = []
        for raw in parts:
            line = raw.strip()
            if not line or line.upper().startswith("CONSTRAINT"):
                continue
            match = re.match(r'"?([A-Za-z0-9_]+)"?\s+(.*)', line)
            if not match:
                continue
            name = match.group(1).upper()
            rest = match.group(2).strip()
            default_val = self._extract_default_value(rest)
            dtype = self._extract_type_part(rest)
            # bỏ qua nếu không nhận diện được kiểu dữ liệu hợp lệ
            if not dtype:
                continue
            base_match = re.match(r"[A-Z0-9_]+", dtype.upper())
            base_type = base_match.group(0) if base_match else ""
            if base_type not in allowed_types:
                continue
            results.append({"name": name, "type": dtype, "default": default_val})
        return results

    def _extract_type_part(self, fragment: str) -> str:
        default_idx = re.search(r"\bDEFAULT\b", fragment, flags=re.IGNORECASE)
        type_part = fragment
        if default_idx:
            type_part = fragment[: default_idx.start()].strip()
        type_part = re.sub(r"\bNOT\s+NULL\b", "", type_part, flags=re.IGNORECASE)
        return type_part.strip().rstrip(",")

    def _extract_default_value(self, fragment: str) -> Optional[str]:
        match = re.search(r"\bDEFAULT\b\s+(.*)", fragment, flags=re.IGNORECASE)
        if not match:
            return None
        remainder = match.group(1).strip()
        remainder = re.sub(r"\bON\s+NULL\b", "", remainder, flags=re.IGNORECASE)
        stop = re.search(r"\bNOT\s+NULL\b|\bNULL\b|,", remainder, flags=re.IGNORECASE)
        if stop:
            remainder = remainder[: stop.start()].strip()
        if not remainder:
            return None
        if remainder.startswith(("'", '"')) and remainder.endswith(("'", '"')):
            return remainder[1:-1]
        return remainder

    def _reset_changes(self):
        if not self._active_table:
            return
        self._append_log(_t("column_ctrl.log.reset"))
        self.on_table_ready(self._active_table["full"])

    # endregion File handling & reset

    # ------------------------------------------------------------------
    def _apply_language(self) -> None:
        super()._apply_language()
        widgets = {
            getattr(self, "grp_search", None): ("text", _t("column_ctrl.section.search")),
            getattr(self, "lbl_table", None): ("text", _t("column_ctrl.label.table_name")),
            getattr(self, "lbl_backup_table", None): ("text", _t("column_ctrl.label.backup_table")),
            getattr(self, "grp_columns", None): ("text", _t("column_ctrl.section.columns")),
            getattr(self, "grp_data", None): ("text", _t("column_ctrl.section.data")),
            getattr(self, "grp_sql", None): ("text", _t("column_ctrl.section.sql")),
            getattr(self, "grp_log", None): ("text", _t("column_ctrl.section.log")),
            getattr(self, "btn_choose_sql", None): ("text", _t("column_ctrl.btn.choose_sql")),
            getattr(self, "btn_generate_sql", None): ("text", _t("column_ctrl.btn.generate_sql")),
            getattr(self, "btn_reset", None): ("text", _t("column_ctrl.btn.reset")),
            getattr(self, "btn_update_sql", None): ("text", _t("column_ctrl.btn.update_sql")),
            getattr(self, "btn_execute", None): ("text", _t("column_ctrl.btn.execute")),
            getattr(self, "lbl_column_type", None): ("text", _t("column_ctrl.label.column_type")),
            getattr(self, "lbl_default_value", None): ("text", _t("column_ctrl.label.default_value")),
            getattr(self, "lbl_values", None): ("text", _t("column_ctrl.label.values")),
            getattr(self, "lbl_value_hint", None): ("text", _t("column_ctrl.label.value_hint")),
        }
        for widget, (option, value) in widgets.items():
            if widget:
                widget.configure(**{option: value})
        if hasattr(self, "lbl_sql_file"):
            self._update_file_label()
        if hasattr(self, "cmb_column_type"):
            self.cmb_column_type.configure(values=self._default_column_types())
