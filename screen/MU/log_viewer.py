# log_viewer.py
import re
import tkinter as tk
from dataclasses import dataclass
from tkinter import filedialog, ttk, messagebox
from typing import List, Optional, Sequence, Tuple

# Regular expressions for parsing
SCREEN_ID_RE = re.compile(r"MU[A-Z]{2}\d{4}")
DATE_PREFIX_RE = re.compile(r"^\d{4}-\d{2}-\d{2} ")
THREAD_RE = re.compile(r"--- \[([^\]]+)\]")
REQUEST_RE = re.compile(r"(?:GET|POST|PUT|DELETE)\s+/(MU[A-Z]{2}\d{4})")

# Mapping of thread to last seen screen ID
thread_screen_map: dict[str, str] = {}

@dataclass
class SqlEntry:
    """Represents a single SQL statement."""
    timestamp: str
    screen_id: Optional[str]
    sql_type: str
    function: str
    params: List[str]
    raw_sql: str
    sql: str

@dataclass
class ErrorEntry:
    """Represents a single error log entry with its stack trace."""
    timestamp: str
    screen_id: Optional[str]
    summary: str
    details: str

def _parse_param_line(line: str) -> List[Tuple[str, str]]:
    """Parse a single 'Parameters:' line into [(val, typ), ...]."""
    params: List[Tuple[str, str]] = []
    try:
        param_str = line.split("Parameters:", 1)[1].strip()
    except Exception:
        return params
    if not param_str:
        return params
    parts = [p.strip() for p in param_str.split(",") if p.strip()]
    for p in parts:
        m = re.match(r"(.*)\((.*)\)", p)
        if m:
            val = m.group(1)
            typ = m.group(2)
        else:
            val = p
            typ = "String"
        params.append((val, typ))
    return params

def parse_sql(file_path: str) -> List[SqlEntry]:
    """Parse a log file and return a list of SqlEntry objects."""
    entries: List[SqlEntry] = []
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
    except Exception as e:
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

            # Collect multiple Parameters lines around this Preparing within ±6 lines and same thread
            window_start = max(0, i - 6)
            window_end = min(total, i + 7)
            param_blocks: List[List[Tuple[str, str]]] = []
            for k in range(window_start, window_end):
                if k == i:
                    continue
                if "Parameters:" in lines[k]:
                    thr_k = THREAD_RE.search(lines[k])
                    if thread and thr_k and thr_k.group(1) != thread:
                        continue
                    parsed = _parse_param_line(lines[k])
                    if parsed:
                        param_blocks.append(parsed)

            # Fallback: at least try to grab the immediate next Parameters if none found
            if not param_blocks:
                for j in range(i + 1, min(i + 6, total)):
                    if "Parameters:" in lines[j]:
                        parsed = _parse_param_line(lines[j])
                        if parsed:
                            param_blocks.append(parsed)
                        break

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
        return entries

def parse_errors(file_path: str) -> List[ErrorEntry]:
    """Parse a log file to extract error entries."""
    errors: List[ErrorEntry] = []
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
    except Exception as e:
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
        return errors

def format_sql(sql: str) -> str:
    """Insert newlines before common SQL keywords to improve readability."""
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
    """Main application class encapsulating the Tkinter GUI and log parsing logic."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("MU Log Reader VIP Premium Supper Limited")
        self.sql_entries: List[SqlEntry] = []
        self.error_entries: List[ErrorEntry] = []

        # Language handling
        self.language_var = tk.StringVar(value="VI")
        self.translations = {
            "VI": {
                "choose_log": "Open Log",
                "log_type": "Loại log:",
                "sql": "SQL",
                "error": "ERROR",
                "command_type": "Loại lệnh:",
                "screen": "Màn hình:",
                "screen_id": "ID màn hình",
                "time": "Thời gian",
                "command": "Lệnh",
                "function": "Hàm",
                "params": "Parameter",
                "sql_filled": "SQL",
                "summary": "Tóm tắt",
                "details": "Chi tiết lỗi",
                "copy": "Copy",
                "close": "Đóng",
                "copied": "Đã copy",
                "sql_copied": "SQL đã được copy vào clipboard",
                "details_copied": "Chi tiết đã được copy vào clipboard",
                "sql_detail_title": "Chi tiết SQL",
                "error_detail_title": "Chi tiết lỗi",
                "error_summary": "Tóm tắt",
                "error_details": "Chi tiết",
                "field": "Trường",
                "value": "Giá trị",
                "keyword": "Từ khóa",
                "search_btn": "Tìm",
                "time_format_full": "yyyy-mm-dd hh:mm:ss",
                "time_format_time": "hh:mm:ss",
                "time_display": "Hiển thị thời gian",
                "param_display": "Parameter",
                "param_show": "Hiện",
                "param_hide": "Ẩn",
                "toggle_param_sql": "Chuyển Param/SQL",
            },
            "JA": {
                "choose_log": "ログ選択",
                "log_type": "ログ種別:",
                "sql": "SQL",
                "error": "エラー",
                "command_type": "コマンド種別:",
                "screen": "画面:",
                "screen_id": "画面ID",
                "time": "日時",
                "command": "コマンド",
                "function": "関数",
                "params": "パラメータ",
                "sql_filled": "SQL",
                "summary": "概要",
                "details": "詳細",
                "copy": "コピー",
                "close": "閉じる",
                "copied": "コピー済み",
                "sql_copied": "SQLがクリップボードにコピーされました",
                "details_copied": "詳細がクリップボードにコピーされました",
                "sql_detail_title": "SQL詳細",
                "error_detail_title": "エラー詳細",
                "error_summary": "概要",
                "error_details": "詳細",
                "field": "フィールド",
                "value": "値",
                "keyword": "キーワード",
                "search_btn": "検索",
                "time_format_full": "yyyy-mm-dd hh:mm:ss",
                "time_format_time": "hh:mm:ss",
                "time_display": "時間表示",
                "param_display": "パラメータ",
                "param_show": "表示",
                "param_hide": "非表示",
                "toggle_param_sql": "パラメータ/SQL切替",
            }
        }

        def _(key: str) -> str:
            lang = self.language_var.get()
            return self.translations.get(lang, {}).get(key, self.translations["VI"].get(key, key))
        self._ = _

        # ----- UI Setup -----
        search_frame = tk.Frame(root, bd=1, relief="groove")
        search_frame.pack(fill="x", padx=5, pady=5)

        row1 = tk.Frame(search_frame)
        row1.pack(fill="x", padx=5, pady=(5, 2))
        self.btn_choose = tk.Button(row1, text=self._("choose_log"), command=self.choose_file)
        self.btn_choose.pack(side="left", padx=(0, 5))
        self.lbl_log_type = tk.Label(row1, text=self._("log_type"))
        self.lbl_log_type.pack(side="left", padx=(10, 5))
        self.log_type_var = tk.StringVar(value="SQL")
        self.rb_sql = tk.Radiobutton(row1, text=self._("sql"), variable=self.log_type_var, value="SQL", command=self.update_filters)
        self.rb_sql.pack(side="left", padx=(0, 5))
        self.rb_error = tk.Radiobutton(row1, text=self._("error"), variable=self.log_type_var, value="ERROR", command=self.update_filters)
        self.rb_error.pack(side="left", padx=(0, 5))

        lang_frame = tk.Frame(row1)
        lang_frame.pack(side="right")
        lang_top = tk.Frame(lang_frame)
        lang_top.pack(side="top", pady=(0, 2))
        self.lbl_lang = tk.Label(lang_top, text="Lang:")
        self.lbl_lang.pack(side="left")
        self.combo_lang = ttk.Combobox(lang_top, textvariable=self.language_var, values=["VI", "JA"], state="readonly", width=4)
        self.combo_lang.bind("<<ComboboxSelected>>", lambda e: self.update_language())
        self.combo_lang.pack(side="left")

        row_screen = tk.Frame(search_frame)
        row_screen.pack(fill="x", padx=5, pady=(5, 2))
        self.lbl_screen = tk.Label(row_screen, text=self._("screen"), width=10, anchor="w")
        self.lbl_screen.pack(side="left", padx=(0, 5))
        self.screen_var = tk.StringVar(value="ALL")
        self.combo_screen = ttk.Combobox(row_screen, textvariable=self.screen_var, values=["ALL"], state="readonly", width=12)
        self.combo_screen.bind("<<ComboboxSelected>>", lambda e: self.refresh_table())
        self.combo_screen.pack(side="left", padx=(0, 5))
        self.btn_refresh = tk.Button(row_screen, text="⟳", width=3, command=self.refresh_file)
        self.btn_refresh.pack(side="right", padx=(5, 0))

        row_cmd = tk.Frame(search_frame)
        row_cmd.pack(fill="x", padx=5, pady=(2, 5))
        self.sql_command_var = tk.StringVar(value="ALL")
        self.sql_command_frame = tk.Frame(row_cmd)
        self.lbl_cmd = tk.Label(self.sql_command_frame, text=self._("command_type"), width=10, anchor="w")
        self.lbl_cmd.pack(side="left", padx=(0, 5))
        self.cmd_buttons = []
        for cmd in ["ALL", "SELECT", "INSERT", "UPDATE", "DELETE"]:
            btn = tk.Radiobutton(row_cmd, text=cmd, variable=self.sql_command_var, value=cmd, command=self.refresh_table)
            btn.pack(side="left", padx=(0, 5))
            self.cmd_buttons.append(btn)
        self.sql_command_frame.pack(side="left")

        # Row for keyword search
        row_search = tk.Frame(search_frame)
        row_search.pack(fill="x", padx=5, pady=(2, 5))
        self.lbl_keyword = tk.Label(row_search, text=self._("keyword"), width=10, anchor="w")
        self.lbl_keyword.pack(side="left", padx=(0, 5))
        self.search_var = tk.StringVar()
        self.entry_search = tk.Entry(row_search, textvariable=self.search_var, width=20)
        self.entry_search.pack(side="left", padx=(0, 5))
        self.btn_search = tk.Button(row_search, text=self._("search_btn"), command=self.perform_search)
        self.btn_search.pack(side="left", padx=(0, 15))
        self.time_format_var = tk.StringVar(value="full")
        self.lbl_time_display = tk.Label(row_search, text=self._("time_display"), anchor="w")
        self.lbl_time_display.pack(side="left", padx=(0, 5))
        self.rb_time_full = tk.Radiobutton(row_search, text=self._("time_format_full"), variable=self.time_format_var, value="full", command=self.refresh_table)
        self.rb_time_full.pack(side="left", padx=(0, 5))
        self.rb_time_time = tk.Radiobutton(row_search, text=self._("time_format_time"), variable=self.time_format_var, value="time", command=self.refresh_table)
        self.rb_time_time.pack(side="left", padx=(0, 5))

        # Row for parameter display toggle (Hiện/Ẩn)
        row_param = tk.Frame(search_frame)
        row_param.pack(fill="x", padx=5, pady=(2, 5))
        self.lbl_param_display = tk.Label(row_param, text=self._("param_display"), width=10, anchor="w")
        self.lbl_param_display.pack(side="left", padx=(0, 5))
        self.param_display_var = tk.StringVar(value="hide")  # default Ẩn
        self.rb_param_show = tk.Radiobutton(row_param, text=self._("param_show"), variable=self.param_display_var, value="show", command=self.refresh_table)
        self.rb_param_show.pack(side="left", padx=(0, 5))
        self.rb_param_hide = tk.Radiobutton(row_param, text=self._("param_hide"), variable=self.param_display_var, value="hide", command=self.refresh_table)
        self.rb_param_hide.pack(side="left", padx=(0, 5))

        # ----- Treeview Setup -----
        columns_sql = ("screen", "timestamp", "command", "function", "params", "sql")
        self.columns_sql = columns_sql
        tree_frame = tk.Frame(root)
        tree_frame.pack(fill="both", expand=True, padx=5, pady=5)
        scroll_y = tk.Scrollbar(tree_frame, orient="vertical")
        scroll_y.pack(side="right", fill="y")
        scroll_x = tk.Scrollbar(tree_frame, orient="horizontal")
        scroll_x.pack(side="bottom", fill="x")
        self.border_frame = tk.Frame(tree_frame, bd=1, relief="solid")
        self.border_frame.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(
            self.border_frame,
            columns=columns_sql,
            show="headings",
            yscrollcommand=scroll_y.set,
            xscrollcommand=scroll_x.set,
        )
        headings = [
            "ID màn hình",
            "Thời gian",
            "Lệnh",
            "Hàm",
            "Parameter",
            "SQL (đã ghép)"
        ]
        for col, heading in zip(columns_sql, headings):
            self.tree.heading(col, text=heading)
            if col == "sql":
                width = 500; stretch = True
            elif col == "params":
                width = 200; stretch = False
            elif col == "function":
                width = 150; stretch = False
            elif col == "command":
                width = 80; stretch = False
            elif col == "timestamp":
                width = 130; stretch = False
            else:
                width = 100; stretch = False
            self.tree.column(col, width=width, stretch=stretch)
        self.tree.pack(fill="both", expand=True)
        scroll_y.config(command=self.tree.yview)
        scroll_x.config(command=self.tree.xview)
        self.error_columns = ("timestamp", "screen", "summary", "details")
        self.tree.bind("<Double-1>", self.on_double_click)

        # Global copy: Ctrl+C copies selected rows, or all rows if none selected.
        self.root.bind_all("<Control-c>", self.copy_all_or_selected)
        self.tree.bind("<Control-c>", self.copy_all_or_selected)

        # Mapping rows to entries
        self.row_to_entry: dict[str, object] = {}

        # Row styling tags
        self.tree.tag_configure("odd_row", background="#f9f9f9")
        self.tree.tag_configure("even_row", background="#ffffff")
        # Tag for matched search results (yellow background)
        self.tree.tag_configure("match", background="#fff2a8")

        # Initial language update
        self.update_language()

    def update_language(self) -> None:
        """Update all UI text strings to the selected language."""
        _ = self._
        self.btn_choose.configure(text=_("choose_log"))
        self.lbl_log_type.configure(text=_("log_type"))
        self.rb_sql.configure(text=_("sql"))
        self.rb_error.configure(text=_("error"))
        self.lbl_lang.configure(text="言語:" if self.language_var.get() == "JA" else "Ngôn ngữ:")
        self.lbl_cmd.configure(text=_("command_type"))
        labels_map = {"ALL": "ALL", "SELECT": "SELECT", "INSERT": "INSERT", "UPDATE": "UPDATE", "DELETE": "DELETE"}
        for btn in self.cmd_buttons:
            val = btn.cget("value")
            btn.configure(text=labels_map.get(val, val))
        self.lbl_screen.configure(text=_("screen"))
        if self.log_type_var.get() == "SQL":
            self.tree.heading("screen", text=_("screen_id"))
            self.tree.heading("timestamp", text=_("time"))
            self.tree.heading("command", text=_("command"))
            self.tree.heading("function", text=_("function"))
            self.tree.heading("params", text=_("params"))
            self.tree.heading("sql", text=_("sql_filled"))
        else:
            self.tree.heading("timestamp", text=_("time"))
            self.tree.heading("screen", text=_("screen_id"))
            self.tree.heading("summary", text=_("summary"))
        self.lbl_keyword.configure(text=_("keyword"))
        self.btn_search.configure(text=_("search_btn"))
        self.lbl_time_display.configure(text=_("time_display"))
        self.rb_time_full.configure(text=_("time_format_full"))
        self.rb_time_time.configure(text=_("time_format_time"))
        # Update param display labels
        self.lbl_param_display.configure(text=_("param_display"))
        self.rb_param_show.configure(text=_("param_show"))
        self.rb_param_hide.configure(text=_("param_hide"))

    def refresh_file(self) -> None:
        """Reload the currently selected log file if one has been loaded."""
        file_path = getattr(self, "current_file", None)
        if not file_path:
            return
        try:
            self.sql_entries = parse_sql(file_path)
            self.error_entries = parse_errors(file_path)
        except Exception:
            import traceback
            messagebox.showerror("Lỗi", traceback.format_exc())
            return
        screens = sorted({entry.screen_id for entry in self.sql_entries + self.error_entries if entry.screen_id})
        self.combo_screen.configure(values=["ALL"] + screens)
        if self.screen_var.get() not in self.combo_screen["values"]:
            self.screen_var.set("ALL")
        self.refresh_table()

    def choose_file(self) -> None:
        """Prompt the user to select a log file and parse it."""
        file_path = filedialog.askopenfilename(title="Chọn file log", filetypes=[("Log files", "*.log"), ("All files", "*.*")])
        if not file_path:
            return
        try:
            self.sql_entries = parse_sql(file_path)
            self.error_entries = parse_errors(file_path)
        except Exception:
            import traceback
            messagebox.showerror("Lỗi", traceback.format_exc())
            return
        screens = sorted({entry.screen_id for entry in self.sql_entries + self.error_entries if entry.screen_id})
        self.combo_screen.configure(values=["ALL"] + screens)
        self.screen_var.set("ALL")
        self.current_file = file_path
        self.refresh_table()

    def update_filters(self) -> None:
        """Update the UI when switching between SQL and ERROR logs."""
        if self.log_type_var.get() == "SQL":
            self.sql_command_frame.pack(side="left")
            self.tree.configure(columns=("screen", "timestamp", "command", "function", "params", "sql"))
            self.tree.heading("screen", text="ID màn hình")
            self.tree.heading("timestamp", text="Thời gian")
            self.tree.heading("command", text="Lệnh")
            self.tree.heading("function", text="Hàm")
            self.tree.heading("params", text="Parameter")
            self.tree.heading("sql", text="SQL (đã ghép)")
            self.tree.column("screen", width=100, stretch=False)
            self.tree.column("timestamp", width=130, stretch=False)
            self.tree.column("command", width=80, stretch=False)
            self.tree.column("function", width=150, stretch=False)
            self.tree.column("params", width=200, stretch=False)
            self.tree.column("sql", width=500, stretch=True)
        else:
            self.sql_command_frame.pack_forget()
            self.tree.configure(columns=("timestamp", "screen", "summary"))
            self.tree.heading("timestamp", text="Thời gian")
            self.tree.heading("screen", text="ID màn hình")
            self.tree.heading("summary", text="Tóm tắt")
            self.tree.column("timestamp", width=130, stretch=False)
            self.tree.column("screen", width=100, stretch=False)
            self.tree.column("summary", width=600, stretch=True)
        self.update_language()
        self.refresh_table()

    def refresh_table(self) -> None:
        """Refresh the tree view based on current filters and log type."""
        for row in self.tree.get_children():
            self.tree.delete(row)
        selected_screen = self.screen_var.get()
        search_term = self.search_var.get().strip().lower()
        self.row_to_entry.clear()
        row_index = 0

        if self.log_type_var.get() == "SQL":
            command_filter = self.sql_command_var.get()
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
                # Decide whether to display parameters or ***
                if self.param_display_var.get() == "hide":
                    param_str_display = "***"
                else:
                    param_str_display = ", ".join(entry.params)
                row_values = [entry.screen_id or "", ts_display, entry.sql_type, entry.function, param_str_display, entry.sql]
                include_row = False if search_term else True
                tag_match = False
                if search_term:
                    for v in row_values:
                        if v and search_term in str(v).lower():
                            include_row = True
                            tag_match = True
                            break
                if not include_row:
                    continue
                row_tag = "even_row" if row_index % 2 == 0 else "odd_row"
                tags = [row_tag]
                if tag_match:
                    tags.append("match")
                item_id = self.tree.insert("", "end", values=tuple(row_values), tags=tuple(tags))
                self.row_to_entry[item_id] = entry
                row_index += 1
            max_lengths = {
                "screen": len(self._("screen_id")),
                "timestamp": len(self._("time")),
                "command": len(self._("command")),
                "function": len(self._("function")),
                "params": len(self._("params")),
            }
            for row_id in self.tree.get_children():
                vals = self.tree.item(row_id, "values")
                if not vals:
                    continue
                col_names = ["screen", "timestamp", "command", "function", "params"]
                for idx, col in enumerate(col_names):
                    if idx < len(vals):
                        length = len(str(vals[idx]))
                        if length > max_lengths[col]:
                            max_lengths[col] = length
            char_w = 7
            self.tree.column("screen", width=max(80, max_lengths["screen"] * char_w), stretch=False)
            self.tree.column("timestamp", width=max(100, max_lengths["timestamp"] * char_w), stretch=False)
            self.tree.column("command", width=max(70, max_lengths["command"] * char_w), stretch=False)
            self.tree.column("function", width=max(100, max_lengths["function"] * char_w), stretch=False)
            self.tree.column("params", width=200, stretch=False)
        else:
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
                row_values = [ts_display, entry.screen_id or "", entry.summary, entry.details]
                include_row = False if search_term else True
                tag_match = False
                if search_term:
                    for v in row_values:
                        if v and search_term in str(v).lower():
                            include_row = True
                            tag_match = True
                            break
                if not include_row:
                    continue
                display_values = [ts_display, entry.screen_id or "", entry.summary]
                row_tag = "even_row" if row_index % 2 == 0 else "odd_row"
                tags = [row_tag]
                if tag_match:
                    tags.append("match")
                item_id = self.tree.insert("", "end", values=tuple(display_values), tags=tuple(tags))
                self.row_to_entry[item_id] = entry
                row_index += 1
            max_lengths = {
                "timestamp": len(self._("time")),
                "screen": len(self._("screen_id")),
                "summary": len(self._("summary")),
            }
            for row_id in self.tree.get_children():
                vals = self.tree.item(row_id, "values")
                if not vals:
                    continue
                names = ["timestamp", "screen", "summary"]
                for idx, name in enumerate(names):
                    if idx < len(vals):
                        l = len(str(vals[idx]))
                        if l > max_lengths[name]:
                            max_lengths[name] = l
            char_w = 7
            self.tree.column("timestamp", width=max(100, max_lengths["timestamp"] * char_w), stretch=False)
            self.tree.column("screen", width=max(80, max_lengths["screen"] * char_w), stretch=False)
            self.tree.column("summary", width=max(200, max_lengths["summary"] * char_w), stretch=True)

    def on_double_click(self, event: tk.Event) -> None:
        """Handle double-click on a row."""
        selection = self.tree.selection()
        if not selection:
            return
        item_id = selection[0]
        column = self.tree.identify_column(event.x)
        entry = self.row_to_entry.get(item_id)
        if entry is None:
            return
        _ = self._

        if self.log_type_var.get() == "SQL":
            if column == "#5":
                # Existing parameter popup
                params = entry.params
                raw_sql = entry.raw_sql
                mapping = self.map_params_to_fields(raw_sql, params)
                popup = tk.Toplevel(self.root)
                popup.title(_("params"))
                popup.geometry("500x300")
                try:
                    popup.iconbitmap("logo.ico")
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
                for field, val in mapping:
                    param_tree.insert("", "end", values=(field or "", val))
                field_len = max(len(str(f or "")) for f, _ in mapping) if mapping else 0
                value_len = max(len(str(v)) for _, v in mapping) if mapping else 0
                char_w = 7
                param_tree.column("field", width=max(80, field_len * char_w), stretch=False)
                param_tree.column("value", width=max(80, value_len * char_w), stretch=True)
                param_tree.pack(fill="both", expand=True)
                scry.config(command=param_tree.yview)
                scrx.config(command=param_tree.xview)
                btn_frame = tk.Frame(popup)
                btn_frame.pack(fill="x", pady=5)
                def copy_params() -> None:
                    lines = []
                    for field, val in mapping:
                        lines.append(f"{field}: {val}" if field else str(val))
                    self.root.clipboard_clear()
                    self.root.clipboard_append("\n".join(lines))
                    messagebox.showinfo(_("copied"), _("details_copied"))
                tk.Button(btn_frame, text=_("copy"), command=copy_params).pack(side="right", padx=5)
                tk.Button(btn_frame, text=_("close"), command=popup.destroy).pack(side="right", padx=5)
            else:
                # SQL popup with toggle button to switch to field/value view
                sql = entry.sql
                if not sql:
                    return
                formatted_sql = format_sql(sql)
                raw_sql = entry.raw_sql
                params = entry.params
                mapping = self.map_params_to_fields(raw_sql, params)

                popup = tk.Toplevel(self.root)
                popup.title(_("sql_detail_title"))
                popup.geometry("800x450")
                try:
                    popup.iconbitmap("logo.ico")
                except Exception:
                    pass

                # Two frames: sql_frame and param_frame
                container = tk.Frame(popup)
                container.pack(fill="both", expand=True, padx=5, pady=5)

                # SQL view
                sql_frame = tk.Frame(container)
                scroll_y_sql = tk.Scrollbar(sql_frame, orient="vertical")
                scroll_y_sql.pack(side="right", fill="y")
                text_sql = tk.Text(sql_frame, wrap="none", yscrollcommand=scroll_y_sql.set)
                text_sql.insert("1.0", formatted_sql)
                text_sql.configure(state="disabled")
                text_sql.pack(fill="both", expand=True)
                scroll_y_sql.config(command=text_sql.yview)

                # Param view
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
                for field, val in mapping:
                    param_tree.insert("", "end", values=(field or "", val))
                char_w = 7
                field_len = max(len(str(f or "")) for f, _ in mapping) if mapping else 0
                value_len = max(len(str(v)) for _, v in mapping) if mapping else 0
                param_tree.column("field", width=max(80, field_len * char_w), stretch=False)
                param_tree.column("value", width=max(80, value_len * char_w), stretch=True)
                param_tree.pack(fill="both", expand=True)
                scry.config(command=param_tree.yview)
                scrx.config(command=param_tree.xview)

                # Start with SQL view
                sql_frame.pack(fill="both", expand=True)

                btn_frame = tk.Frame(popup)
                btn_frame.pack(fill="x", pady=5)

                # Toggle action
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
                        for field, val in mapping:
                            lines.append(f"{field}: {val}" if field else str(val))
                        self.root.clipboard_append("\n".join(lines))
                        messagebox.showinfo(_("copied"), _("details_copied"))

                tk.Button(btn_frame, text=self._("toggle_param_sql"), command=toggle_view).pack(side="left", padx=5)
                tk.Button(btn_frame, text=_("copy"), command=copy_current).pack(side="right", padx=5)
                tk.Button(btn_frame, text=_("close"), command=popup.destroy).pack(side="right", padx=5)
        else:
            details = entry.details
            if not details:
                return
            popup = tk.Toplevel(self.root)
            popup.title(_("error_detail_title"))
            popup.geometry("800x400")
            try:
                popup.iconbitmap("logo.ico")
            except Exception:
                pass
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
        """Map parameter values back to corresponding columns/conditions in raw SQL."""
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

    def perform_search(self) -> None:
        """Trigger a table refresh based on the current search term."""
        self.refresh_table()

    def copy_all_or_selected(self, event=None) -> None:
        """Copy selected rows to clipboard as TSV. If none selected, copy all rows."""
        columns = self.tree["columns"]
        items = self.tree.selection()
        if not items:
            items = self.tree.get_children()
        header = [self.tree.heading(c)["text"] for c in columns]
        lines = ["\t".join(header)]
        for it in items:
            vals = self.tree.item(it, "values")
            safe_vals = [str(v) if v is not None else "" for v in vals]
            lines.append("\t".join(safe_vals))
        data = "\n".join(lines)
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(data)
        except Exception:
            pass  # Clipboard may fail in some environments

def main() -> None:
    root = tk.Tk()
    root.geometry("1200x800")
    try:
        root.iconbitmap("logo.ico")
    except Exception:
        pass
    try:
        default_font = ("Segoe UI", 10)
        root.option_add("*Font", default_font)
    except Exception:
        pass
    style = ttk.Style()
    try:
        style.theme_use(style.theme_use())
    except Exception:
        pass
    # Remove internal grid lines for a clean look; header is not bold
    style.configure("Treeview", borderwidth=0, relief="flat", rowheight=25)
    style.configure("Treeview.Heading", borderwidth=0, relief="flat")
    app = LogViewerApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
