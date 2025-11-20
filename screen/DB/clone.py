"""
Màn hình Clone DB - sao chép dữ liệu giữa hai môi trường.
"""
from __future__ import annotations

import json
import os
import threading
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from tkinter.scrolledtext import ScrolledText
from typing import Dict, List, Optional, Tuple
import re

from screen.DB import db_utils
from screen.DB.widgets import LoadingPopup
from core import history, i18n

APP_TITLE_KEY = "common.app_title"
ACTION_TYPE = "clone_db"

APPDATA = os.environ.get("APPDATA") or os.path.expanduser("~")
PERSIST_DIR = os.path.join(APPDATA, "ToolVIP")
CONFIGS_DIR = os.path.join(PERSIST_DIR, "configs")
CLONE_ENV_PATH = os.path.join(CONFIGS_DIR, "clone_envs.json")
DB_LIST_PATH = os.path.join(CONFIGS_DIR, "db_list.json")
os.makedirs(CONFIGS_DIR, exist_ok=True)


def _t(key: str, **kwargs) -> str:
    return i18n.translate(key, **kwargs)


def _load_saved_envs() -> Dict[str, Dict[str, str]]:
    if not os.path.isfile(CLONE_ENV_PATH):
        return {}
    try:
        with open(CLONE_ENV_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return {}
    environments = {}
    for entry in data.get("environments", []):
        name = entry.get("name")
        if not name:
            continue
        environments[name] = {
            "name": name,
            "user": entry.get("user", ""),
            "password": entry.get("password", ""),
            "alias": entry.get("alias", ""),
            "host": entry.get("host", ""),
            "port": entry.get("port", ""),
            "use_host_port": bool(entry.get("use_host_port")),
        }
    return environments


def _save_envs(envs: Dict[str, Dict[str, str]]) -> None:
    payload = {
        "environments": [
            {
                "name": name,
                "user": data.get("user", ""),
                "password": data.get("password", ""),
                "alias": data.get("alias", ""),
                "host": data.get("host", ""),
                "port": data.get("port", ""),
                "use_host_port": bool(data.get("use_host_port")),
            }
            for name, data in sorted(envs.items())
        ]
    }
    with open(CLONE_ENV_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


def block_extract(block: str) -> Dict[str, str]:
    def pick(pattern):
        m = re.search(pattern, block, flags=re.IGNORECASE)
        return m.group(1).strip() if m else ""

    return {
        "host": pick(r"HOST\s*=\s*([^) \r\n]+)"),
        "port": pick(r"PORT\s*=\s*([0-9]+)"),
    }


class CloneDbWindow(tk.Toplevel):
    """Cửa sổ clone DB."""

    BATCH_SIZE = 500

    def __init__(
        self,
        parent: tk.Widget,
        default_source: Optional[Dict[str, str]] = None,
        default_target: Optional[Dict[str, str]] = None,
        conn_blocks: Optional[Dict[str, str]] = None,
    ):
        super().__init__(parent)
        self.parent = parent
        self.title(_t("clone.title"))
        self.geometry("900x800")
        self.minsize(900, 800)
        self._saved_envs = _load_saved_envs()
        self._lang_listener = self._on_language_changed
        i18n.add_listener(self._lang_listener)
        self._text_widgets: List[Tuple[tk.Widget, str]] = []
        self._defaults: Dict[str, Dict[str, str]] = {
            "source": default_source or {},
            "target": default_target or {},
        }
        self._conn_blocks = conn_blocks or {}
        self._db_list_items = _load_db_list_items()

        self._source_conn = None
        self._target_conn = None
        self._source_conn_key = ""
        self._target_conn_key = ""
        self._source_owner = ""
        self._target_owner = ""
        self._source_connected = False
        self._target_connected = False
        self._source_tables: List[str] = []
        self._filtered_tables: List[str] = []
        self._mapping_rows: Dict[str, Dict[str, str]] = {}
        self._export_thread: threading.Thread | None = None
        self._cancel_event = threading.Event()

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._apply_default_env("source")
        self._apply_default_env("target")

    # ------------------------------------------------------------------
    def _register_text(self, widget: tk.Widget, key: str):
        self._text_widgets.append((widget, key))
        widget.configure(text=_t(key))

    def _build_ui(self):
        self.main = ttk.Frame(self, padding=8)
        self.main.pack(fill="both", expand=True)
        self.main.columnconfigure(0, weight=1)
        self.main.rowconfigure(2, weight=1)

        env_frame = ttk.Frame(self.main)
        env_frame.grid(row=0, column=0, sticky="nsew")
        env_frame.columnconfigure(0, weight=1)
        env_frame.columnconfigure(1, weight=1)

        self.env_forms: Dict[str, Dict[str, tk.Variable]] = {}
        self._create_env_section(env_frame, "source", 0, "clone.section.source")
        self._create_env_section(env_frame, "target", 1, "clone.section.target")

        # Table selection
        selection = ttk.LabelFrame(self.main, padding=8)
        self._register_text(selection, "clone.section.tables")
        selection.grid(row=1, column=0, sticky="ew", pady=(4, 4))
        selection.columnconfigure(0, weight=1)
        selection.columnconfigure(1, weight=1)
        selection.rowconfigure(1, weight=0)

        self.var_table_search = tk.StringVar()
        lbl_search = ttk.Label(selection)
        self._register_text(lbl_search, "clone.label.table_search")
        lbl_search.grid(row=0, column=0, sticky="w")
        search_entry = ttk.Entry(selection, textvariable=self.var_table_search)
        search_entry.grid(row=0, column=0, sticky="ew")
        search_entry.bind("<KeyRelease>", lambda _e: self._filter_source_tables())

        self.lst_source_tables = tk.Listbox(selection, height=6, selectmode="extended")
        self.lst_source_tables.grid(row=1, column=0, sticky="nsew", pady=(4, 0))
        self.lst_source_tables.bind("<Double-Button-1>", lambda _e: self._add_selected_tables())
        src_scroll = ttk.Scrollbar(selection, orient="vertical", command=self.lst_source_tables.yview)
        src_scroll.grid(row=1, column=0, sticky="nse")
        self.lst_source_tables.configure(yscrollcommand=src_scroll.set)

        btn_add = ttk.Button(selection, command=self._add_selected_tables)
        self._register_text(btn_add, "clone.btn.add")
        btn_add.grid(row=2, column=0, sticky="w", pady=(6, 0))

        mapping_frame = ttk.Frame(selection)
        mapping_frame.grid(row=0, column=1, rowspan=3, sticky="ew", padx=(12, 0))
        mapping_frame.columnconfigure(0, weight=1)
        mapping_frame.rowconfigure(0, weight=0)

        self.tree_mappings = ttk.Treeview(mapping_frame, columns=("source", "target"), show="headings", height=6)
        self.tree_mappings.heading("source", text=_t("clone.column.source"))
        self.tree_mappings.heading("target", text=_t("clone.column.target"))
        self.tree_mappings.column("source", width=200, anchor="w")
        self.tree_mappings.column("target", width=200, anchor="w")
        self.tree_mappings.grid(row=0, column=0, columnspan=3, sticky="nsew")

        map_scroll = ttk.Scrollbar(mapping_frame, orient="vertical", command=self.tree_mappings.yview)
        map_scroll.grid(row=0, column=3, sticky="ns")
        self.tree_mappings.configure(yscrollcommand=map_scroll.set)

        btn_edit_target = ttk.Button(mapping_frame, command=self._edit_target_mapping)
        self._register_text(btn_edit_target, "clone.btn.edit_target")
        btn_edit_target.grid(row=1, column=0, sticky="w", pady=(6, 0))
        btn_remove = ttk.Button(mapping_frame, command=self._remove_selected_mapping)
        self._register_text(btn_remove, "clone.btn.remove")
        btn_remove.grid(row=1, column=1, sticky="w", pady=(6, 0))
        btn_clear = ttk.Button(mapping_frame, command=self._clear_mappings)
        self._register_text(btn_clear, "clone.btn.clear")
        btn_clear.grid(row=1, column=2, sticky="e", pady=(6, 0))

        # Export + log
        bottom = ttk.Frame(self.main)
        bottom.grid(row=2, column=0, sticky="nsew", pady=(4, 0))
        bottom.columnconfigure(0, weight=1)
        bottom.rowconfigure(1, weight=0)
        bottom.rowconfigure(2, weight=1)

        btn_row = ttk.Frame(bottom)
        btn_row.grid(row=0, column=0, sticky="ew")
        btn_row.columnconfigure(0, weight=1)
        self.var_truncate = tk.BooleanVar(value=True)
        chk_truncate = ttk.Checkbutton(btn_row, variable=self.var_truncate)
        self._register_text(chk_truncate, "clone.option.truncate")
        chk_truncate.grid(row=0, column=0, sticky="w")
        self.btn_export = ttk.Button(btn_row, command=self._start_export, state="disabled")
        self._register_text(self.btn_export, "clone.btn.export")
        self.btn_export.grid(row=0, column=1, sticky="e")

        progress_frame = ttk.Frame(bottom)
        progress_frame.grid(row=1, column=0, sticky="ew", pady=(8, 0), padx=12)
        progress_frame.columnconfigure(0, weight=1)
        progress_frame.columnconfigure(1, weight=0)
        self.progress = ttk.Progressbar(progress_frame, mode="determinate")
        self.progress.grid(row=0, column=0, sticky="ew")
        self.lbl_progress = ttk.Label(progress_frame, text="")
        self.lbl_progress.grid(row=0, column=1, padx=(12, 0), sticky="w")

        log_frame = ttk.LabelFrame(bottom, padding=6)
        self._register_text(log_frame, "clone.section.log")
        log_frame.grid(row=2, column=0, sticky="nsew", pady=(8, 0))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

        self.txt_log = ScrolledText(log_frame, height=8, wrap="word")
        self.txt_log.grid(row=0, column=0, sticky="nsew")

        self._apply_language()

    def _create_env_section(self, parent, kind: str, column: int, title_key: str):
        frame = ttk.LabelFrame(parent, padding=8)
        self._register_text(frame, title_key)
        frame.grid(row=0, column=column, sticky="nsew", padx=(0 if column == 0 else 8, 0))
        frame.columnconfigure(1, weight=1)

        combo = ttk.Combobox(frame, state="readonly")
        combo.grid(row=0, column=0, columnspan=2, sticky="ew")
        combo.bind("<<ComboboxSelected>>", lambda _e, k=kind: self._on_select_env(k))

        btn_bar = ttk.Frame(frame)
        btn_bar.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(4, 8))
        btn_save = ttk.Button(btn_bar, command=lambda k=kind: self._save_env(k))
        self._register_text(btn_save, "clone.btn.save_env")
        btn_save.pack(side="left", padx=(0, 4))
        btn_rename = ttk.Button(btn_bar, command=lambda k=kind: self._rename_env(k))
        self._register_text(btn_rename, "clone.btn.rename_env")
        btn_rename.pack(side="left", padx=(0, 4))
        btn_delete = ttk.Button(btn_bar, command=lambda k=kind: self._delete_env(k))
        self._register_text(btn_delete, "clone.btn.delete_env")
        btn_delete.pack(side="left")

        labels = [
            ("clone.label.user", "user"),
            ("clone.label.password", "password"),
            ("clone.label.alias", "alias"),
            ("clone.label.host", "host"),
            ("clone.label.port", "port"),
        ]
        vars_dict: Dict[str, tk.Variable] = {
            "user": tk.StringVar(),
            "password": tk.StringVar(),
            "alias": tk.StringVar(),
            "host": tk.StringVar(),
            "port": tk.StringVar(),
        }
        for idx, (label_key, var_name) in enumerate(labels, start=2):
            lbl = ttk.Label(frame)
            self._register_text(lbl, label_key)
            lbl.grid(row=idx, column=0, sticky="w")
            show = "*" if var_name == "password" else None
            entry = ttk.Entry(frame, textvariable=vars_dict[var_name], show=show)
            entry.grid(row=idx, column=1, sticky="ew", pady=2)
        btn_check = ttk.Button(frame, command=lambda k=kind: self._check_connection(k))
        self._register_text(btn_check, "clone.btn.check_connection")
        btn_check.grid(row=idx + 1, column=0, columnspan=2, sticky="ew")

        status = ttk.Label(frame, text=_t("clone.status.disconnected"), foreground="#aa0000")
        status.grid(row=idx + 2, column=0, columnspan=2, sticky="w", pady=(4, 0))

        self.env_forms[kind] = {
            "frame": frame,
            "title_key": title_key,
            "combo": combo,
            "status": status,
            **vars_dict,
        }
        self._refresh_env_combobox(kind)

    # ------------------------------------------------------------------
    def _refresh_env_combobox(self, kind: str):
        names = sorted(self._saved_envs.keys())
        combo: ttk.Combobox = self.env_forms[kind]["combo"]  # type: ignore[index]
        values = names or self._db_list_items
        combo["values"] = values
        default_data = self._defaults.get(kind)
        if default_data:
            if values:
                combo.set(values[0])
                self._on_select_env(kind)
            else:
                combo.set("")
        elif values:
            combo.set(values[0])
            if values[0] in self._saved_envs:
                self._on_select_env(kind)
            else:
                self._on_select_env(kind)
        else:
            combo.set("")

    def _on_select_env(self, kind: str):
        name = self.env_forms[kind]["combo"].get()
        data = self._saved_envs.get(name)
        vars_dict = self.env_forms[kind]
        if not data:
            parsed = self._parse_db_entry(name)
            if parsed:
                for key, value in parsed.items():
                    vars_dict[key].set(value)  # type: ignore[index]
                self._apply_alias_details(vars_dict, parsed.get("alias", ""))
                return
            for key in ("user", "password", "alias", "host", "port"):
                vars_dict[key].set("")  # type: ignore[index]
            return
        for key in ("user", "password", "alias", "host", "port"):
            vars_dict[key].set(data.get(key, ""))  # type: ignore[index]
        self._apply_alias_details(vars_dict, vars_dict["alias"].get().strip())  # type: ignore[index]

    def _apply_default_env(self, kind: str):
        default = self._defaults.get(kind)
        if not default:
            return
        vars_dict = self.env_forms.get(kind)
        if not vars_dict:
            return
        for key in ("user", "password", "alias", "host", "port"):
            vars_dict[key].set(default.get(key, ""))  # type: ignore[index]
        self._apply_alias_details(vars_dict, vars_dict["alias"].get().strip())  # type: ignore[index]
        self._defaults[kind] = {}

    def _parse_db_entry(self, entry: str) -> Optional[Dict[str, str]]:
        if not entry:
            return None
        parts = entry.split(".", 1)
        candidate = parts[1] if len(parts) > 1 else parts[0]
        if "@" not in candidate or "/" not in candidate:
            return None
        creds, alias = candidate.split("@", 1)
        if "/" not in creds:
            return None
        user, password = creds.split("/", 1)
        block_info = block_extract(self._conn_blocks.get(alias.strip(), ""))
        return {
            "user": user.strip(),
            "password": password.strip(),
            "alias": alias.strip(),
            "host": block_info.get("host", ""),
            "port": block_info.get("port", ""),
        }

    def _apply_alias_details(self, vars_dict: Dict[str, tk.Variable], alias: str):
        if not alias:
            return
        block = self._conn_blocks.get(alias)
        if not block:
            return
        info = block_extract(block)
        if info.get("host"):
            vars_dict["host"].set(info["host"])  # type: ignore[index]
        if info.get("port"):
            vars_dict["port"].set(info["port"])  # type: ignore[index]

    def _collect_env_data(self, kind: str) -> Dict[str, str]:
        vars_dict = self.env_forms[kind]
        return {
            "user": vars_dict["user"].get().strip(),  # type: ignore[index]
            "password": vars_dict["password"].get(),  # type: ignore[index]
            "alias": vars_dict["alias"].get().strip(),  # type: ignore[index]
            "host": vars_dict["host"].get().strip(),  # type: ignore[index]
            "port": vars_dict["port"].get().strip(),  # type: ignore[index]
            "use_host_port": False,
        }

    def _validate_env_data(self, data: Dict[str, str]) -> bool:
        if not data["user"] or not data["password"]:
            messagebox.showwarning(_t(APP_TITLE_KEY), _t("clone.msg.need_user_pass"), parent=self)
            return False
        if not data["alias"]:
            messagebox.showwarning(_t(APP_TITLE_KEY), _t("clone.msg.need_alias"), parent=self)
            return False
        return True

    def _save_env(self, kind: str):
        data = self._collect_env_data(kind)
        if not self._validate_env_data(data):
            return
        default_name = self.env_forms[kind]["combo"].get() or data["alias"] or data["user"]
        name = simpledialog.askstring(_t(APP_TITLE_KEY), _t("clone.dialog.save_env"), initialvalue=default_name, parent=self)
        if not name:
            return
        data["name"] = name.strip()
        if not data["name"]:
            return
        self._saved_envs[data["name"]] = data
        try:
            _save_envs(self._saved_envs)
        except Exception as exc:
            messagebox.showerror(_t(APP_TITLE_KEY), _t("clone.msg.save_env_error", error=exc), parent=self)
            return
        self._refresh_env_combobox("source")
        self._refresh_env_combobox("target")
        messagebox.showinfo(_t(APP_TITLE_KEY), _t("clone.msg.save_env_ok"), parent=self)

    def _rename_env(self, kind: str):
        current = self.env_forms[kind]["combo"].get()
        if not current or current not in self._saved_envs:
            messagebox.showwarning(_t(APP_TITLE_KEY), _t("clone.msg.select_env"), parent=self)
            return
        new_name = simpledialog.askstring(_t(APP_TITLE_KEY), _t("clone.dialog.rename_env"), initialvalue=current, parent=self)
        if not new_name:
            return
        new_name = new_name.strip()
        if not new_name:
            return
        data = self._saved_envs.pop(current)
        data["name"] = new_name
        self._saved_envs[new_name] = data
        _save_envs(self._saved_envs)
        self._refresh_env_combobox("source")
        self._refresh_env_combobox("target")

    def _delete_env(self, kind: str):
        current = self.env_forms[kind]["combo"].get()
        if not current or current not in self._saved_envs:
            messagebox.showwarning(_t(APP_TITLE_KEY), _t("clone.msg.select_env"), parent=self)
            return
        if not messagebox.askyesno(_t(APP_TITLE_KEY), _t("clone.msg.confirm_delete_env", name=current), parent=self):
            return
        self._saved_envs.pop(current, None)
        _save_envs(self._saved_envs)
        self._refresh_env_combobox("source")
        self._refresh_env_combobox("target")

    # ------------------------------------------------------------------
    def _check_connection(self, kind: str):
        data = self._collect_env_data(kind)
        if not self._validate_env_data(data):
            return
        status: ttk.Label = self.env_forms[kind]["status"]  # type: ignore[index]
        status.configure(text=_t("clone.status.connecting"), foreground="#0066aa")
        self.update_idletasks()
        try:
            conn = db_utils.connect_oracle(
                data["user"],
                data["password"],
                data["host"],
                data["port"],
                data["alias"],
                data["use_host_port"],
            )
        except Exception as exc:
            status.configure(text=_t("clone.status.failed", error=exc), foreground="#aa0000")
            if kind == "source":
                self._source_conn = None
                self._source_connected = False
            else:
                self._target_conn = None
                self._target_connected = False
            self._update_export_button_state()
            return

        key = f"{data['user']}@{data['alias'] or data['host']}"
        if kind == "source":
            if self._target_conn_key and key == self._target_conn_key:
                status.configure(text=_t("clone.msg.same_environment"), foreground="#aa0000")
                conn.close()
                return
            if self._source_conn:
                try:
                    self._source_conn.close()
                except Exception:
                    pass
            self._source_conn = conn
            self._source_conn_key = key
            self._source_owner = data["user"].upper()
            self._source_connected = True
            status.configure(text=_t("clone.status.connected"), foreground="#228833")
            self._load_source_tables()
        else:
            if self._source_conn_key and key == self._source_conn_key:
                status.configure(text=_t("clone.msg.same_environment"), foreground="#aa0000")
                conn.close()
                return
            if self._target_conn:
                try:
                    self._target_conn.close()
                except Exception:
                    pass
            self._target_conn = conn
            self._target_conn_key = key
            self._target_owner = data["user"].upper()
            self._target_connected = True
            status.configure(text=_t("clone.status.connected"), foreground="#228833")
        self._update_export_button_state()

    def _load_source_tables(self):
        if not self._source_conn:
            return
        loader = LoadingPopup(self, _t("common.loading_tables"))

        def worker():
            try:
                tables = db_utils.fetch_accessible_tables(self._source_conn)
            except Exception as exc:
                self.after(0, lambda: self._handle_table_error(loader, exc))
                return
            self.after(0, lambda: self._apply_table_list(loader, tables))

        threading.Thread(target=worker, daemon=True).start()

    def _handle_table_error(self, loader: LoadingPopup, exc: Exception):
        loader.close()
        messagebox.showerror(_t(APP_TITLE_KEY), _t("clone.msg.table_error", error=exc), parent=self)

    def _apply_table_list(self, loader: LoadingPopup, tables: List[str]):
        loader.close()
        tables = sorted(tables)
        self._source_tables = tables
        self._filtered_tables = list(tables)
        self.lst_source_tables.delete(0, tk.END)
        for name in tables:
            self.lst_source_tables.insert(tk.END, name)

    def _filter_source_tables(self):
        keyword = self.var_table_search.get().strip().upper()
        self.lst_source_tables.delete(0, tk.END)
        if not keyword:
            self._filtered_tables = list(self._source_tables)
        else:
            self._filtered_tables = [name for name in self._source_tables if keyword in name.upper()]
        for name in self._filtered_tables:
            self.lst_source_tables.insert(tk.END, name)

    def _add_selected_tables(self):
        selection = self.lst_source_tables.curselection()
        if not selection:
            return
        for idx in selection:
            if idx >= len(self._filtered_tables):
                continue
            source = self._filtered_tables[idx]
            owner, table = db_utils.split_owner_table(source, self._source_owner or "")
            target = table
            self._add_mapping(f"{owner}.{table}", target)
        self._update_export_button_state()

    def _add_mapping(self, source: str, target: str):
        for existing in self._mapping_rows.values():
            if existing["source"] == source:
                return
        item_id = self.tree_mappings.insert("", "end", values=(source, target))
        self._mapping_rows[item_id] = {"source": source, "target": target}

    def _remove_selected_mapping(self):
        selection = self.tree_mappings.selection()
        for item in selection:
            self.tree_mappings.delete(item)
            self._mapping_rows.pop(item, None)
        self._update_export_button_state()

    def _clear_mappings(self):
        for item in list(self._mapping_rows.keys()):
            self.tree_mappings.delete(item)
        self._mapping_rows.clear()
        self._update_export_button_state()

    def _edit_target_mapping(self):
        selection = self.tree_mappings.selection()
        if not selection:
            messagebox.showwarning(_t(APP_TITLE_KEY), _t("clone.msg.select_mapping"), parent=self)
            return
        item = selection[0]
        mapping = self._mapping_rows.get(item)
        if not mapping:
            return
        current = mapping["target"]
        new_value = simpledialog.askstring(
            _t(APP_TITLE_KEY), _t("clone.dialog.target_table"), initialvalue=current, parent=self
        )
        if not new_value:
            return
        new_value = new_value.strip()
        if not new_value:
            return
        mapping["target"] = new_value
        self.tree_mappings.item(item, values=(mapping["source"], mapping["target"]))

    # ------------------------------------------------------------------
    def _update_export_button_state(self):
        enabled = self._source_connected and self._target_connected and bool(self._mapping_rows)
        self.btn_export.configure(state="normal" if enabled else "disabled")

    def _start_export(self):
        if self._export_thread and self._export_thread.is_alive():
            return
        if not self._mapping_rows:
            messagebox.showwarning(_t(APP_TITLE_KEY), _t("clone.msg.no_table_selected"), parent=self)
            return
        if not self._source_conn or not self._target_conn:
            return
        tasks = list(self._mapping_rows.values())
        self.progress.configure(maximum=len(tasks), value=0)
        self.lbl_progress.configure(text="")
        self._append_log(_t("clone.log.start", count=len(tasks)))
        self.btn_export.configure(state="disabled")
        self._cancel_event.clear()
        self._export_thread = threading.Thread(target=self._run_export_thread, args=(tasks,), daemon=True)
        self._export_thread.start()

    def _run_export_thread(self, tasks: List[Dict[str, str]]):
        total_rows = 0
        failures = 0
        action_id = history.log_action(ACTION_TYPE, ",".join(t["source"] for t in tasks), 0, "pending")
        for idx, mapping in enumerate(tasks, start=1):
            if self._cancel_event.is_set():
                break
            try:
                rows = self._copy_table(mapping)
                total_rows += rows
                self._append_log(_t("clone.log.copied", source=mapping["source"], target=mapping["target"], rows=rows))
            except Exception as exc:
                failures += 1
                self._append_log(_t("clone.log.error", source=mapping["source"], error=exc))
            finally:
                self.after(0, self._update_progress, idx, len(tasks))
        status = "success" if failures == 0 else "failed"
        message = _t("clone.log.summary", total=len(tasks), failed=failures)
        if action_id:
            history.mark_action_status(action_id, status, message, row_count=total_rows)
        self.after(0, lambda: self._finish_export(message))

    def _update_progress(self, value: int, total: int):
        self.progress.configure(value=value, maximum=total)
        self.lbl_progress.configure(text=f"{value}/{total}")

    def _finish_export(self, message: str):
        self.progress.configure(value=self.progress["maximum"])
        self.lbl_progress.configure(text=message)
        self.btn_export.configure(state="normal")
        messagebox.showinfo(_t(APP_TITLE_KEY), message, parent=self)

    def _copy_table(self, mapping: Dict[str, str]) -> int:
        if not self._source_conn or not self._target_conn:
            return 0
        source_owner, source_table = db_utils.split_owner_table(mapping["source"], self._source_owner)
        target_owner, target_table = db_utils.split_owner_table(mapping["target"], self._target_owner)
        columns = db_utils.fetch_table_columns(self._source_conn, mapping["source"], self._source_owner)
        column_names = [c["column_name"] for c in columns]
        if not column_names:
            raise RuntimeError(_t("clone.msg.no_columns", table=mapping["source"]))
        col_expr = ", ".join(column_names)
        select_sql = f"SELECT {col_expr} FROM {source_owner}.{source_table}"
        placeholders = ", ".join(f":{idx+1}" for idx in range(len(column_names)))
        insert_sql = f"INSERT INTO {target_owner}.{target_table} ({col_expr}) VALUES ({placeholders})"
        row_count = 0
        src_cur = self._source_conn.cursor()
        dst_cur = self._target_conn.cursor()
        try:
            if self.var_truncate.get():
                try:
                    dst_cur.execute(f"TRUNCATE TABLE {target_owner}.{target_table}")
                except Exception:
                    dst_cur.execute(f"DELETE FROM {target_owner}.{target_table}")
            src_cur.execute(select_sql)
            while True:
                rows = src_cur.fetchmany(self.BATCH_SIZE)
                if not rows:
                    break
                dst_cur.executemany(insert_sql, rows)
                row_count += len(rows)
            self._target_conn.commit()
        except Exception:
            self._target_conn.rollback()
            raise
        finally:
            try:
                src_cur.close()
            except Exception:
                pass
            try:
                dst_cur.close()
            except Exception:
                pass
        return row_count

    # ------------------------------------------------------------------
    def _append_log(self, text: str):
        self.txt_log.insert(tk.END, text.strip() + "\n")
        self.txt_log.see(tk.END)

    def _on_language_changed(self, _lang: str):
        self._apply_language()

    def _apply_language(self):
        self.title(_t("clone.title"))
        for widget, key in self._text_widgets:
            try:
                widget.configure(text=_t(key))
            except tk.TclError:
                continue
        for info in self.env_forms.values():
            frame = info.get("frame")
            title_key = info.get("title_key")
            if frame and title_key:
                frame.configure(text=_t(title_key))
        self.tree_mappings.heading("source", text=_t("clone.column.source"))
        self.tree_mappings.heading("target", text=_t("clone.column.target"))

    def _on_close(self):
        self._cancel_event.set()
        if self._source_conn:
            try:
                self._source_conn.close()
            except Exception:
                pass
        if self._target_conn:
            try:
                self._target_conn.close()
            except Exception:
                pass
        i18n.remove_listener(self._lang_listener)
        self.destroy()


def open_clone_window(
    parent: tk.Widget,
    *,
    default_source: Optional[Dict[str, str]] = None,
    default_target: Optional[Dict[str, str]] = None,
    conn_blocks: Optional[Dict[str, str]] = None,
):
    """Helper mở màn hình clone."""
    CloneDbWindow(parent, default_source=default_source, default_target=default_target, conn_blocks=conn_blocks)
def _load_db_list_items() -> List[str]:
    if not os.path.isfile(DB_LIST_PATH):
        return []
    try:
        with open(DB_LIST_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        items = data.get("items", [])
        return [str(item) for item in items if isinstance(item, str)]
    except Exception:
        return []
