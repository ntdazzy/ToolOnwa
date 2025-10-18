#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ToolONWA VIP v1.0 - main
"""
import os, re, sys, json, threading, logging
import datetime as dt
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinter import font as tkfont
from tkinter.scrolledtext import ScrolledText
from screen.DB import edit_connection
from screen.DB import cmd_sql_plus
from screen.DB import db_utils
from screen.DB import insert as insert_screen
from screen.DB import update as update_screen
from screen.DB import backup as backup_screen
from screen.MU import log_viewer as log_viewer
from screen.General import history_window, rdsinfo
from core import i18n

APP_TITLE = "ToolONWA VIP v1.0"
WIN_W, WIN_H = 560, 600
BASE_DIR = os.path.dirname(__file__)
FONTS_DIR = None  # set below
ICON_PATH = None  # set below

# -- onefile support: resolve bundled resources --
def resource_path(rel):
    base = getattr(sys, "_MEIPASS", BASE_DIR)
    return os.path.join(base, rel)

# read-only bundled resources
READ_FONTS_DIR = resource_path("fonts")
READ_ICONS_DIR = resource_path("icons")
READ_ORA_PATH  = resource_path(os.path.join("ora","tnsnames.ora"))

# persistent config dir (user profile) for writable configs
APPDATA = os.environ.get("APPDATA") or os.path.expanduser("~")
PERSIST_DIR = os.path.join(APPDATA, "ToolVIP")
os.makedirs(PERSIST_DIR, exist_ok=True)

DEFAULT_ORA_PATH = READ_ORA_PATH
FONTS_DIR = READ_FONTS_DIR
ICON_PATH = os.path.join(READ_ICONS_DIR, "logo.ico")

CONFIGS_DIR = os.path.join(PERSIST_DIR, "configs")
CONFIG_PATH = os.path.join(CONFIGS_DIR, "config.json")
DB_LIST_PATH = os.path.join(CONFIGS_DIR, "db_list.json")
LOG_DIR = os.path.join(PERSIST_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)

LOGGER = logging.getLogger("ToolVIP")


def _setup_global_logging() -> None:
    log_path = os.path.join(LOG_DIR, dt.datetime.now().strftime("%Y%m%d") + ".log")
    handlers: list[logging.Handler] = []
    try:
        handlers.append(logging.FileHandler(log_path, encoding="utf-8"))
    except Exception:
        pass
    handlers.append(logging.StreamHandler())
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s:%(lineno)d %(message)s",
        handlers=handlers,
    )

    def _global_excepthook(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        logging.getLogger("ToolVIP").exception("Unhandled exception", exc_info=(exc_type, exc_value, exc_traceback))

    sys.excepthook = _global_excepthook

    def _threading_excepthook(args: threading.ExceptHookArgs) -> None:
        logging.getLogger("ToolVIP").exception(
            "Unhandled thread exception in %s", args.thread.name if args.thread else "thread",
            exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
        )

    threading.excepthook = _threading_excepthook


_setup_global_logging()
# ---------------- helpers ----------------
_ALIAS_RE = re.compile(r"^\s*([A-Za-z0-9_.-]+)\s*=\s*\(", re.MULTILINE)
def parse_tnsnames_blocks(text: str):
    results = {}
    positions = [(m.group(1), m.start()) for m in _ALIAS_RE.finditer(text)]
    if not positions: return results
    positions.append(("#END#", len(text)))
    for i in range(len(positions)-1):
        alias, start = positions[i]
        _, end = positions[i+1]
        results[alias] = text[start:end].strip()
    return results

def block_extract(block: str):
    def pick(pattern):
        m = re.search(pattern, block, flags=re.IGNORECASE)
        return m.group(1).strip() if m else ""
    return {"host": pick(r"HOST\s*=\s*([^) \r\n]+)"),
            "port": pick(r"PORT\s*=\s*([0-9]+)"),
            "service": pick(r"SERVICE_NAME\s*=\s*([^) \r\n]+)"),
            "sid": pick(r"SID\s*=\s*([^) \r\n]+)")}

def ensure_configs_dir():
    os.makedirs(CONFIGS_DIR, exist_ok=True)

def save_config(cfg):
    ensure_configs_dir()
    with open(CONFIG_PATH,"w",encoding="utf-8") as f:
        json.dump(cfg,f,indent=2,ensure_ascii=False)

def load_config():
    ensure_configs_dir()
    if not os.path.isfile(CONFIG_PATH):
        cfg = {"lang":"VN","ora_path":DEFAULT_ORA_PATH,"last_alias":None,"use_host_port":False}
        save_config(cfg)
                # fallback if saved ora_path missing
        if not os.path.isfile(cfg.get("ora_path","")):
            cfg["ora_path"] = DEFAULT_ORA_PATH; save_config(cfg)
        return cfg
    try:
        with open(CONFIG_PATH,"r",encoding="utf-8") as f:
            cfg=json.load(f)
            if cfg.get("lang") in ("vi","ja"):
                cfg["lang"]="VN" if cfg["lang"]=="vi" else "JP"
                    # fallback if saved ora_path missing
        if not os.path.isfile(cfg.get("ora_path","")):
            cfg["ora_path"] = DEFAULT_ORA_PATH; save_config(cfg)
        return cfg
    except Exception as exc:
        LOGGER.exception("Failed to load config %s", CONFIG_PATH)
        return {"lang":"VN","ora_path":DEFAULT_ORA_PATH,"last_alias":None,"use_host_port":False}

def ensure_db_list_file():
    ensure_configs_dir()
    if not os.path.isfile(DB_LIST_PATH):
        sample = {
            "items": [
                "1.SJUSER04/SJUSER04@ONDEVDB01",
                "2.CM_NRI04/NRI04@ONDEVDB10",
                "3.CL_NRI04/NRI@ONDEVDB10",
                "4.PO_NRI03/NRI@ONDEVDB10",
                "5.JAN_EDI03/nri@ONDEVDB10",
                "6.JOH_MART/MART@WJDB03X",
                "7.JOH_MART/MART@WJDB13X",
                "8.JOH_HAIBUN/HAIBUN@WJDB03X",
                "9.JOH_LEGACY/LEGACY@WJDB13X"
            ]
        }
        with open(DB_LIST_PATH,"w",encoding="utf-8") as f:
            json.dump(sample,f,indent=2,ensure_ascii=False)
        return True
    return False

class ToolVIP(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        if os.path.isfile(ICON_PATH):
            try: self.iconbitmap(ICON_PATH)
            except Exception: pass

        self.geometry(f"{WIN_W}x{WIN_H}")
        self.minsize(WIN_W, WIN_H); self.maxsize(WIN_W, WIN_H)
        self.resizable(False, False)

        self.config = load_config()
        preferred_lang = self.config.get("lang", i18n.LANG_VI)
        i18n.set_language(preferred_lang)
        self.lang = i18n.get_language()
        self.current_ora_path = self.config.get("ora_path") or DEFAULT_ORA_PATH
        self._logger = logging.getLogger("ToolVIP")
        self.report_callback_exception = self._handle_callback_exception
        self._logger.info("Application started")

        # state
        self.show_pwd = tk.BooleanVar(value=False)
        self.var_use_host_port = tk.BooleanVar(value=bool(self.config.get("use_host_port", False)))
        self._last_error = ""
        self._status_custom = False
        self.conn_blocks = {}
        self._history_window = None

        self._setup_fonts()
        self._build_ui()
        self._lang_listener = self._handle_language_change
        i18n.add_listener(self._lang_listener)
        self._apply_language()
        self._center_on_screen()
        self._load_ora(self.current_ora_path)
        created = ensure_db_list_file()
        self._load_combobox_from_json()
        if created: self._set_status("main.status.created_db_list", ok=False)

    def _setup_fonts(self):
        base = tkfont.nametofont("TkDefaultFont"); base.configure(size=10)
        try:
            if sys.platform.startswith("win") and os.path.isdir(FONTS_DIR):
                import ctypes; FR_PRIVATE=0x10
                for fn in os.listdir(FONTS_DIR):
                    if fn.lower().endswith((".ttf",".otf")):
                        ctypes.windll.gdi32.AddFontResourceExW(os.path.join(FONTS_DIR,fn), FR_PRIVATE,0)
        except Exception as exc:
            self._logger.warning("Failed to register font resources: %s", exc)
        style = ttk.Style()
        style.configure("TButton", padding=(10,6))
        style.configure("Status.TLabel", padding=(6,2))
        style.configure("Details.TButton", padding=(6,2))   # smaller details button

    def _build_ui(self):
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        root = ttk.Frame(self, padding=8)
        root.grid(row=0, column=0, sticky="nsew")
        root.columnconfigure(0, weight=1)

        # Nhóm DB
        self.db_group = ttk.LabelFrame(root, padding=(8, 6), relief="ridge", borderwidth=2)
        self.db_group.grid(row=0, column=0, sticky="nsew", padx=2, pady=(2, 8))
        self.db_group.columnconfigure(0, weight=1)
        self.db_group.columnconfigure(1, weight=0)

        self.frm_connection = ttk.LabelFrame(self.db_group, padding=8, relief="ridge", borderwidth=2)
        self.frm_connection.grid(row=0, column=0, sticky="nsew", padx=(0, 8), pady=(0, 8))
        self.frm_connection.columnconfigure(0, weight=1)
        self.frm_connection.columnconfigure(1, weight=1)
        self.frm_connection.columnconfigure(2, weight=0)

        self.cbo_conn = ttk.Combobox(self.frm_connection, state="readonly")
        self.cbo_conn.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 6))
        self.cbo_conn.bind("<<ComboboxSelected>>", self._on_pick_connection)

        self.lbl_user = ttk.Label(self.frm_connection)
        self.lbl_user.grid(row=1, column=0, sticky="w", pady=2, padx=(0, 6))
        self.ent_user = ttk.Entry(self.frm_connection)
        self.ent_user.grid(row=1, column=1, columnspan=2, sticky="ew", pady=2)

        self.lbl_password = ttk.Label(self.frm_connection)
        self.lbl_password.grid(row=2, column=0, sticky="w", pady=2, padx=(0, 6))
        self.ent_pass = ttk.Entry(self.frm_connection, show="*")
        self.ent_pass.grid(row=2, column=1, sticky="ew", pady=2)
        self.chk_show_pwd = ttk.Checkbutton(
            self.frm_connection,
            variable=self.show_pwd,
            command=self._toggle_show_pwd,
        )
        self.chk_show_pwd.grid(row=2, column=2, sticky="w")

        self.lbl_datasource = ttk.Label(self.frm_connection)
        self.lbl_datasource.grid(row=3, column=0, sticky="w", pady=2, padx=(0, 6))
        self.ent_dsn = ttk.Entry(self.frm_connection)
        self.ent_dsn.grid(row=3, column=1, columnspan=2, sticky="ew", pady=(2, 0))

        self.lbl_hostport = ttk.Label(self.frm_connection)
        self.lbl_hostport.grid(row=4, column=0, sticky="w", pady=2, padx=(0, 6))
        self.ent_host = ttk.Entry(self.frm_connection)
        self.ent_host.grid(row=4, column=1, sticky="ew", pady=2, padx=(0, 3))
        self.ent_port = ttk.Entry(self.frm_connection, width=8)
        self.ent_port.grid(row=4, column=2, sticky="ew", pady=2, padx=(3, 0))

        self.chk_sqlplus_host = ttk.Checkbutton(
            self.frm_connection,
            variable=self.var_use_host_port,
            command=self._on_toggle_hostport,
        )
        self.chk_sqlplus_host.grid(row=5, column=0, columnspan=3, sticky="w", pady=(4, 0))

        self.frm_shortcuts = ttk.Frame(self.db_group)
        self.frm_shortcuts.grid(row=0, column=1, sticky="nsew", pady=(24, 8))
        self.frm_shortcuts.columnconfigure(0, weight=1)
        ttk.Frame(self.frm_shortcuts).grid(row=0, column=0, sticky="ns")
        self.btn_open_ora = ttk.Button(self.frm_shortcuts, command=self._open_ora_dialog, width=18)
        self.btn_open_ora.grid(row=1, column=0, sticky="ew", pady=(6, 6))
        self.btn_check = ttk.Button(self.frm_shortcuts, command=self._check_connection, width=18)
        self.btn_check.grid(row=2, column=0, sticky="ew")
        self.btn_show_logs = ttk.Button(self.frm_shortcuts, command=self._show_logs_dialog, width=18)
        self.btn_show_logs.grid(row=3, column=0, sticky="ew", pady=(6, 0))

        self.frm_action = ttk.LabelFrame(self.db_group, padding=8, relief="ridge", borderwidth=2)
        self.frm_action.grid(row=1, column=0, columnspan=2, sticky="ew")
        for i in range(3):
            self.frm_action.columnconfigure(i, weight=1)
        self.btn_insert = ttk.Button(self.frm_action, command=self._open_insert_screen)
        self.btn_insert.grid(row=0, column=0, sticky="ew", padx=4, pady=4)
        self.btn_update = ttk.Button(self.frm_action, command=self._open_update_screen)
        self.btn_update.grid(row=0, column=1, sticky="ew", padx=4, pady=4)
        self.btn_backup = ttk.Button(self.frm_action, command=self._open_backup_restore)
        self.btn_backup.grid(row=0, column=2, sticky="ew", padx=4, pady=4)
        self.btn_sqlplus = ttk.Button(self.frm_action, command=self._run_cmd_sqlplus)
        self.btn_sqlplus.grid(row=1, column=0, sticky="ew", padx=4, pady=4)
        self.btn_compare = ttk.Button(self.frm_action, command=self._coming_soon)
        self.btn_compare.grid(row=1, column=1, sticky="ew", padx=4, pady=4)
        self.btn_edit_conn = ttk.Button(self.frm_action, command=self._edit_connection)
        self.btn_edit_conn.grid(row=1, column=2, sticky="ew", padx=4, pady=4)

        self.frm_mu = ttk.LabelFrame(root, padding=(8, 6), relief="ridge", borderwidth=2)
        self.frm_mu.grid(row=1, column=0, sticky="ew", padx=2, pady=(0, 8))
        self.btn_log_mu = ttk.Button(self.frm_mu, command=self._open_log_view_mu)
        self.btn_log_mu.grid(row=0, column=0, padx=4, pady=4, sticky="w")

        self.frm_common = ttk.LabelFrame(root, padding=(8, 6), relief="ridge", borderwidth=2)
        self.frm_common.grid(row=2, column=0, sticky="ew", padx=2, pady=(0, 8))
        for i in range(4):
            self.frm_common.columnconfigure(i, weight=1)
        self.btn_rds = ttk.Button(self.frm_common, command=self._open_rds_info)
        self.btn_rds.grid(row=0, column=0, padx=8, pady=4, sticky="ew")
        self.btn_docs = ttk.Button(self.frm_common, command=self._coming_soon)
        self.btn_docs.grid(row=0, column=1, padx=8, pady=4, sticky="ew")
        self.btn_tips = ttk.Button(self.frm_common, command=self._coming_soon)
        self.btn_tips.grid(row=0, column=2, padx=8, pady=4, sticky="ew")
        self.btn_history = ttk.Button(self.frm_common, command=self._open_history_window)
        self.btn_history.grid(row=0, column=3, padx=8, pady=4, sticky="ew")

        bottom = ttk.Frame(root)
        bottom.grid(row=3, column=0, sticky="ew", pady=(4, 0))
        bottom.columnconfigure(0, weight=1)

        self.lbl_status = ttk.Label(bottom, anchor="w", relief="sunken", style="Status.TLabel")
        self.lbl_status.grid(row=0, column=0, sticky="ew", padx=(0, 6))

        self.btn_details = ttk.Button(bottom, width=8, command=self._show_error_details, style="Details.TButton")
        self.btn_details.grid(row=0, column=1, sticky="e")

        self.lbl_language = ttk.Label(bottom)
        self.lbl_language.grid(row=0, column=2, sticky="e", padx=(8, 4))
        self.cbo_lang = ttk.Combobox(bottom, state="readonly", width=6, values=[i18n.LANG_VI, i18n.LANG_JP])
        self.cbo_lang.grid(row=0, column=3, sticky="e")
        self.cbo_lang.set(self.lang)
        self.cbo_lang.bind("<<ComboboxSelected>>", self._on_change_lang)
    def _center_on_screen(self):
        self.update_idletasks()
        w,h=self.winfo_width(),self.winfo_height()
        x=(self.winfo_screenwidth()-w)//2; y=(self.winfo_screenheight()-h)//2
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _t(self, key: str, default: str | None = None, **fmt) -> str:
        """Tiện ích gọi bộ dịch chung."""
        return i18n.translate(key, default=default, **fmt)

    def _handle_language_change(self, lang: str) -> None:
        """Callback khi ngôn ngữ toàn cục thay đổi."""
        self.lang = lang
        self._apply_language()

    def destroy(self):
        if hasattr(self, "_lang_listener"):
            i18n.remove_listener(self._lang_listener)
        super().destroy()

    def _apply_language(self) -> None:
        """Cập nhật toàn bộ nhãn theo ngôn ngữ hiện tại."""
        self.lang = i18n.get_language()
        if self.cbo_lang.get() != self.lang:
            self.cbo_lang.set(self.lang)

        self.db_group.config(text=self._t("main.section.db"))
        self.frm_connection.config(text=self._t("main.section.connection"))
        self.lbl_user.config(text=self._t("main.label.user_id"))
        self.lbl_password.config(text=self._t("main.label.password"))
        self.chk_show_pwd.config(text=self._t("main.btn.show_password"))
        self.lbl_datasource.config(text=self._t("main.label.data_source"))
        self.lbl_hostport.config(text=self._t("main.label.host_port"))
        self.chk_sqlplus_host.config(text=self._t("main.chk.sqlplus_hostport"))

        self.btn_open_ora.config(text=self._t("main.btn.open_ora"))
        self.btn_check.config(text=self._t("main.btn.check_connection"))
        self.btn_show_logs.config(text=self._t("main.btn.show_logs"))

        self.frm_action.config(text=self._t("main.section.actions"))
        self.btn_insert.config(text=self._t("main.btn.insert"))
        self.btn_update.config(text=self._t("main.btn.update"))
        self.btn_backup.config(text=self._t("main.btn.backup"))
        self.btn_sqlplus.config(text=self._t("main.btn.sqlplus"))
        self.btn_compare.config(text=self._t("main.btn.compare"))
        self.btn_edit_conn.config(text=self._t("main.btn.edit_conn"))

        self.frm_mu.config(text=self._t("main.section.mu"))
        self.btn_log_mu.config(text=self._t("main.btn.read_log_mu"))

        self.frm_common.config(text=self._t("main.section.common"))
        self.btn_rds.config(text=self._t("main.btn.rds_info"))
        self.btn_docs.config(text=self._t("main.btn.docs"))
        self.btn_tips.config(text=self._t("main.btn.tips"))
        if hasattr(self, "btn_history"):
            self.btn_history.config(text=self._t("main.btn.history"))

        if not getattr(self, "_status_custom", False):
            self.lbl_status.config(text=self._t("main.status.not_connected"))
        self.btn_details.config(text=self._t("main.btn.details"))

        self.lbl_language.config(text=self._t("main.label.language"))

    def _handle_callback_exception(self, exc, value, tb) -> None:
        self._logger.exception("Tkinter callback error", exc_info=(exc, value, tb))
        try:
            messagebox.showerror(APP_TITLE, self._t("main.msg.generic_error", error=str(value)), parent=self)
        except Exception:
            pass

    def _log_exception(self, message: str) -> None:
        self._logger.exception(message)

    def _on_change_lang(self, _event=None) -> None:
        lang = self.cbo_lang.get()
        i18n.set_language(lang)
        self.config["lang"] = i18n.get_language()
        save_config(self.config)



    # ---------- data sources ----------
    def _open_ora_dialog(self):
        initdir = os.path.dirname(self.current_ora_path) if self.current_ora_path else BASE_DIR
        path = filedialog.askopenfilename(
            title=self._t("main.btn.open_ora"),
            filetypes=[("tnsnames.ora", "tnsnames.ora"), ("All files", "*.*")],
            initialdir=initdir,
        )
        if path:
            self.current_ora_path = path
            self.config["ora_path"] = path
            save_config(self.config)
            self._load_ora(path)
            self._set_status("main.msg.loaded_tns", ok=False)



    def _load_ora(self, path):
        if not os.path.isfile(path):
            if os.path.isfile(DEFAULT_ORA_PATH):
                path = DEFAULT_ORA_PATH
                self.current_ora_path = path
                self.config["ora_path"] = path
                save_config(self.config)
            else:
                return
        try:
            with open(path,"r",encoding="utf-8",errors="ignore") as f: text=f.read()
            self.conn_blocks=parse_tnsnames_blocks(text)
        except Exception as exc:
            self._log_exception(f"Failed to load tnsnames file: {path}")
            messagebox.showerror(APP_TITLE, self._t("main.msg.load_tns_error", error=str(exc)))

    def _load_combobox_from_json(self):
        ensure_configs_dir()
        try:
            with open(DB_LIST_PATH,"r",encoding="utf-8") as f:
                data=json.load(f)
            items=[str(x) for x in data.get("items",[])]
        except Exception as exc:
            self._log_exception(f"Failed to read DB list from {DB_LIST_PATH}")
            items=[]
        self.cbo_conn["values"]=items
        if items:
            self.cbo_conn.set(items[0]); self._on_pick_connection()
        else:
            self._set_status("main.msg.no_config_items", ok=False)

    def _parse_display_item(self, disp: str):
        s = disp.strip()
        if re.match(r"^\d+\.", s): s = s.split(".",1)[1].strip()
        if s.startswith("@"): return "", "", s[1:]
        try:
            left, alias = s.split("@",1)
            user, passwd = left.split("/",1)
            return user.strip(), passwd.strip(), alias.strip()
        except ValueError:
            return "", "", s

    def _on_pick_connection(self,_evt=None):
        disp = self.cbo_conn.get()
        user, pwd, alias = self._parse_display_item(disp)
        self.ent_user.delete(0,tk.END); self.ent_user.insert(0,user)
        self.ent_pass.delete(0,tk.END); self.ent_pass.insert(0,pwd)
        self.ent_dsn.delete(0,tk.END); self.ent_dsn.insert(0,alias)
        block = self.conn_blocks.get(alias,""); ex = block_extract(block)
        self.ent_host.delete(0,tk.END); self.ent_host.insert(0, ex.get("host",""))
        self.ent_port.delete(0,tk.END); self.ent_port.insert(0, ex.get("port",""))
        self.config["last_alias"]=alias; save_config(self.config)
        # Any non-error status should hide details
        self._last_error = ""

    def _check_connection(self):
        user=self.ent_user.get().strip(); pwd=self.ent_pass.get().strip()
        host=self.ent_host.get().strip(); port=self.ent_port.get().strip()
        data_src=self.ent_dsn.get().strip()
        if not (user and pwd and data_src):
            messagebox.showwarning(APP_TITLE, self._t("main.msg.missing_credentials")); return
        loading = tk.Toplevel(self)
        loading.title("Checking...")
        loading.resizable(False, False)
        ttk.Label(loading, text=self._t("main.msg.checking_connection")).grid(row=0, column=0, padx=12, pady=(12, 6))
        pb = ttk.Progressbar(loading, mode="indeterminate", length=220)
        pb.grid(row=1, column=0, padx=12, pady=(0, 12))
        pb.start(10)

        # cháº·n ngÆ°á»i dÃ¹ng tá»± Ä‘Ã³ng cá»­a sá»• trong khi Ä‘ang check
        loading.protocol("WM_DELETE_WINDOW", lambda: None)

        loading.transient(self)
        loading.grab_set()
        loading.update_idletasks()
        x = self.winfo_rootx() + (self.winfo_width() - loading.winfo_width()) // 2
        y = self.winfo_rooty() + (self.winfo_height() - loading.winfo_height()) // 2
        loading.geometry(f"+{x}+{y}")

        result = {"ok": False, "msg": ""}
        _finished = {"v": False}  # guard chá»‘ng gá»i finish 2 láº§n

        def worker():
            try:
                conn = db_utils.connect_oracle(
                    user,
                    pwd,
                    host,
                    port,
                    data_src,
                    bool(self.var_use_host_port.get()),
                )
                conn.close()
                result["ok"] = True
            except db_utils.OracleDriverNotAvailable as exc:
                self._logger.error("Oracle driver not available: %s", exc)
                result["msg"] = str(exc)
            except Exception as exc:
                self._logger.exception("Connection check failed for %s", data_src)
                result["msg"] = str(exc)
            finally:
                self.after(0, finish)

        def finish():
            if _finished["v"]:
                return
            _finished["v"] = True
            # an toÃ n khi widget Ä‘Ã£ bá»‹ há»§y
            try:
                if pb.winfo_exists():
                    try:
                        pb.stop()
                    except tk.TclError:
                        pass
            except tk.TclError:
                pass
            try:
                if loading.winfo_exists():
                    loading.destroy()
            except tk.TclError:
                pass

            if result["ok"]:
                self._set_status("main.msg.conn_success", ok=True)
                messagebox.showinfo(APP_TITLE, self._t("main.msg.conn_success"))
            else:
                self._set_status("main.msg.conn_fail", ok=False, details=result["msg"])
                messagebox.showerror(APP_TITLE, f"{self._t('main.msg.conn_fail')}: {result['msg'] or self._t('common.unknown_error')}")

        threading.Thread(target=worker, daemon=True).start()


    def _set_status(self, text_key, *, ok: bool = False, details: str | None = None, translate: bool = True) -> None:
        text = self._t(text_key) if translate else text_key
        self._status_custom = translate and text_key not in {"main.status.not_connected"}
        font = tkfont.nametofont("TkDefaultFont").copy()
        font.configure(weight="normal")
        self.lbl_status.configure(text=text, font=font, foreground="black")
        self._last_error = details or ""

    def _on_toggle_hostport(self):
        self.config["use_host_port"] = bool(self.var_use_host_port.get())
        save_config(self.config)

    def _show_error_details(self):
        if not self._last_error:
            messagebox.showinfo(APP_TITLE, self._t("main.msg.no_error_detail"))
            return
        win = tk.Toplevel(self)
        win.title(self._t("main.popup.details_title"))
        win.resizable(False, False)
        w, h = 820, 420
        x = self.winfo_rootx() + (self.winfo_width() - w) // 2
        y = self.winfo_rooty() + (self.winfo_height() - h) // 2
        win.geometry(f"{w}x{h}+{x}+{y}")
        frm = ttk.Frame(win, padding=10)
        frm.pack(fill="both", expand=True)
        txt = ScrolledText(frm, wrap="word")
        txt.pack(fill="both", expand=True)
        txt.configure(fg="black")
        txt.insert("1.0", self._last_error)
        txt.config(state="disabled")
        ttk.Button(frm, text=self._t("common.close"), command=win.destroy).pack(anchor="e", pady=(8, 0))



    def _coming_soon(self): messagebox.showinfo(APP_TITLE, self._t("main.msg.coming_soon"))

    def _show_logs_dialog(self) -> None:
        try:
            files = sorted(
                [os.path.join(LOG_DIR, name) for name in os.listdir(LOG_DIR) if name.lower().endswith(".log")],
                reverse=True,
            )
        except Exception as exc:
            self._logger.exception("Failed to list log files")
            messagebox.showerror(APP_TITLE, self._t("main.log.open_error", error=str(exc)), parent=self)
            return

        win = tk.Toplevel(self)
        win.title(i18n.translate("main.log.title"))
        win.geometry("520x380")
        win.resizable(False, False)
        try:
            if os.path.isfile(ICON_PATH):
                win.iconbitmap(ICON_PATH)
        except Exception:
            pass
        frame = ttk.Frame(win, padding=10)
        frame.pack(fill="both", expand=True)

        if not files:
            ttk.Label(frame, text=i18n.translate("main.log.no_files")).pack(fill="x", pady=(0, 8))
            ttk.Button(frame, text=self._t("common.close"), command=win.destroy).pack(anchor="e")
            return

        listbox = tk.Listbox(frame, height=14, activestyle="dotbox")
        listbox.pack(fill="both", expand=True)
        for path in files:
            listbox.insert(tk.END, os.path.basename(path))

        listbox.bind("<Double-Button-1>", lambda _e: self._open_log_file(win, files, listbox))
        ttk.Button(frame, text=self._t("common.close"), command=win.destroy).pack(anchor="e", pady=(8, 0))
        listbox.focus_set()

    def _open_log_file(self, parent: tk.Toplevel, files: list[str], listbox: tk.Listbox) -> None:
        selection = listbox.curselection()
        if not selection:
            return
        path = files[selection[0]]
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                content = fh.read()
        except Exception as exc:
            self._logger.exception("Failed to open log file %s", path)
            messagebox.showerror(APP_TITLE, self._t("main.log.open_error", error=str(exc)), parent=parent)
            return

        win = tk.Toplevel(parent)
        win.title(i18n.translate("main.log.content_title", name=os.path.basename(path)))
        win.geometry("840x520")
        try:
            if os.path.isfile(ICON_PATH):
                win.iconbitmap(ICON_PATH)
        except Exception:
            pass
        text = ScrolledText(win, wrap="word")
        text.pack(fill="both", expand=True, padx=8, pady=(8, 0))
        text.insert("1.0", content)
        text.configure(state="disabled")

        btn_frame = ttk.Frame(win, padding=8)
        btn_frame.pack(fill="x")
        ttk.Button(btn_frame, text=i18n.translate("main.log.copy"), command=lambda: self._copy_log_to_clipboard(content)).pack(side="left")
        ttk.Button(btn_frame, text=self._t("common.close"), command=win.destroy).pack(side="right")

    def _copy_log_to_clipboard(self, content: str) -> None:
        try:
            self.clipboard_clear()
            self.clipboard_append(content)
            messagebox.showinfo(APP_TITLE, i18n.translate("main.log.copied"), parent=self)
        except Exception as exc:
            self._logger.exception("Copy log failed")
    def _edit_connection(self):
        initial = {
            "user": self.ent_user.get().strip(),
            "password": self.ent_pass.get().strip(),
            "alias": self.ent_dsn.get().strip(),
            "host": self.ent_host.get().strip(),
            "port": self.ent_port.get().strip(),
            "current_display": self.cbo_conn.get().strip(),
        }
        paths = {"config": CONFIG_PATH, "db_list": DB_LIST_PATH, "tnsnames": self.current_ora_path}
        edit_connection.open_dialog(self, initial, paths, self.conn_blocks)
        self._load_ora(self.current_ora_path); self._load_combobox_from_json()
        target = f"{initial['user']}/{initial['password']}@{initial['alias']}"
        for v in self.cbo_conn['values']:
            if v.endswith(target) or v.split('.',1)[-1]==target:
                self.cbo_conn.set(v); self._on_pick_connection(); break

    def _toggle_show_pwd(self):
        self.ent_pass.config(show="" if self.show_pwd.get() else "*")

    def _run_cmd_sqlplus(self):
        user = self.ent_user.get().strip(); pwd  = self.ent_pass.get().strip()
        alias= self.ent_dsn.get().strip(); host = self.ent_host.get().strip(); port = self.ent_port.get().strip()
        if not (user and pwd and alias):
            messagebox.showwarning(APP_TITLE, self._t("main.msg.missing_credentials")); return
        try:
            cmd_sql_plus.open_sqlplus(user, pwd, host, port, alias, self.var_use_host_port.get())
        except Exception as exc:
            self._logger.exception("Failed to open SQL*Plus for %s", alias)
            messagebox.showerror(APP_TITLE, self._t("main.msg.sqlplus_error", error=str(exc)))

    def _collect_connection_info(self) -> dict | None:
        user = self.ent_user.get().strip()
        password = self.ent_pass.get()
        alias = self.ent_dsn.get().strip()
        host = self.ent_host.get().strip()
        port = self.ent_port.get().strip()
        if not user or not password or not alias:
            messagebox.showwarning(APP_TITLE, self._t("main.msg.need_user_pass_alias"))
            return None
        return {
            "user": user,
            "password": password,
            "alias": alias,
            "host": host,
            "port": port,
            "use_host_port": bool(self.var_use_host_port.get()),
        }

    def _open_rds_info(self):
        """Mở màn hình quản lý thông tin RDS."""
        try:
            rdsinfo.open_rds_window(self)
        except Exception as exc:
            self._logger.exception("Failed to open RDS window")
            messagebox.showerror(APP_TITLE, self._t("rds.msg.open_error", error=str(exc)), parent=self)

    def _open_insert_screen(self):
        info = self._collect_connection_info()
        if not info:
            return
        insert_screen.open_insert_window(self, info)

    def _open_update_screen(self):
        info = self._collect_connection_info()
        if not info:
            return
        update_screen.open_update_window(self, info)

    def _open_backup_restore(self):
        info = self._collect_connection_info()
        if not info:
            return
        selection = backup_screen.ask_backup_mode(self)
        if selection == "backup":
            backup_screen.open_backup_window(self, info)
        elif selection == "restore_backup":
            backup_screen.open_restore_from_backup_window(self, info)
        elif selection == "restore_csv":
            backup_screen.open_restore_from_csv_window(self, info)



    def _open_history_window(self):
        """Mo man hinh lich su thao tac."""
        try:
            if self._history_window and self._history_window.winfo_exists():
                self._history_window.lift()
                self._history_window.focus_force()
                return
            window = history_window.HistoryWindow(self)

            def _cleanup(event):
                if event.widget is window:
                    self._history_window = None

            window.bind("<Destroy>", _cleanup)
            self._history_window = window
        except Exception as exc:
            self._logger.exception("Failed to open history window")
            messagebox.showerror(APP_TITLE, self._t("history.msg.open_error", error=str(exc)), parent=self)


    def _open_log_view_mu(self):
        try:
            log_viewer.open_log_viewer(self, ICON_PATH)
        except Exception as exc:
            self._logger.exception("Failed to open MU log viewer")
            messagebox.showerror(APP_TITLE, self._t("main.msg.log_viewer_error", error=str(exc)))

def main(): app=ToolVIP(); app.mainloop()
if __name__=="__main__": main()
