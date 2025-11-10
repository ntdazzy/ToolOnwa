# log_viewer.py
import logging
import os
import re
import subprocess
import sys
import tkinter as tk
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, ttk, messagebox
from typing import Any, List, Optional, Sequence, Tuple

from core import i18n

# Regular expressions for parsing
SCREEN_ID_RE = re.compile(r"MU[A-Z]{2}\d{4}")
DATE_PREFIX_RE = re.compile(r"^\d{4}-\d{2}-\d{2} ")
THREAD_RE = re.compile(r"--- \[([^\]]+)\]")
REQUEST_RE = re.compile(r"(?:GET|POST|PUT|DELETE)\s+/(MU[A-Z]{2}\d{4})")

# Mapping of thread to last seen screen ID

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parents[1]

APP_TITLE_KEY = "common.app_title"

def resource_path(rel: str) -> str:
    base = getattr(sys, "_MEIPASS", str(ROOT_DIR))
    return os.path.join(base, rel)

DEFAULT_ICON_PATH = resource_path(os.path.join("icons", "logo.ico"))

thread_screen_map: dict[str, str] = {}

logger = logging.getLogger("ToolVIP.LogViewer")


MAX_DISPLAY_ROWS = 2000
EMPTY_MARK = "[ ]"
CHECK_MARK = "[x]"


@dataclass
class SqlEntry:
    """Thông tin một câu SQL kèm metadata cần thiết."""

    timestamp: str
    screen_id: Optional[str]
    sql_type: str
    function: str
    params: List[str]
    raw_sql: str
    sql: str


@dataclass
class ErrorEntry:
    """Thông tin một dòng lỗi và phần stack trace tương ứng."""

    timestamp: str
    screen_id: Optional[str]
    summary: str
    details: str


def _split_param_chunks(text: str) -> List[str]:
    """Tách chuỗi tham số thành các cụm độc lập, giữ nguyên nội dung trong ngoặc."""
    text = text.strip().rstrip(",")
    if not text:
        return []
    chunks: List[str] = []
    buf: List[str] = []
    depth = 0
    for ch in text:
        if ch == "," and depth == 0:
            chunk = "".join(buf).strip()
            if chunk:
                chunks.append(chunk)
            buf = []
            continue
        buf.append(ch)
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(depth - 1, 0)
    tail = "".join(buf).strip()
    if tail:
        chunks.append(tail)
    return chunks


def _parse_param_text(text: str) -> List[Tuple[str, str]]:
    """Chuyển chuỗi giá trị tham số thành cặp (giá trị, kiểu)."""
    params: List[Tuple[str, str]] = []
    for chunk in _split_param_chunks(text):
        m = re.match(r"(.*)\((.*)\)", chunk)
        if m:
            val = m.group(1).strip()
            typ = m.group(2).strip()
        else:
            val = chunk.strip()
            typ = "String"
        params.append((val, typ))
    return params


def _parse_param_line(line: str, *, has_label: bool = True) -> List[Tuple[str, str]]:
    """Tách dòng Parameters thành danh sách giá trị + kiểu."""
    text = ""
    if has_label:
        parts = line.split("Parameters:", 1)
        text = parts[1] if len(parts) > 1 else ""
    else:
        if "Parameters:" in line:
            parts = line.split("Parameters:", 1)
            text = parts[1] if len(parts) > 1 else ""
        elif "]" in line:
            text = line.rsplit("]", 1)[1]
        else:
            text = line
    return _parse_param_text(text)


def _collect_param_blocks(
    lines: Sequence[str],
    start_index: int,
    thread: Optional[str],
) -> List[List[Tuple[str, str]]]:
    """
    Gom nhóm các dòng Parameters liên quan tới câu SQL starting tại start_index.
    Hỗ trợ cả trường hợp nhiều dòng Parameters cùng thuộc một batch insert.
    """
    blocks: List[List[Tuple[str, str]]] = []
    current: List[Tuple[str, str]] = []
    total = len(lines)
    j = start_index + 1
    while j < total:
        line = lines[j]
        if "Preparing:" in line and "DEBUG" in line:
            break
        if DATE_PREFIX_RE.match(line) and "Parameters:" not in line and not line.strip().startswith((" ", "\t")):
            # Gặp log mới không phải parameters -> kết thúc block hiện tại
            if current:
                blocks.append(current)
                current = []
            if thread is None:
                break
        if "Parameters:" in line:
            thr_match = THREAD_RE.search(line)
            if thread and thr_match and thr_match.group(1) != thread:
                j += 1
                continue
            parsed = _parse_param_line(line, has_label=True)
            if parsed:
                if current:
                    blocks.append(current)
                current = parsed
        elif current and line.strip():
            # Continuation line (không có tiền tố Parameters)
            continuation = _parse_param_line(line, has_label=False)
            if continuation:
                current.extend(continuation)
        j += 1
    if current:
        blocks.append(current)
    return blocks

def parse_sql(file_path: str) -> List[SqlEntry]:
    """Đọc file log và gom danh sách các câu SQL."""
    entries: List[SqlEntry] = []
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
    except Exception as e:
        logger.exception("Could not read log file %s", file_path)
        raise RuntimeError(f"Could not read log file {file_path}: {e}")

    global thread_screen_map
    thread_screen_map = {}
    i = 0
    total = len(lines)
    while i < total:
        line = lines[i]
        # Update thread context mapping
        thread = None
        m_thread = THREAD_RE.search(line)
        if m_thread:
            thread = m_thread.group(1)
            req_match = REQUEST_RE.search(line)
            if req_match:
                thread_screen_map[thread] = req_match.group(1)
            elif "service.MU" in line:
                m = SCREEN_ID_RE.search(line)
                if m:
                    thread_screen_map[thread] = m.group(0)

        if "Preparing:" in line and "DEBUG" in line:
            timestamp = line[:19] if DATE_PREFIX_RE.match(line) else ""
            try:
                prefix, rest = line.split(": ==>", 1)
            except ValueError:
                i += 1
                continue
            func_tokens = prefix.rstrip().split()
            function = func_tokens[-1].split(".")[-1] if func_tokens else ""
            try:
                raw_sql = rest.split("Preparing:", 1)[1].strip()
            except IndexError:
                i += 1
                continue

            param_blocks = _collect_param_blocks(lines, i, thread)

            # Replace ? with each parameter set
            def replace_placeholders(query: str, parameters: Sequence[Tuple[str, str]]) -> str:
                param_iter = iter(parameters)
                def repl(_: re.Match) -> str:
                    try:
                        val, typ = next(param_iter)
                    except StopIteration:
                        return "?"
                    is_numeric = bool(re.match(r"^-?\d+(\.\d+)?$", val)) and (typ and "String" not in typ)
                    return val if is_numeric else f"'{val}'"
                return re.sub(r"\?", repl, query)

            # Screen id nearby or via thread map
            screen_id: Optional[str] = None
            for k in range(max(0, i - 5), min(i + 6, total)):
                m = SCREEN_ID_RE.search(lines[k])
                if m:
                    screen_id = m.group(0)
                    break
            if screen_id is None and thread:
                screen_id = thread_screen_map.get(thread, None)

            blocks = param_blocks if param_blocks else [[]]
            for params in blocks:
                final_sql = replace_placeholders(raw_sql, params)
                sql_type = final_sql.strip().split()[0].upper() if final_sql.strip() else ""
                param_values = [val for val, _ in params]
                entries.append(SqlEntry(timestamp, screen_id, sql_type, function, param_values, raw_sql, final_sql))
        i += 1
    try:
        return sorted(entries, key=lambda e: e.timestamp, reverse=True)
    except Exception:
        logger.exception("Failed to sort SQL entries")
        return entries

def parse_errors(file_path: str) -> List[ErrorEntry]:
    """Đọc file log và gom danh sách lỗi kèm chi tiết."""
    errors: List[ErrorEntry] = []
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
    except Exception as e:
        logger.exception("Could not read log file %s", file_path)
        raise RuntimeError(f"Could not read log file {file_path}: {e}")

    i = 0
    total = len(lines)
    while i < total:
        line = lines[i]
        if "ERROR" in line:
            timestamp = line[:19] if DATE_PREFIX_RE.match(line) else ""
            details_lines = [line.rstrip("\n")]
            i += 1
            while i < total:
                next_line = lines[i]
                if DATE_PREFIX_RE.match(next_line):
                    break
                details_lines.append(next_line.rstrip("\n"))
                i += 1
            screen_id: Optional[str] = None
            for m in SCREEN_ID_RE.finditer("\n".join(details_lines)):
                screen_id = m.group(0)
                break
            if screen_id is None:
                m_thread = THREAD_RE.search(details_lines[0])
                if m_thread:
                    thread = m_thread.group(1)
                    if thread in thread_screen_map:
                        screen_id = thread_screen_map[thread]
            summary = details_lines[0]
            if "ERROR" in summary:
                parts = summary.split("ERROR", 1)[1].strip()
                if " - " in parts:
                    parts = parts.split(" - ", 1)[1].strip()
                summary = parts
            details = "\n".join(details_lines)
            errors.append(ErrorEntry(timestamp, screen_id, summary, details))
        else:
            i += 1
    try:
        return sorted(errors, key=lambda e: e.timestamp, reverse=True)
    except Exception:
        logger.exception("Failed to sort error entries")
        return errors

def format_sql(sql: str) -> str:
    """Chèn xuống dòng tại các từ khóa SQL để dễ đọc hơn."""
    keywords = [
        "ORDER BY", "GROUP BY", "INNER JOIN", "LEFT JOIN", "RIGHT JOIN",
        "INSERT INTO", "VALUES", "DELETE FROM", "DELETE", "UPDATE",
        "SET", "SELECT", "FROM", "WHERE", "AND", "OR", "ON", "HAVING",
        "JOIN", "CASE", "WHEN", "ELSE", "END"
    ]
    pattern = re.compile(r"\b(" + "|".join(map(re.escape, keywords)) + r")\b", re.IGNORECASE)

    def repl(match: re.Match) -> str:
        kw = match.group(1)
        return "\n" + kw.upper()

    formatted = pattern.sub(repl, raw_sql := sql)
    lines = formatted.strip().split("\n")
    for idx in range(1, len(lines)):
        lines[idx] = lines[idx].strip()
    return "\n".join(lines)

class LogViewerApp:
    """Lớp điều khiển giao diện xem và phân tích log MU."""

    def __init__(self, root: tk.Misc, icon_path: Optional[str] = None) -> None:
        """Khởi tạo giao diện chính và trạng thái ban đầu của log viewer."""
        self.root = root
        self.icon_path = icon_path or (DEFAULT_ICON_PATH if os.path.isfile(DEFAULT_ICON_PATH) else None)
        self._apply_icon(self.root)
        self.sql_entries: List[SqlEntry] = []
        self.error_entries: List[ErrorEntry] = []
        self._visible_count = 0
        self._total_count = 0

        # Language handling
        self._key_map = {
            "choose_log": "log.btn.choose",
            "choose_new": "log.btn.choose_new",
            "choose_recent": "log.btn.choose_recent",
            "choose_source": "log.dialog.choose_source",
            "log_type": "log.label.type",
            "sql": "log.option.sql",
            "error": "log.option.error",
            "command_type": "log.label.command_type",
            "screen": "log.label.screen",
            "screen_id": "log.column.screen_id",
            "time": "log.column.time",
            "command": "log.column.command",
            "function": "log.column.function",
            "params": "log.column.params",
            "sql_filled": "log.column.sql",
            "summary": "log.column.summary",
            "details": "log.column.details",
            "copy": "log.btn.copy",
            "close": "log.btn.close",
            "copied": "log.msg.copied",
            "sql_copied": "log.msg.sql_copied",
            "details_copied": "log.msg.details_copied",
            "sql_detail_title": "log.detail.sql_title",
            "error_detail_title": "log.detail.error_title",
            "error_summary": "log.column.summary",
            "error_details": "log.column.details",
            "field": "log.column.field",
            "value": "log.column.value",
            "keyword": "log.label.keyword",
            "search_btn": "log.btn.search",
            "time_format_full": "log.option.time_full",
            "time_format_time": "log.option.time_time",
            "time_display": "log.label.time_display",
            "param_display": "log.label.param_display",
            "param_show": "log.option.param_show",
            "param_hide": "log.option.param_hide",
            "toggle_param_sql": "log.btn.toggle_param_sql",
            "filters_section": "log.section.filters",
            "results_section": "log.section.results",
            "file_label": "log.label.file",
            "open_folder": "log.btn.open_folder",
            "save_log": "log.btn.save_log",
            "view_saved_logs": "log.btn.view_saved",
            "delete_log": "log.btn.delete_log",
            "clear": "log.btn.clear",
            "refresh": "log.btn.refresh",
            "reset_filters": "log.btn.reset",
            "summary_status": "log.status.summary",
            "open_folder_error": "log.msg.open_folder_error",
            "no_file": "log.msg.no_file",
            "msg_save_none": "log.msg.save_none",
            "msg_save_success": "log.msg.save_success",
            "msg_no_saved_log": "log.msg.no_saved_log",
            "msg_delete_confirm": "log.msg.delete_confirm",
            "msg_delete_done": "log.msg.delete_done",
            "msg_delete_none": "log.msg.delete_none",
            "msg_delete_error": "log.msg.delete_error",
            "msg_no_recent_log": "log.msg.no_recent_log",
            "msg_choose_prompt": "log.msg.choose_prompt",
            "important_only": "log.label.important_only",
            "saved_logs_title": "log.dialog.saved_title",
            "saved_at": "log.column.saved_at",
            "recent_title": "log.dialog.recent_title",
            "filename": "log.column.filename",
            "path": "log.column.path",
            "opened_at": "log.column.opened_at",
            "size": "log.column.size",
        }

        def _(key: str, **kwargs) -> str:
            full_key = self._key_map.get(key, f"log.{key}")
            return i18n.translate(full_key, **kwargs)

        self._ = _
        self._lang_listener = self._handle_language_change
        i18n.add_listener(self._lang_listener)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        style = ttk.Style()
        try:
            style.theme_use(style.theme_use())
        except Exception:
            pass
        style.configure("Treeview", borderwidth=0, relief="flat", rowheight=25)
        style.configure("Treeview.Heading", borderwidth=0, relief="flat")

        container = ttk.Frame(root, padding=12)
        container.pack(fill="both", expand=True)
        container.columnconfigure(0, weight=1)
        container.rowconfigure(1, weight=1)

        filter_side = ttk.Frame(container, padding=(12, 12))
        filter_side.grid(row=0, column=0, sticky="ew")
        filter_side.columnconfigure(0, weight=1)

        content_side = ttk.Frame(container, padding=(12, 12))
        content_side.grid(row=1, column=0, sticky="nsew")
        content_side.columnconfigure(0, weight=1)
        content_side.rowconfigure(2, weight=1)

        # ----- Filter panel -----
        self.frm_filters = ttk.LabelFrame(filter_side, text=self._("filters_section"), padding=10)
        self.frm_filters.grid(row=0, column=0, sticky="ew")
        for col in range(3):
            self.frm_filters.columnconfigure(col, weight=1)

        controls_row = ttk.Frame(self.frm_filters)
        controls_row.grid(row=0, column=0, columnspan=3, sticky="ew")
        controls_row.columnconfigure(0, weight=1)
        controls_row.columnconfigure(1, weight=1)
        left_controls = ttk.Frame(controls_row)
        left_controls.grid(row=0, column=0, sticky="w")
        self.btn_choose = ttk.Button(left_controls, text=self._("choose_log"), command=self.choose_file, width=10)
        self.btn_choose.pack(side="left", padx=(0, 6))
        self.btn_refresh = ttk.Button(left_controls, text=self._("refresh"), command=self.refresh_file)
        self.btn_refresh.pack(side="left", padx=(0, 6))
        self.btn_reset_filters = ttk.Button(left_controls, text=self._("reset_filters"), command=self.reset_filters)
        self.btn_reset_filters.pack(side="left")

        right_controls = ttk.Frame(controls_row)
        right_controls.grid(row=0, column=1, sticky="e")
        self.btn_open_folder = ttk.Button(right_controls, text=self._("open_folder"), command=self.open_current_folder)
        self.btn_open_folder.pack(side="left")
        self.btn_save_log = ttk.Button(right_controls, text=self._("save_log"), command=self.save_selected_logs, state="disabled")
        self.btn_save_log.pack(side="left", padx=(6, 0))
        self.btn_saved_logs = ttk.Button(right_controls, text=self._("view_saved_logs"), command=self.show_saved_logs, state="disabled")
        self.btn_saved_logs.pack(side="left", padx=(6, 0))

        ttk.Separator(self.frm_filters).grid(row=1, column=0, columnspan=3, sticky="ew", pady=(10, 8))

        row_index = 2

        log_command_row = ttk.Frame(self.frm_filters)
        log_command_row.grid(row=row_index, column=0, columnspan=3, sticky="ew", pady=(0, 4))
        log_command_row.columnconfigure(0, weight=0)
        log_command_row.columnconfigure(1, weight=1)
        self.log_type_var = tk.StringVar(value="SQL")
        log_group = ttk.Frame(log_command_row)
        log_group.grid(row=0, column=0, sticky="w")
        self.lbl_log_type = ttk.Label(log_group, text=self._("log_type"))
        self.lbl_log_type.pack(side="left", padx=(0, 6))
        self.rb_sql = ttk.Radiobutton(log_group, text=self._("sql"), variable=self.log_type_var, value="SQL", command=self.update_filters)
        self.rb_sql.pack(side="left")
        self.rb_error = ttk.Radiobutton(log_group, text=self._("error"), variable=self.log_type_var, value="ERROR", command=self.update_filters)
        self.rb_error.pack(side="left", padx=(12, 0))

        command_group = ttk.Frame(log_command_row)
        command_group.grid(row=0, column=1, sticky="w", padx=(24, 0))
        self.sql_command_row = command_group
        self.lbl_cmd = ttk.Label(command_group, text=self._("command_type"))
        self.lbl_cmd.pack(side="left", padx=(0, 6))
        self.sql_command_var = tk.StringVar(value="ALL")
        commands_frame = ttk.Frame(command_group)
        commands_frame.pack(side="left")
        self.cmd_buttons = []
        for cmd in ["ALL", "SELECT", "INSERT", "UPDATE", "DELETE"]:
            btn = ttk.Radiobutton(commands_frame, text=cmd, variable=self.sql_command_var, value=cmd, command=self.refresh_table)
            btn.pack(side="left", padx=(0, 10))
            self.cmd_buttons.append(btn)

        row_index += 1

        screen_row = ttk.Frame(self.frm_filters)
        screen_row.grid(row=row_index, column=0, columnspan=3, sticky="ew", pady=(8, 0))
        screen_row.columnconfigure(1, weight=1)
        screen_row.columnconfigure(3, weight=1)
        self.lbl_screen = ttk.Label(screen_row, text=self._("screen"))
        self.lbl_screen.grid(row=0, column=0, sticky="w", padx=(0, 6))
        self.screen_var = tk.StringVar(value="ALL")
        self.combo_screen = ttk.Combobox(screen_row, textvariable=self.screen_var, values=["ALL"], state="readonly")
        self.combo_screen.grid(row=0, column=1, sticky="ew")
        self.combo_screen.configure(takefocus=True)
        self.combo_screen.bind("<<ComboboxSelected>>", lambda _e: self.refresh_table())

        self.lbl_keyword = ttk.Label(screen_row, text=self._("keyword"))
        self.lbl_keyword.grid(row=0, column=2, sticky="w", padx=(16, 6))
        self.search_var = tk.StringVar()
        entry_container = ttk.Frame(screen_row)
        entry_container.grid(row=0, column=3, sticky="ew")
        entry_container.columnconfigure(0, weight=1)
        self.entry_search = ttk.Entry(entry_container, textvariable=self.search_var)
        self.entry_search.grid(row=0, column=0, sticky="ew")
        self.btn_search = ttk.Button(entry_container, text=self._("search_btn"), command=self.perform_search, width=10)
        self.btn_search.grid(row=0, column=1, padx=(8, 0))
        self.btn_clear_search = ttk.Button(entry_container, text=self._("clear"), command=self.clear_search, width=8)
        self.btn_clear_search.grid(row=0, column=2, padx=(6, 0))

        row_index += 1

        toggle_row = ttk.Frame(self.frm_filters)
        toggle_row.grid(row=row_index, column=0, columnspan=3, sticky="ew", pady=(10, 0))
        toggle_row.columnconfigure(0, weight=1)
        toggle_row.columnconfigure(1, weight=1)
        toggle_row.columnconfigure(2, weight=1)

        self.time_row = ttk.Frame(toggle_row)
        self.time_row.grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.lbl_time_display = ttk.Label(self.time_row, text=self._("time_display"))
        self.lbl_time_display.grid(row=0, column=0, sticky="w", padx=(0, 6))
        time_options = ttk.Frame(self.time_row)
        time_options.grid(row=0, column=1, sticky="w")
        self.time_format_var = tk.StringVar(value="full")
        self.rb_time_full = ttk.Radiobutton(time_options, text=self._("time_format_full"), variable=self.time_format_var, value="full", command=self.refresh_table)
        self.rb_time_full.pack(side="left", padx=(0, 8))
        self.rb_time_time = ttk.Radiobutton(time_options, text=self._("time_format_time"), variable=self.time_format_var, value="time", command=self.refresh_table)
        self.rb_time_time.pack(side="left")

        self.show_params_var = tk.BooleanVar(value=False)
        self.param_row = ttk.Frame(toggle_row)
        self.param_row.grid(row=0, column=1, sticky="w", padx=(0, 8))
        self.lbl_param_display = ttk.Label(self.param_row, text=self._("param_display"))
        self.lbl_param_display.grid(row=0, column=0, sticky="w", padx=(0, 6))
        self.chk_params = ttk.Checkbutton(self.param_row, variable=self.show_params_var, command=self.on_toggle_params)
        self.chk_params.grid(row=0, column=1, sticky="w")
        self._update_param_check_text()

        self.important_only_var = tk.BooleanVar(value=False)
        self.important_row = ttk.Frame(toggle_row)
        self.important_row.grid(row=0, column=2, sticky="w")
        self.lbl_important = ttk.Label(self.important_row, text=self._("important_only"))
        self.lbl_important.grid(row=0, column=0, sticky="w", padx=(0, 6))
        self.chk_important = ttk.Checkbutton(self.important_row, variable=self.important_only_var, command=self.on_toggle_important)
        self.chk_important.grid(row=0, column=1, sticky="w")

        # ----- Content panel -----
        self.file_path_var = tk.StringVar(value=self._("no_file"))
        self.summary_var = tk.StringVar(value="")
        self._refresh_file_label()
        self._recent_logs: list[dict[str, object]] = []

        self.sql_entries_full: List[SqlEntry] = []
        self.sql_entries: List[SqlEntry] = []
        self.error_entries_full: List[ErrorEntry] = []
        self.error_entries: List[ErrorEntry] = []
        self._log_truncated_sql = False
        self._log_truncated_error = False

        header = ttk.Frame(content_side)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 4))
        header.columnconfigure(1, weight=1)
        self.lbl_file_caption = ttk.Label(header, text=self._("file_label"))
        self.lbl_file_caption.grid(row=0, column=0, sticky="w")
        self.lbl_file_path = ttk.Label(header, textvariable=self.file_path_var, wraplength=360, justify="left")
        self.lbl_file_path.grid(row=0, column=1, sticky="w", padx=(6, 0))
        self.lbl_summary = ttk.Label(header, textvariable=self.summary_var, anchor="e")
        self.lbl_summary.grid(row=0, column=2, sticky="e", padx=(6, 0))

        ttk.Separator(content_side).grid(row=1, column=0, sticky="ew", pady=(8, 8))

        self._sql_columns_full: Tuple[str, ...] = ("mark", "screen", "timestamp", "command", "function", "params", "sql")
        self._sql_columns_important: Tuple[str, ...] = ("mark", "screen", "timestamp", "params", "sql")
        self.error_columns: Tuple[str, ...] = ("timestamp", "screen", "summary")
        self._column_meta: dict[str, dict[str, Any]] = {
            "mark": {"heading": "", "width": 38, "stretch": False, "anchor": "center"},
            "screen": {"heading": "screen_id", "width": 108, "stretch": False},
            "timestamp": {"heading": "time", "width": 160, "stretch": False},
            "command": {"heading": "command", "width": 96, "stretch": False},
            "function": {"heading": "function", "width": 156, "stretch": False},
            "params": {"heading": "params", "width": 220, "stretch": False},
            "sql": {"heading": "sql_filled", "width": 520, "stretch": True},
            "summary": {"heading": "summary", "width": 260, "stretch": True},
        }
        self._mark_symbol = CHECK_MARK
        self._empty_mark = EMPTY_MARK
        self._marked_keys: set[str] = set()
        self._item_to_key: dict[str, str] = {}
        self._entry_by_key: dict[str, SqlEntry] = {}
        self._saved_logs: List[dict[str, Any]] = []
        self._recent_loaded = False

        tree_frame = ttk.LabelFrame(content_side, text=self._("results_section"), padding=6, borderwidth=2, relief="ridge")
        tree_frame.grid(row=2, column=0, sticky="nsew")
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)
        self.frm_results = tree_frame

        scroll_y = ttk.Scrollbar(tree_frame, orient="vertical")
        scroll_y.grid(row=0, column=1, sticky="ns")
        scroll_x = ttk.Scrollbar(tree_frame, orient="horizontal")
        scroll_x.grid(row=1, column=0, sticky="ew")
        self.border_frame = tk.Frame(tree_frame, bd=1, relief="solid")
        self.border_frame.grid(row=0, column=0, sticky="nsew")
        self.border_frame.columnconfigure(0, weight=1)
        self.border_frame.rowconfigure(0, weight=1)
        self.tree = ttk.Treeview(
            self.border_frame,
            columns=(),
            show="headings",
            yscrollcommand=scroll_y.set,
            xscrollcommand=scroll_x.set,
        )
        self._configure_tree_columns()
        self.tree.grid(row=0, column=0, sticky="nsew")
        scroll_y.config(command=self.tree.yview)
        scroll_x.config(command=self.tree.xview)
        self.empty_label = ttk.Label(self.border_frame, text=self._("msg.no_results"), anchor="center")
        self.empty_label.place_forget()
        self.tree.bind("<Button-1>", self._on_tree_click, add="+")
        self.entry_search.bind("<Return>", lambda _e: self.perform_search())
        self.root.bind_all("<Control-f>", self.focus_search_entry)
        self.tree.bind("<Double-1>", self.on_double_click)
        self._update_action_buttons()

        # Global copy: Ctrl+C copies selected rows, or all rows if none selected.
        self.root.bind_all("<Control-c>", self.copy_all_or_selected)
        self.tree.bind("<Control-c>", self.copy_all_or_selected)

        # Mapping rows to entries
        self.row_to_entry: dict[str, object] = {}
        self._populate_rows: List[Tuple[Tuple[Any, ...], Tuple[str, ...], object, Optional[str]]] = []
        self._populate_index = 0
        self._populate_job: Optional[str] = None

        # Row styling tags
        self.tree.tag_configure("odd_row", background="#f9f9f9")
        self.tree.tag_configure("even_row", background="#ffffff")
        # Tag for matched search results (yellow background)
        self.tree.tag_configure("match", background="#fff2a8")

        # Initial language update
        self._apply_language()

    def _apply_language(self) -> None:
        """Cập nhật toàn bộ text theo ngôn ngữ i18n hiện tại."""
        _ = self._
        self.root.title(i18n.translate("log.title"))
        if hasattr(self, "frm_filters"):
            self.frm_filters.configure(text=_("filters_section"))
        if hasattr(self, "frm_results"):
            self.frm_results.configure(text=_("results_section"))
        self.btn_choose.configure(text=_("choose_log"))
        self.btn_refresh.configure(text=_("refresh"))
        self.btn_reset_filters.configure(text=_("reset_filters"))
        self.btn_save_log.configure(text=_("save_log"))
        self.btn_saved_logs.configure(text=_("view_saved_logs"))
        self.btn_open_folder.configure(text=_("open_folder"))
        self.lbl_log_type.configure(text=_("log_type"))
        self.rb_sql.configure(text=_("sql"))
        self.rb_error.configure(text=_("error"))
        self.lbl_cmd.configure(text=_("command_type"))
        self.lbl_screen.configure(text=_("screen"))
        self.lbl_keyword.configure(text=_("keyword"))
        self.btn_search.configure(text=_("search_btn"))
        self.btn_clear_search.configure(text=_("clear"))
        self.lbl_time_display.configure(text=_("time_display"))
        self.rb_time_full.configure(text=_("time_format_full"))
        self.rb_time_time.configure(text=_("time_format_time"))
        self.lbl_param_display.configure(text=_("param_display"))
        self._update_param_check_text()
        self.lbl_important.configure(text=_("important_only"))
        self.lbl_file_caption.configure(text=_("file_label"))
        self.empty_label.configure(text=_("msg.no_results"))
        self._configure_tree_columns()
        self._refresh_file_label()
        self._update_summary_label()

    def _handle_language_change(self, _: str) -> None:
        """Lắng nghe thay đổi ngôn ngữ từ i18n."""
        self._apply_language()

    def _get_active_columns(self) -> Tuple[str, ...]:
        if self.log_type_var.get() == "SQL":
            return self._sql_columns_important if self.important_only_var.get() else self._sql_columns_full
        return self.error_columns

    def _configure_tree_columns(self) -> None:
        if not hasattr(self, "tree"):
            return
        cols = self._get_active_columns()
        self.tree.configure(columns=cols)
        for col in cols:
            meta = self._column_meta.get(col, {})
            heading_key = meta.get("heading")
            heading_text = "" if not heading_key else self._(heading_key)
            self.tree.heading(col, text=heading_text)
            width = meta.get("width", 120)
            if col == "params" and not self.show_params_var.get():
                width = 70
            if col == "timestamp" and self.time_format_var.get() == "time":
                width = 118
            if col in {"screen", "command"}:
                width = min(width, 110 if col == "screen" else 96)
            stretch = meta.get("stretch", False)
            anchor = meta.get("anchor", "w")
            self.tree.column(col, width=width, stretch=stretch, anchor=anchor)

    def refresh_file(self) -> None:
        """Tải lại log đang mở nếu có."""
        file_path = getattr(self, "current_file", None)
        if not file_path:
            return
        self._load_log_file(file_path, update_recent=False)

    def choose_file(self) -> None:
        self._ensure_recent_loaded()
        popup = tk.Toplevel(self.root)
        popup.title(self._("choose_log"))
        popup.transient(self.root)
        popup.resizable(False, False)
        try:
            popup.grab_set()
        except Exception:
            pass
        try:
            self._apply_icon(popup)
        except Exception:
            pass
        frame = ttk.Frame(popup, padding=12)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text=self._("choose_source"), anchor="center").pack(fill="x", pady=(0, 12))
        ttk.Button(frame, text=self._("choose_new"), command=lambda: self._choose_new_log(popup)).pack(fill="x", pady=(0, 6))
        ttk.Button(frame, text=self._("choose_recent"), command=lambda: self._show_recent_logs_dialog(popup)).pack(fill="x", pady=(0, 6))
        ttk.Button(frame, text=self._("close"), command=popup.destroy).pack(fill="x", pady=(4, 0))
        self._center_child(popup, width=260, height=160)

    def _center_child(self, window: tk.Toplevel, *, width: int, height: int) -> None:
        try:
            window.update_idletasks()
            parent_x = self.root.winfo_rootx()
            parent_y = self.root.winfo_rooty()
            parent_w = self.root.winfo_width()
            parent_h = self.root.winfo_height()
            x = parent_x + max((parent_w - width) // 2, 0)
            y = parent_y + max((parent_h - height) // 2, 0)
            window.geometry(f"{width}x{height}+{x}+{y}")
        except Exception:
            pass

    def _choose_new_log(self, dialog: Optional[tk.Toplevel] = None) -> None:
        if dialog and dialog.winfo_exists():
            dialog.destroy()
        file_path = filedialog.askopenfilename(
            title=self._("choose_log"),
            filetypes=[("Log files", "*.log"), ("All files", "*.*")],
        )
        if not file_path:
            return
        if self._load_log_file(file_path):
            self.current_file = file_path

    def _show_recent_logs_dialog(self, dialog: Optional[tk.Toplevel] = None) -> None:
        if dialog and dialog.winfo_exists():
            dialog.destroy()
        self._ensure_recent_loaded()
        if not self._recent_logs:
            messagebox.showinfo(i18n.translate(APP_TITLE_KEY), self._("msg_no_recent_log"), parent=self.root)
            return
        win = tk.Toplevel(self.root)
        win.title(self._("recent_title"))
        win.geometry("720x360")
        win.minsize(640, 320)
        win.transient(self.root)
        try:
            win.grab_set()
        except Exception:
            pass
        try:
            self._apply_icon(win)
        except Exception:
            pass
        frame = ttk.Frame(win, padding=12)
        frame.pack(fill="both", expand=True)
        columns = ("name", "path", "opened_at", "size")
        tree = ttk.Treeview(frame, columns=columns, show="headings")
        tree.heading("name", text=self._("filename"))
        tree.heading("path", text=self._("path"))
        tree.heading("opened_at", text=self._("opened_at"))
        tree.heading("size", text=self._("size"))
        tree.column("name", width=180, stretch=False)
        tree.column("path", width=360, stretch=True)
        tree.column("opened_at", width=140, stretch=False)
        tree.column("size", width=90, stretch=False, anchor="e")
        tree.pack(fill="both", expand=True)
        scrollbar_y = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        scrollbar_y.pack(side="right", fill="y")
        tree.configure(yscrollcommand=scrollbar_y.set)
        record_map: dict[str, dict[str, object]] = {}
        for rec in self._recent_logs:
            path_val = rec.get("path", "")
            opened = rec.get("opened_at")
            if isinstance(opened, datetime):
                opened_display = opened.strftime("%Y-%m-%d %H:%M:%S")
            else:
                opened_display = str(opened)
            size_display = self._format_size(rec.get("size"))
            iid = tree.insert(
                "",
                "end",
                values=(rec.get("name", ""), self._shorten_recent_path(path_val), opened_display, size_display),
            )
            record_map[iid] = rec

        def open_selected() -> None:
            selection = tree.selection()
            if not selection:
                return
            iid_selected = selection[0]
            rec = record_map.get(iid_selected)
            if not rec:
                return
            win.destroy()
            path_value = rec.get("path")
            if not isinstance(path_value, str):
                return
            success = self._load_log_file(path_value)
            if success:
                self.current_file = path_value

        def _on_double(_event: tk.Event) -> str:
            open_selected()
            return "break"

        tree.bind("<Double-1>", _on_double)
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill="x", pady=(8, 0))
        ttk.Button(btn_frame, text=self._("open_folder"), command=lambda: self._open_recent_location(tree, record_map)).pack(side="left")
        ttk.Button(btn_frame, text=self._("choose_log"), command=open_selected).pack(side="right", padx=(0, 6))
        ttk.Button(btn_frame, text=self._("close"), command=win.destroy).pack(side="right")
        self._center_child(win, width=720, height=360)

    def _add_recent_log(self, file_path: str) -> None:
        self._ensure_recent_loaded()
        if not file_path:
            return
        info = Path(file_path)
        try:
            size = info.stat().st_size if info.exists() else None
        except Exception:
            size = None
        record = {
            "path": file_path,
            "name": info.name or file_path,
            "opened_at": datetime.now(),
            "size": size,
        }
        self._recent_logs = [r for r in self._recent_logs if r.get("path") != file_path]
        self._recent_logs.insert(0, record)
        if len(self._recent_logs) > 20:
            self._recent_logs = self._recent_logs[:20]
        try:
            import json

            recent_path = ROOT_DIR / ".cache" / "recent_logs.json"
            recent_path.parent.mkdir(parents=True, exist_ok=True)
            serializable: List[dict[str, object]] = []
            for r in self._recent_logs:
                opened = r.get("opened_at")
                if isinstance(opened, datetime):
                    opened_str = opened.strftime("%Y-%m-%d %H:%M:%S")
                else:
                    opened_str = str(opened or "")
                serializable.append({
                    "path": r.get("path"),
                    "name": r.get("name"),
                    "opened_at": opened_str,
                    "size": r.get("size"),
                })
            with (recent_path.open("w", encoding="utf-8")) as fh:
                json.dump(serializable, fh, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _load_log_file(self, file_path: str, *, update_recent: bool = True) -> bool:
        if not file_path:
            return False
        try:
            sql_full = parse_sql(file_path)
            error_full = parse_errors(file_path)
        except Exception:
            import traceback

            logger.exception("Failed to load log file %s", file_path)
            messagebox.showerror(
                i18n.translate(APP_TITLE_KEY),
                self._("msg.read_error", error=traceback.format_exc()),
                parent=self.root,
            )
            return False
        self.sql_entries_full = sql_full
        self.error_entries_full = error_full
        self._apply_entry_limits()
        if update_recent:
            self._add_recent_log(file_path)
        screens = sorted({entry.screen_id for entry in self.sql_entries_full + self.error_entries_full if entry.screen_id})
        self.combo_screen.configure(values=["ALL"] + screens)
        if self.screen_var.get() not in self.combo_screen["values"]:
            self.screen_var.set("ALL")
        self.current_file = file_path
        self._refresh_file_label()
        self.refresh_table()
        return True

    def _format_size(self, size_bytes: Optional[object]) -> str:
        try:
            size = int(size_bytes) if size_bytes is not None else None
        except Exception:
            size = None
        if size is None or size < 0:
            return ""
        units = ["B", "KB", "MB", "GB", "TB"]
        value = float(size)
        unit = 0
        while value >= 1024 and unit < len(units) - 1:
            value /= 1024
            unit += 1
        if unit == 0:
            return f"{int(value)} {units[unit]}"
        return f"{value:.1f} {units[unit]}"

    def _shorten_recent_path(self, path: str) -> str:
        if not path:
            return ""
        marker = "master-unfiticated"
        idx = path.find(marker)
        if idx != -1:
            return path[idx:]
        if len(path) <= 80:
            return path
        return "..." + path[-77:]

    def _open_recent_location(self, tree: ttk.Treeview, record_map: dict[str, dict[str, object]]) -> None:
        selection = tree.selection()
        if not selection:
            return
        rec = record_map.get(selection[0])
        if not rec:
            return
        path_val = rec.get("path")
        if not isinstance(path_val, str) or not path_val:
            return
        folder = os.path.dirname(path_val)
        if not folder or not os.path.isdir(folder):
            messagebox.showerror(i18n.translate(APP_TITLE_KEY), self._("open_folder_error", error=self._("no_file")), parent=self.root)
            return
        try:
            if sys.platform.startswith("win"):
                os.startfile(folder)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", folder])
            else:
                subprocess.Popen(["xdg-open", folder])
        except Exception as exc:
            logger.exception("Failed to open folder %s", folder)
            messagebox.showerror(i18n.translate(APP_TITLE_KEY), self._("open_folder_error", error=str(exc)), parent=self.root)

    def _ensure_recent_loaded(self) -> None:
        if getattr(self, "_recent_loaded", False):
            return
        recent_path = ROOT_DIR / ".cache" / "recent_logs.json"
        try:
            import json
            data = json.loads(recent_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            self._recent_logs = []
            self._recent_loaded = True
            return
        except Exception:
            self._recent_logs = []
            self._recent_loaded = True
            return
        parsed: List[dict[str, object]] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            path_val = item.get("path")
            if not path_val:
                continue
            opened_raw = item.get("opened_at")
            try:
                opened_dt = datetime.strptime(opened_raw, "%Y-%m-%d %H:%M:%S") if opened_raw else datetime.now()
            except Exception:
                opened_dt = datetime.now()
            size_val = item.get("size")
            if size_val is not None:
                try:
                    size_val = int(size_val)
                except Exception:
                    size_val = None
            parsed.append({
                "path": path_val,
                "name": item.get("name") or Path(path_val).name or path_val,
                "opened_at": opened_dt,
                "size": size_val,
            })
        self._recent_logs = parsed
        self._recent_loaded = True

    def _apply_entry_limits(self) -> None:
        if len(self.sql_entries_full) > MAX_DISPLAY_ROWS:
            self.sql_entries = self.sql_entries_full[:MAX_DISPLAY_ROWS]
            self._log_truncated_sql = True
        else:
            self.sql_entries = list(self.sql_entries_full)
            self._log_truncated_sql = False
        if len(self.error_entries_full) > MAX_DISPLAY_ROWS:
            self.error_entries = self.error_entries_full[:MAX_DISPLAY_ROWS]
            self._log_truncated_error = True
        else:
            self.error_entries = list(self.error_entries_full)
            self._log_truncated_error = False

    def update_filters(self) -> None:
        """Điều chỉnh bố cục và tiêu đề khi đổi loại log (SQL/ERROR)."""
        if not hasattr(self, "tree"):
            return
        is_sql = self.log_type_var.get() == "SQL"
        if is_sql:
            self.sql_command_row.grid()
            self.param_row.grid()
            self.important_row.grid()
        else:
            self.sql_command_row.grid_remove()
            self.param_row.grid_remove()
            self.important_row.grid_remove()
            if self.show_params_var.get():
                self.show_params_var.set(False)
                self._update_param_check_text()
            if self.important_only_var.get():
                self.important_only_var.set(False)
        self._configure_tree_columns()
        self._update_action_buttons()
        self._apply_language()
        self.refresh_table()

    def refresh_table(self) -> None:
        """Làm mới bảng kết quả theo bộ lọc hiện tại."""
        if not hasattr(self, "tree"):
            return
        self._configure_tree_columns()
        self._cancel_pending_population()
        for row in self.tree.get_children():
            self.tree.delete(row)
        selected_screen = self.screen_var.get()
        search_term = self.search_var.get().strip().lower()
        is_sql = self.log_type_var.get() == "SQL"
        columns = self._get_active_columns()
        self.row_to_entry.clear()
        self._item_to_key = {}
        rows_to_render: List[Tuple[Tuple[Any, ...], Tuple[str, ...], object, Optional[str]]] = []

        if is_sql:
            command_filter = self.sql_command_var.get()
            self._entry_by_key = {}
            self._total_count = len(self.sql_entries)
            for entry in self.sql_entries:
                if selected_screen != "ALL" and entry.screen_id != selected_screen:
                    continue
                if command_filter != "ALL" and entry.sql_type != command_filter:
                    continue
                ts = entry.timestamp
                if self.time_format_var.get() == "time" and ts:
                    try:
                        ts_display = ts.split()[1]
                    except Exception:
                        ts_display = ts
                else:
                    ts_display = ts
                param_str_display = "***" if not self.show_params_var.get() else ", ".join(entry.params)
                row_lookup = [entry.screen_id or "", ts_display, entry.sql_type, entry.function, param_str_display, entry.sql]
                include_row = not search_term
                tag_match = False
                if search_term:
                    for v in row_lookup:
                        if v and search_term in str(v).lower():
                            include_row = True
                            tag_match = True
                            break
                if not include_row:
                    continue
                key = self._build_entry_key(entry)
                self._entry_by_key[key] = entry
                mark_value = self._mark_symbol if key in self._marked_keys else self._empty_mark
                row_map = {
                    "mark": mark_value,
                    "screen": entry.screen_id or "",
                    "timestamp": ts_display,
                    "command": entry.sql_type,
                    "function": entry.function,
                    "params": param_str_display,
                    "sql": entry.sql,
                }
                row_values = tuple(row_map.get(col, "") for col in columns)
                row_tag = "even_row" if len(rows_to_render) % 2 == 0 else "odd_row"
                tags: List[str] = [row_tag]
                if tag_match:
                    tags.append("match")
                rows_to_render.append((row_values, tuple(tags), entry, key))
            self._marked_keys.intersection_update(set(self._entry_by_key.keys()))
        else:
            self._total_count = len(self.error_entries)
            self._marked_keys.clear()
            self._entry_by_key = {}
            for entry in self.error_entries:
                if selected_screen != "ALL" and entry.screen_id != selected_screen:
                    continue
                ts = entry.timestamp
                if self.time_format_var.get() == "time" and ts:
                    try:
                        ts_display = ts.split()[1]
                    except Exception:
                        ts_display = ts
                else:
                    ts_display = ts
                row_values_all = [ts_display, entry.screen_id or "", entry.summary, entry.details]
                include_row = not search_term
                tag_match = False
                if search_term:
                    for v in row_values_all:
                        if v and search_term in str(v).lower():
                            include_row = True
                            tag_match = True
                            break
                if not include_row:
                    continue
                display_values = (row_values_all[0], row_values_all[1], row_values_all[2])
                row_tag = "even_row" if len(rows_to_render) % 2 == 0 else "odd_row"
                tags = [row_tag]
                if tag_match:
                    tags.append("match")
                rows_to_render.append((display_values, tuple(tags), entry, None))

        self._visible_count = len(rows_to_render)
        self._update_empty_state(bool(rows_to_render))
        self._update_summary_label()
        self._populate_tree_async(rows_to_render)
        self._update_action_buttons()

    def _cancel_pending_population(self) -> None:
        """Hủy job insert treeview còn dang dở khi refresh."""
        if self._populate_job:
            try:
                self.root.after_cancel(self._populate_job)
            except Exception:
                pass
            self._populate_job = None
        self._populate_rows = []
        self._populate_index = 0

    def _populate_tree_async(self, rows: Sequence[Tuple[Tuple[Any, ...], Tuple[str, ...], object, Optional[str]]]) -> None:
        """Chèn dữ liệu vào tree từng đợt nhỏ để UI không bị đứng."""
        self._populate_rows = list(rows)
        self._populate_index = 0
        if not self._populate_rows:
            return
        batch = 400 if len(self._populate_rows) > 1200 else 250

        def insert_chunk() -> None:
            if not self.root.winfo_exists():
                return
            start = self._populate_index
            end = min(start + batch, len(self._populate_rows))
            for row_values, tags, entry, key in self._populate_rows[start:end]:
                item_id = self.tree.insert("", "end", values=row_values, tags=tags)
                self.row_to_entry[item_id] = entry
                if key is not None:
                    self._item_to_key[item_id] = key
            self._populate_index = end
            if end < len(self._populate_rows):
                self._populate_job = self.root.after(10, insert_chunk)
            else:
                self._populate_job = None
                self._populate_rows = []

        insert_chunk()

    def clear_search(self) -> None:
        """Xóa từ khóa tìm kiếm và làm mới kết quả."""
        if self.search_var.get():
            self.search_var.set("")
            self.refresh_table()
        self.entry_search.focus_set()

    def reset_filters(self) -> None:
        """Đặt lại toàn bộ bộ lọc về trạng thái mặc định."""
        self.log_type_var.set("SQL")
        self.sql_command_var.set("ALL")
        self.screen_var.set("ALL")
        self.search_var.set("")
        self.time_format_var.set("full")
        if self.show_params_var.get():
            self.show_params_var.set(False)
        self._update_param_check_text()
        if self.important_only_var.get():
            self.important_only_var.set(False)
        self.update_filters()
        self.entry_search.focus_set()

    def focus_search_entry(self, _event=None) -> str:
        """Đưa focus vào ô tìm kiếm khi người dùng nhấn Ctrl+F."""
        try:
            self.entry_search.focus_set()
            self.entry_search.select_range(0, tk.END)
        except Exception:
            pass
        return "break"

    def open_current_folder(self) -> None:
        """Mở thư mục chứa file log đang xem."""
        path = getattr(self, "current_file", "") or ""
        if not path:
            messagebox.showinfo(i18n.translate(APP_TITLE_KEY), self._("no_file"), parent=self.root)
            return
        folder = os.path.dirname(path)
        if not folder or not os.path.isdir(folder):
            messagebox.showerror(i18n.translate(APP_TITLE_KEY), self._("open_folder_error", error=self._("no_file")), parent=self.root)
            return
        try:
            if sys.platform.startswith("win"):
                os.startfile(folder)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", folder])
            else:
                subprocess.Popen(["xdg-open", folder])
        except Exception as exc:
            logger.exception("Failed to open log folder %s", folder)
            messagebox.showerror(i18n.translate(APP_TITLE_KEY), self._("open_folder_error", error=str(exc)), parent=self.root)

    def _format_path(self, path: str) -> str:
        if not path:
            return self._("no_file")
        normalized = os.path.normpath(path)
        if len(normalized) <= 90:
            return normalized
        return "..." + normalized[-87:]

    def _refresh_file_label(self) -> None:
        display = self._format_path(getattr(self, "current_file", "") or "")
        self.file_path_var.set(display)

    def _update_empty_state(self, has_rows: bool) -> None:
        if has_rows:
            self.empty_label.place_forget()
        else:
            self.empty_label.configure(text=self._("msg.no_results"))
            self.empty_label.place(relx=0.5, rely=0.5, anchor="center")
            self.empty_label.lift()

    def _update_summary_label(self) -> None:
        if not getattr(self, "current_file", None):
            self.summary_var.set("")
            return
        total = self._total_count
        visible = self._visible_count
        if total <= 0:
            self.summary_var.set(self._("msg.no_results"))
            return
        summary = self._("summary_status", visible=visible, total=total)
        if visible == 0 and total > 0:
            summary = f"{summary} | {self._('msg.no_results')}"
        self.summary_var.set(summary)

    def on_toggle_params(self) -> None:
        """Đổi trạng thái hiển thị tham số và làm mới bảng."""
        self._update_param_check_text()
        self.refresh_table()

    def on_toggle_important(self) -> None:
        """Bật/tắt chế độ chỉ hiển thị cột quan trọng."""
        if self.log_type_var.get() != "SQL":
            self.important_only_var.set(False)
            return
        self._configure_tree_columns()
        self.refresh_table()

    def _update_param_check_text(self) -> None:
        if not hasattr(self, "chk_params"):
            return
        text = self._("param_show") if self.show_params_var.get() else self._("param_hide")
        try:
            self.chk_params.configure(text=text)
        except tk.TclError:
            pass

    def _update_action_buttons(self) -> None:
        if not hasattr(self, "btn_save_log"):
            return
        is_sql = self.log_type_var.get() == "SQL"
        if not is_sql:
            self.btn_save_log.state(["disabled"])
            self.btn_saved_logs.state(["disabled"])
            return
        if self._marked_keys:
            self.btn_save_log.state(["!disabled"])
        else:
            self.btn_save_log.state(["disabled"])
        if self._saved_logs:
            self.btn_saved_logs.state(["!disabled"])
        else:
            self.btn_saved_logs.state(["disabled"])

    def _build_entry_key(self, entry: SqlEntry) -> str:
        params_key = "|".join(entry.params)
        return "||".join([
            entry.timestamp or "",
            entry.screen_id or "",
            entry.sql_type,
            entry.function,
            entry.sql,
            params_key,
        ])

    def _on_tree_click(self, event: tk.Event):
        if self.log_type_var.get() != "SQL":
            return
        region = self.tree.identify("region", event.x, event.y)
        if region != "cell":
            return
        column_id = self.tree.identify_column(event.x)
        try:
            column_index = int(column_id[1:]) - 1
        except (ValueError, TypeError):
            return
        columns = self.tree["columns"]
        if column_index < 0 or column_index >= len(columns) or columns[column_index] != "mark":
            return
        item_id = self.tree.identify_row(event.y)
        if not item_id:
            return
        self.tree.selection_set(item_id)
        self.tree.focus(item_id)
        self._toggle_mark(item_id)
        return "break"

    def _toggle_mark(self, item_id: str) -> None:
        key = self._item_to_key.get(item_id)
        if not key:
            return
        if key in self._marked_keys:
            self._marked_keys.remove(key)
            symbol = ""
        else:
            self._marked_keys.add(key)
            symbol = self._mark_symbol
        if "mark" in self.tree["columns"]:
            self.tree.set(item_id, "mark", symbol if symbol else self._empty_mark)
        self._update_action_buttons()

    def save_selected_logs(self) -> None:
        if self.log_type_var.get() != "SQL":
            return
        selected_keys = [key for key in self._marked_keys if key in self._entry_by_key]
        if not selected_keys:
            messagebox.showinfo(i18n.translate(APP_TITLE_KEY), self._("msg_save_none"), parent=self.root)
            return
        for key in selected_keys:
            entry = self._entry_by_key.get(key)
            if not entry:
                continue
            self._saved_logs.append({"saved_at": datetime.now(), "entry": entry})
        self._marked_keys.difference_update(selected_keys)
        self.refresh_table()
        self._update_action_buttons()
        messagebox.showinfo(i18n.translate(APP_TITLE_KEY), self._("msg_save_success", count=len(selected_keys)), parent=self.root)

    def show_saved_logs(self) -> None:
        if not self._saved_logs:
            messagebox.showinfo(i18n.translate(APP_TITLE_KEY), self._("msg_no_saved_log"), parent=self.root)
            return
        win = tk.Toplevel(self.root)
        win.title(self._("saved_logs_title"))
        win.geometry("980x420")
        try:
            self._apply_icon(win)
        except Exception:
            pass
        frame = ttk.Frame(win, padding=10)
        frame.pack(fill="both", expand=True)
        columns = ("saved_at", "screen", "timestamp", "command", "function", "params", "sql")
        tree = ttk.Treeview(frame, columns=columns, show="headings")
        tree.heading("saved_at", text=self._("saved_at"))
        tree.heading("screen", text=self._("screen_id"))
        tree.heading("timestamp", text=self._("time"))
        tree.heading("command", text=self._("command"))
        tree.heading("function", text=self._("function"))
        tree.heading("params", text=self._("params"))
        tree.heading("sql", text=self._("sql_filled"))
        tree.column("saved_at", width=160, stretch=False)
        tree.column("screen", width=108, stretch=False)
        tree.column("timestamp", width=148, stretch=False)
        tree.column("command", width=96, stretch=False)
        tree.column("function", width=150, stretch=False)
        tree.column("params", width=220, stretch=False)
        tree.column("sql", width=420, stretch=True)
        tree.pack(fill="both", expand=True)
        scry = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        scry.pack(side="right", fill="y")
        scrx = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
        scrx.pack(side="bottom", fill="x")
        tree.configure(yscrollcommand=scry.set, xscrollcommand=scrx.set)
        saved_row_map: dict[str, SqlEntry] = {}
        for record in self._saved_logs:
            entry = record["entry"]
            saved_at = record["saved_at"].strftime("%Y-%m-%d %H:%M:%S")
            params_text = ", ".join(entry.params)
            iid = tree.insert(
                "",
                "end",
                values=(saved_at, entry.screen_id or "", entry.timestamp, entry.sql_type, entry.function, params_text, entry.sql),
            )
            saved_row_map[iid] = entry

        def on_saved_double_click(event: tk.Event) -> None:
            if tree.identify("region", event.x, event.y) != "cell":
                return
            item = tree.identify_row(event.y)
            if not item:
                return
            tree.selection_set(item)
            entry_selected = saved_row_map.get(item)
            if not entry_selected:
                return
            column_id = tree.identify_column(event.x)
            try:
                col_idx = int(column_id[1:]) - 1
            except (ValueError, TypeError):
                col_idx = -1
            if col_idx < 0:
                return
            cols = tree["columns"]
            if col_idx >= len(cols):
                return
            col_name = cols[col_idx]
            if col_name == "params":
                self._show_params_popup(entry_selected)
            else:
                self._show_sql_popup(entry_selected)

        tree.bind("<Double-1>", on_saved_double_click, add="+")
        ttk.Button(frame, text=self._("close"), command=win.destroy).pack(pady=(8, 0))


    def on_double_click(self, event: tk.Event) -> None:
        """Xử lý thao tác double-click để xem chi tiết."""
        if self.tree.identify("region", event.x, event.y) != "cell":
            return
        item_id = self.tree.identify_row(event.y)
        if not item_id:
            return
        self.tree.selection_set(item_id)
        entry = self.row_to_entry.get(item_id)
        if entry is None:
            return
        column_id = self.tree.identify_column(event.x)
        column_name: Optional[str] = None
        columns = self.tree["columns"]
        try:
            col_index = int(column_id[1:]) - 1
        except (ValueError, TypeError):
            col_index = -1
        if 0 <= col_index < len(columns):
            column_name = columns[col_index]

        if isinstance(entry, SqlEntry):
            if column_name == "mark":
                return
            if column_name == "params":
                self._show_params_popup(entry)
            else:
                self._show_sql_popup(entry)
        elif isinstance(entry, ErrorEntry):
            self._show_error_popup(entry)

    def _show_params_popup(self, entry: SqlEntry) -> None:
        """Hiển thị popup tham số với dạng bảng."""
        mapping = self.map_params_to_fields(entry.raw_sql, entry.params)
        _ = self._
        popup = tk.Toplevel(self.root)
        popup.title(_("params"))
        popup.geometry("520x320")
        try:
            self._apply_icon(popup)
        except Exception:
            pass
        table_frame = tk.Frame(popup)
        table_frame.pack(fill="both", expand=True, padx=5, pady=5)
        scry = tk.Scrollbar(table_frame, orient="vertical")
        scry.pack(side="right", fill="y")
        scrx = tk.Scrollbar(table_frame, orient="horizontal")
        scrx.pack(side="bottom", fill="x")
        param_border = tk.Frame(table_frame, bd=1, relief="solid")
        param_border.pack(fill="both", expand=True)
        param_tree = ttk.Treeview(
            param_border,
            columns=("field", "value"),
            show="headings",
            yscrollcommand=scry.set,
            xscrollcommand=scrx.set,
        )
        param_tree.heading("field", text=_("field"))
        param_tree.heading("value", text=_("value"))
        if mapping:
            for field, val in mapping:
                param_tree.insert("", "end", values=(field or "", val))
        else:
            for val in entry.params:
                param_tree.insert("", "end", values=("", val))
        char_w = 7
        field_len = max(len(str(f or "")) for f, _ in mapping) if mapping else 0
        value_len = max(len(str(v)) for _, v in mapping) if mapping else 0
        param_tree.column("field", width=max(80, field_len * char_w), stretch=False)
        param_tree.column("value", width=max(80, value_len * char_w), stretch=True)
        param_tree.pack(fill="both", expand=True)
        scry.config(command=param_tree.yview)
        scrx.config(command=param_tree.xview)
        btn_frame = tk.Frame(popup)
        btn_frame.pack(fill="x", pady=5)

        def copy_params() -> None:
            lines = []
            source = mapping if mapping else [(None, val) for val in entry.params]
            for field, val in source:
                lines.append(f"{field}: {val}" if field else str(val))
            self.root.clipboard_clear()
            self.root.clipboard_append("\n".join(lines))
            messagebox.showinfo(_("copied"), _("details_copied"))

        tk.Button(btn_frame, text=_("copy"), command=copy_params).pack(side="right", padx=5)
        tk.Button(btn_frame, text=_("close"), command=popup.destroy).pack(side="right", padx=5)

    def _show_sql_popup(self, entry: SqlEntry) -> None:
        """Hiển thị popup SQL với khả năng chuyển đổi qua tham số."""
        sql = entry.sql
        if not sql:
            return
        formatted_sql = format_sql(sql)
        mapping = self.map_params_to_fields(entry.raw_sql, entry.params)
        _ = self._
        popup = tk.Toplevel(self.root)
        popup.title(_("sql_detail_title"))
        popup.geometry("820x460")
        try:
            self._apply_icon(popup)
        except Exception:
            pass

        container = tk.Frame(popup)
        container.pack(fill="both", expand=True, padx=5, pady=5)

        sql_frame = tk.Frame(container)
        scroll_y_sql = tk.Scrollbar(sql_frame, orient="vertical")
        scroll_y_sql.pack(side="right", fill="y")
        text_sql = tk.Text(sql_frame, wrap="none", yscrollcommand=scroll_y_sql.set)
        text_sql.insert("1.0", formatted_sql)
        text_sql.configure(state="disabled")
        text_sql.pack(fill="both", expand=True)
        scroll_y_sql.config(command=text_sql.yview)

        param_frame = tk.Frame(container)
        scry = tk.Scrollbar(param_frame, orient="vertical")
        scry.pack(side="right", fill="y")
        scrx = tk.Scrollbar(param_frame, orient="horizontal")
        scrx.pack(side="bottom", fill="x")
        param_border = tk.Frame(param_frame, bd=1, relief="solid")
        param_border.pack(fill="both", expand=True)
        param_tree = ttk.Treeview(
            param_border,
            columns=("field", "value"),
            show="headings",
            yscrollcommand=scry.set,
            xscrollcommand=scrx.set,
        )
        param_tree.heading("field", text=_("field"))
        param_tree.heading("value", text=_("value"))
        if mapping:
            for field, val in mapping:
                param_tree.insert("", "end", values=(field or "", val))
        else:
            for val in entry.params:
                param_tree.insert("", "end", values=("", val))
        char_w = 7
        field_len = max(len(str(f or "")) for f, _ in mapping) if mapping else 0
        value_len = max(len(str(v)) for _, v in mapping) if mapping else 0
        param_tree.column("field", width=max(80, field_len * char_w), stretch=False)
        param_tree.column("value", width=max(80, value_len * char_w), stretch=True)
        param_tree.pack(fill="both", expand=True)
        scry.config(command=param_tree.yview)
        scrx.config(command=param_tree.xview)

        sql_frame.pack(fill="both", expand=True)

        btn_frame = tk.Frame(popup)
        btn_frame.pack(fill="x", pady=5)
        showing_sql = {"value": True}

        def toggle_view() -> None:
            if showing_sql["value"]:
                sql_frame.pack_forget()
                param_frame.pack(fill="both", expand=True)
            else:
                param_frame.pack_forget()
                sql_frame.pack(fill="both", expand=True)
            showing_sql["value"] = not showing_sql["value"]

        def copy_current() -> None:
            self.root.clipboard_clear()
            if showing_sql["value"]:
                self.root.clipboard_append(formatted_sql)
                messagebox.showinfo(_("copied"), _("sql_copied"))
            else:
                lines = []
                source = mapping if mapping else [(None, val) for val in entry.params]
                for field, val in source:
                    lines.append(f"{field}: {val}" if field else str(val))
                self.root.clipboard_append("\n".join(lines))
                messagebox.showinfo(_("copied"), _("details_copied"))

        tk.Button(btn_frame, text=self._("toggle_param_sql"), command=toggle_view).pack(side="left", padx=5)
        tk.Button(btn_frame, text=_("copy"), command=copy_current).pack(side="right", padx=5)
        tk.Button(btn_frame, text=_("close"), command=popup.destroy).pack(side="right", padx=5)

    def _show_error_popup(self, entry: ErrorEntry) -> None:
        """Hiển thị popup chi tiết lỗi."""
        details = entry.details
        if not details:
            return
        _ = self._
        popup = tk.Toplevel(self.root)
        popup.title(_("error_detail_title"))
        popup.geometry("800x400")
        self._apply_icon(popup)
        text_frame = tk.Frame(popup)
        text_frame.pack(fill="both", expand=True, padx=5, pady=5)
        scroll_y = tk.Scrollbar(text_frame, orient="vertical")
        scroll_y.pack(side="right", fill="y")
        text = tk.Text(text_frame, wrap="none", yscrollcommand=scroll_y.set)
        text.insert("1.0", details)
        text.configure(state="disabled")
        text.pack(fill="both", expand=True)
        scroll_y.config(command=text.yview)
        btn_frame = tk.Frame(popup)
        btn_frame.pack(fill="x", pady=5)

        def copy_details() -> None:
            self.root.clipboard_clear()
            self.root.clipboard_append(details)
            messagebox.showinfo(_("copied"), _("details_copied"))

        tk.Button(btn_frame, text=_("copy"), command=copy_details).pack(side="right", padx=5)
        tk.Button(btn_frame, text=_("close"), command=popup.destroy).pack(side="right", padx=5)

    def map_params_to_fields(self, raw_sql: str, params: List[str]) -> List[Tuple[Optional[str], str]]:
        """Ghép giá trị tham số về cột/điều kiện tương ứng trong SQL gốc."""
        # Insert: map param to columns
        m = re.search(r"insert\s+into\s+\S+\s*\(([^)]+)\)", raw_sql, re.IGNORECASE)
        if m:
            cols = [c.strip() for c in m.group(1).split(",")]
            mapping = []
            for i, val in enumerate(params):
                col = cols[i] if i < len(cols) else None
                mapping.append((col, val))
            return mapping
        pattern = re.compile(
            r"(\b\w+\b)\s*(?:=|<>|!=|>=|<=|>|<|IN\s*\(|LIKE)\s*\?",
            re.IGNORECASE,
        )
        fields = [match.group(1) for match in pattern.finditer(raw_sql)]
        results: List[Tuple[Optional[str], str]] = []
        if len(fields) >= len(params):
            for i, val in enumerate(params):
                results.append((fields[i], val))
        else:
            positions = []
            start = 0
            while True:
                idx = raw_sql.find("?", start)
                if idx == -1:
                    break
                positions.append(idx)
                start = idx + 1
            field_pattern = re.compile(r"(\b\w+\b)\s*(?:=|IN\s*\()", re.IGNORECASE)
            for pos, val in zip(positions, params):
                substr = raw_sql[max(0, pos - 80):pos]
                m = None
                for match in field_pattern.finditer(substr):
                    m = match
                field_name = m.group(1) if m else None
                results.append((field_name, val))
        if len(results) < len(params):
            for val in params[len(results):]:
                results.append((None, val))
        return results

    def _apply_icon(self, window: tk.Misc) -> None:
        """Đặt biểu tượng cửa sổ nếu đường dẫn hợp lệ."""
        if not self.icon_path:
            return
        try:
            window.iconbitmap(self.icon_path)
        except Exception:
            pass

    def _cleanup_language_listener(self) -> None:
        """Bỏ đăng ký listener i18n khi cửa sổ đóng lại."""
        if getattr(self, "_lang_listener", None):
            i18n.remove_listener(self._lang_listener)
            self._lang_listener = None

    def _on_close(self) -> None:
        """Đóng cửa sổ log viewer và thu dọn tài nguyên."""
        self._cleanup_language_listener()
        self._cancel_pending_population()
        try:
            self.root.unbind_all("<Control-c>")
            self.root.unbind_all("<Control-f>")
        except Exception:
            pass
        if self.root.winfo_exists():
            self.root.destroy()

    def perform_search(self) -> None:
        """Kích hoạt tìm kiếm theo từ khóa hiện tại."""
        self.refresh_table()

    def copy_all_or_selected(self, event=None) -> None:
        """Copy các dòng được chọn (hoặc toàn bộ nếu không chọn) vào clipboard định dạng TSV."""
        tree = getattr(self, "tree", None)
        if tree is None:
            return "break" if event else None
        try:
            if not tree.winfo_exists():
                return "break" if event else None
        except tk.TclError:
            return "break" if event else None
        try:
            columns = tree["columns"]
        except tk.TclError:
            return "break" if event else None
        items = tree.selection()
        if not items:
            items = tree.get_children()
        header: List[str] = []
        for c in columns:
            try:
                header.append(tree.heading(c)["text"])
            except tk.TclError:
                header.append("")
        lines = ["\t".join(header)]
        for it in items:
            try:
                vals = tree.item(it, "values")
            except tk.TclError:
                continue
            safe_vals = [str(v) if v is not None else "" for v in vals]
            lines.append("\t".join(safe_vals))
        data = "\n".join(lines)
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(data)
        except Exception:
            pass  # Clipboard may fail in some environments
        return "break" if event else None

def open_log_viewer(parent: Optional[tk.Misc] = None, icon_path: Optional[str] = None):
    resolved_icon = icon_path
    if resolved_icon and not os.path.isfile(resolved_icon):
        resolved_icon = None
    if not resolved_icon and os.path.isfile(DEFAULT_ICON_PATH):
        resolved_icon = DEFAULT_ICON_PATH
    if parent is not None:
        window = tk.Toplevel(parent)
        window.geometry("1200x800")
        window.minsize(960, 640)
        window.transient(parent)
        app = LogViewerApp(window, resolved_icon)
        window.log_app = app
        window.focus_set()
        return window
    root = tk.Tk()
    root.geometry("1200x800")
    root.minsize(960, 640)
    app = LogViewerApp(root, resolved_icon)
    root.log_app = app
    root.mainloop()
    return root


def main() -> None:
    open_log_viewer()


if __name__ == "__main__":
    main()
