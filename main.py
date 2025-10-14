#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ToolONWA VIP v1.0 - main
"""
import os, re, sys, json, threading
import tkinter as tk
import subprocess
from tkinter import ttk, filedialog, messagebox
from tkinter import font as tkfont
from tkinter.scrolledtext import ScrolledText
from screen.DB import edit_connection
from screen.DB import cmd_sql_plus

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
    except Exception:
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

        self.lang="VN"
        self.config = load_config()
        self.current_ora_path = self.config.get("ora_path") or DEFAULT_ORA_PATH
        self.lang = self.config.get("lang","VN")

        # state
        self.show_pwd = tk.BooleanVar(value=False)
        self.var_use_host_port = tk.BooleanVar(value=bool(self.config.get("use_host_port", False)))
        self._last_error = ""
        self.conn_blocks = {}

        self._setup_fonts()
        self._build_ui()
        self._center_on_screen()
        self._load_ora(self.current_ora_path)
        created = ensure_db_list_file()
        self._load_combobox_from_json()
        if created: self._set_status("Created configs/db_list.json", ok=False)

    def _setup_fonts(self):
        base = tkfont.nametofont("TkDefaultFont"); base.configure(size=10)
        try:
            if sys.platform.startswith("win") and os.path.isdir(FONTS_DIR):
                import ctypes; FR_PRIVATE=0x10
                for fn in os.listdir(FONTS_DIR):
                    if fn.lower().endswith((".ttf",".otf")):
                        ctypes.windll.gdi32.AddFontResourceExW(os.path.join(FONTS_DIR,fn), FR_PRIVATE,0)
        except Exception: pass
        style = ttk.Style()
        style.configure("TButton", padding=(10,6))
        style.configure("Status.TLabel", padding=(6,2))
        style.configure("Details.TButton", padding=(6,2))   # smaller details button

    def _build_ui(self):
        self.rowconfigure(0, weight=1); self.columnconfigure(0, weight=1)
        root=ttk.Frame(self, padding=8); root.grid(row=0,column=0,sticky="nsew"); root.columnconfigure(0, weight=1)

        self.db_group=ttk.LabelFrame(root, text=self._t("DB"), padding=(8,6), relief="ridge", borderwidth=2)
        self.db_group.grid(row=0,column=0,sticky="nsew",padx=2,pady=(2,8))
        self.db_group.columnconfigure(0, weight=1); self.db_group.columnconfigure(1, weight=0)

        connect=ttk.LabelFrame(self.db_group, text=self._t("Thiết Lập Kết Nối"), padding=8, relief="ridge", borderwidth=2)
        connect.grid(row=0,column=0,sticky="nsew",padx=(0,8),pady=(0,8))
        connect.columnconfigure(0, weight=1); connect.columnconfigure(1, weight=1); connect.columnconfigure(2, weight=0)

        self.cbo_conn=ttk.Combobox(connect, state="readonly")
        # combobox chiếm toàn bộ bề ngang của khối connect
        self.cbo_conn.grid(row=0,column=0,columnspan=3,sticky="ew",pady=(0,6))
        self.cbo_conn.bind("<<ComboboxSelected>>", self._on_pick_connection)

        ttk.Label(connect,text=self._t("User ID")).grid(row=1,column=0,sticky="w",pady=2,padx=(0,6))
        self.ent_user=ttk.Entry(connect); self.ent_user.grid(row=1,column=1,columnspan=2,sticky="ew",pady=2)

        ttk.Label(connect,text=self._t("Password")).grid(row=2,column=0,sticky="w",pady=2,padx=(0,6))
        self.ent_pass=ttk.Entry(connect, show="*"); self.ent_pass.grid(row=2,column=1,sticky="ew",pady=2)
        ttk.Checkbutton(connect, text=self._t("Hiện mật khẩu"), variable=self.show_pwd,
                        command=self._toggle_show_pwd).grid(row=2, column=2, sticky="w")

        ttk.Label(connect,text=self._t("Data Source")).grid(row=3,column=0,sticky="w",pady=2,padx=(0,6))
        self.ent_dsn=ttk.Entry(connect); self.ent_dsn.grid(row=3,column=1,columnspan=2,sticky="ew",pady=(2,0))

        ttk.Label(connect,text=self._t("Host/Port")).grid(row=4,column=0,sticky="w",pady=2,padx=(0,6))
        self.ent_host=ttk.Entry(connect); self.ent_host.grid(row=4,column=1,sticky="ew",pady=2,padx=(0,3))
        self.ent_port=ttk.Entry(connect,width=8); self.ent_port.grid(row=4,column=2,sticky="ew",pady=2,padx=(3,0))

        ttk.Checkbutton(connect, text=self._t("SQL Plus kèm host:port"),
                        variable=self.var_use_host_port,
                        command=self._on_toggle_hostport).grid(row=5, column=0, columnspan=3, sticky="w", pady=(4,0))

        right=ttk.Frame(self.db_group); right.grid(row=0,column=1,sticky="nsew",pady=(24,8))
        right.columnconfigure(0, weight=1); right.rowconfigure(0, weight=1)
        ttk.Frame(right).grid(row=0, column=0, sticky="ns")  # spacer
        self.btn_open_ora=ttk.Button(right,text=self._t("Open Ora File"),command=self._open_ora_dialog,width=18)
        self.btn_open_ora.grid(row=1,column=0,sticky="ew",pady=(6,6))
        self.btn_check=ttk.Button(right,text=self._t("Check Connection"),command=self._check_connection,width=18)
        self.btn_check.grid(row=2,column=0,sticky="ew")

        action=ttk.LabelFrame(self.db_group, text="Action", padding=8, relief="ridge", borderwidth=2)
        action.grid(row=1,column=0,columnspan=2,sticky="ew")
        for i in range(3): action.columnconfigure(i, weight=1)
        ttk.Button(action,text="Insert").grid(row=0,column=0,sticky="ew",padx=4,pady=4)
        ttk.Button(action,text="Update").grid(row=0,column=1,sticky="ew",padx=4,pady=4)
        ttk.Button(action,text="Backup/Restore").grid(row=0,column=2,sticky="ew",padx=4,pady=4)
        ttk.Button(action,text="SQL Plus", command=self._run_cmd_sqlplus).grid(row=1,column=0,sticky="ew",padx=4,pady=4)
        ttk.Button(action,text="Compare Data").grid(row=1,column=1,sticky="ew",padx=4,pady=4)
        ttk.Button(action,text="Edit Connection", command=self._edit_connection).grid(row=1,column=2,sticky="ew",padx=4,pady=4)

        mu=ttk.LabelFrame(root,text=self._t("MU"),padding=(8,6), relief="ridge", borderwidth=2)
        mu.grid(row=1,column=0,sticky="ew",padx=2,pady=(0,8))
        ttk.Button(mu,text=self._t("Read Log MU"), command=self._open_log_view_mu).grid(row=0,column=0,padx=4,pady=4,sticky="w")

        common=ttk.LabelFrame(root,text=self._t("Chung"),padding=(8,6), relief="ridge", borderwidth=2)
        common.grid(row=2,column=0,sticky="ew",padx=2,pady=(0,8))
        for i in range(3): common.columnconfigure(i, weight=1)
        ttk.Button(common,text=self._t("RDS information"),command=self._coming_soon).grid(row=0,column=0,padx=8,pady=4,sticky="ew")
        ttk.Button(common,text=self._t("Tài liệu"),command=self._coming_soon).grid(row=0,column=1,padx=8,pady=4,sticky="ew")
        ttk.Button(common,text=self._t("Bí kíp võ công"),command=self._coming_soon).grid(row=0,column=2,padx=8,pady=4,sticky="ew")

        bottom=ttk.Frame(root); bottom.grid(row=3,column=0,sticky="ew",pady=(4,0))
        bottom.columnconfigure(0, weight=1)

        self.lbl_status=ttk.Label(bottom,text=self._t("Chưa kết nối"),anchor="w",relief="sunken", style="Status.TLabel")
        self.lbl_status.grid(row=0,column=0,sticky="ew",padx=(0,6))

        # Details button small and hidden initially
        self.btn_details = ttk.Button(bottom, text=self._t("Chi tiết"), width=8, command=self._show_error_details, style="Details.TButton")
        self.btn_details.grid(row=0, column=1, sticky="e")

        ttk.Label(bottom,text=self._t("Ngôn Ngữ")).grid(row=0,column=2,sticky="e",padx=(8,4))
        self.cbo_lang=ttk.Combobox(bottom,state="readonly",width=6,values=["VN","JP"])
        self.cbo_lang.grid(row=0,column=3,sticky="e"); self.cbo_lang.set(self.lang)
        self.cbo_lang.bind("<<ComboboxSelected>>", self._on_change_lang)

    def _center_on_screen(self):
        self.update_idletasks()
        w,h=self.winfo_width(),self.winfo_height()
        x=(self.winfo_screenwidth()-w)//2; y=(self.winfo_screenheight()-h)//2
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _t(self,s):
        vi={"DB":"DB","Thiết Lập Kết Nối":"Thiết Lập Kết Nối","User ID":"User ID","Password":"Password","Data Source":"Data Source","Host/Port":"Host/Port","Open Ora File":"Open Ora File","Check Connection":"Check Connection","Insert":"Insert","Update":"Update","Backup/Restore":"Backup/Restore","SQL Plus":"SQL Plus","Compare Data":"Compare Data","Edit Connection":"Edit Connection","MU":"MU","Read Log MU":"Read Log MU","Chung":"Chung","RDS information":"RDS information","Tài liệu":"Tài liệu","Bí kíp võ công":"Bí kíp võ công","Chưa kết nối":"Chưa kết nối","Ngôn Ngữ":"Ngôn Ngữ","Chi tiết":"Chi tiết","Kết nối thất bại":"Kết nối thất bại","Kết nối thành công":"Kết nối thành công"}
        ja={"DB":"DB","Thiết Lập Kết Nối":"接続設定","User ID":"ユーザーID","Password":"パスワード","Data Source":"データソース","Host/Port":"ホスト/ポート","Open Ora File":"tnsnamesを開く","Check Connection":"接続チェック","Insert":"挿入","Update":"更新","Backup/Restore":"バックアップ/復元","SQL Plus":"SQL Plus","Compare Data":"データ比較","Edit Connection":"接続編集","MU":"MU","Read Log MU":"MUログ読込","Chung":"共通","RDS information":"RDS情報","Tài liệu":"ドキュメント","Bí kíp võ công":"Tips","Chưa kết nối":"未接続","Ngôn Ngữ":"言語","Chi tiết":"詳細","Kết nối thất bại":"接続失敗","Kết nối thành công":"接続成功"}
        return (vi if self.lang=="VN" else ja).get(s,s)

    def _apply_language(self):
        self.db_group.config(text=self._t("DB"))
        self.btn_open_ora.config(text=self._t("Open Ora File"))
        self.btn_check.config(text=self._t("Check Connection"))
        self.lbl_status.config(text=self._t("Chưa kết nối"))
        self.btn_details.config(text=self._t("Chi tiết"))

    def _on_change_lang(self,_): self.lang=self.cbo_lang.get(); self.config["lang"]=self.lang; save_config(self.config); self._apply_language()

    # ---------- data sources ----------
    def _open_ora_dialog(self):
        initdir=os.path.dirname(self.current_ora_path) if self.current_ora_path else BASE_DIR
        path=filedialog.askopenfilename(title=self._t("Open Ora File"), filetypes=[("tnsnames.ora","tnsnames.ora"),("All files","*.*")], initialdir=initdir)
        if path:
            self.current_ora_path=path; self.config["ora_path"]=path; save_config(self.config); self._load_ora(path); self._set_status("Loaded new tnsnames.ora", ok=False)

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
        except Exception as e:
            messagebox.showerror(APP_TITLE, f"Could not load tnsnames.ora:\n{e}")

    def _load_combobox_from_json(self):
        ensure_configs_dir()
        try:
            with open(DB_LIST_PATH,"r",encoding="utf-8") as f:
                data=json.load(f)
            items=[str(x) for x in data.get("items",[])]
        except Exception:
            items=[]
        self.cbo_conn["values"]=items
        if items:
            self.cbo_conn.set(items[0]); self._on_pick_connection()
        else:
            self._set_status("No items in configs/db_list.json", ok=False)

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
            messagebox.showwarning(APP_TITLE, "Thiếu thông tin kết nối."); return
        dsn = f"{host}:{port}/{data_src}" if (self.var_use_host_port.get() and host and port) else data_src

        loading = tk.Toplevel(self)
        loading.title("Checking...")
        loading.resizable(False, False)
        ttk.Label(loading, text="Checking connection...").grid(row=0, column=0, padx=12, pady=(12, 6))
        pb = ttk.Progressbar(loading, mode="indeterminate", length=220)
        pb.grid(row=1, column=0, padx=12, pady=(0, 12))
        pb.start(10)

        # chặn người dùng tự đóng cửa sổ trong khi đang check
        loading.protocol("WM_DELETE_WINDOW", lambda: None)

        loading.transient(self)
        loading.grab_set()
        loading.update_idletasks()
        x = self.winfo_rootx() + (self.winfo_width() - loading.winfo_width()) // 2
        y = self.winfo_rooty() + (self.winfo_height() - loading.winfo_height()) // 2
        loading.geometry(f"+{x}+{y}")

        result = {"ok": False, "msg": ""}
        _finished = {"v": False}  # guard chống gọi finish 2 lần

        def worker():
            try:
                try:
                    import oracledb as driver
                except Exception:
                    import cx_Oracle as driver  # type: ignore
                conn = driver.connect(user=user, password=pwd, dsn=dsn)
                conn.close()
                result["ok"] = True
            except Exception as e:
                result["msg"] = str(e)
            finally:
                self.after(0, finish)

        def finish():
            if _finished["v"]:
                return
            _finished["v"] = True
            # an toàn khi widget đã bị hủy
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
                self._set_status(self._t("Kết nối thành công"), ok=True)
                messagebox.showinfo(APP_TITLE, self._t("Kết nối thành công"))
            else:
                self._set_status(self._t("Kết nối thất bại"), ok=False, details=result["msg"])
                messagebox.showerror(APP_TITLE, f"{self._t('Kết nối thất bại')}: {result['msg'] or 'Không rõ lỗi.'}")

        threading.Thread(target=worker, daemon=True).start()


    def _set_status(self,text,ok=False,details:str|None=None):
        f=tkfont.nametofont("TkDefaultFont").copy(); f.configure(weight="normal")
        self.lbl_status.configure(text=text,font=f,foreground="black")
        self._last_error = details or ""

    def _on_toggle_hostport(self):
        self.config["use_host_port"] = bool(self.var_use_host_port.get())
        save_config(self.config)

    def _show_error_details(self):
        if not self._last_error:
            messagebox.showinfo(APP_TITLE, "Không có chi tiết lỗi."); return
        win = tk.Toplevel(self); win.title(self._t("Chi tiết")); win.resizable(False, False)
        w, h = 820, 420
        x = self.winfo_rootx() + (self.winfo_width() - w)//2
        y = self.winfo_rooty() + (self.winfo_height() - h)//2
        win.geometry(f"{w}x{h}+{x}+{y}")
        frm = ttk.Frame(win, padding=10); frm.pack(fill="both", expand=True)
        txt = ScrolledText(frm, wrap="word"); txt.pack(fill="both", expand=True)
        txt.configure(fg="black"); txt.insert("1.0", self._last_error); txt.config(state="disabled")
        ttk.Button(frm, text="Close", command=win.destroy).pack(anchor="e", pady=(8,0))

    def _coming_soon(self): messagebox.showinfo(APP_TITLE,"Coming soon.")
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
            messagebox.showwarning(APP_TITLE, "Thiếu thông tin kết nối."); return
        try:
            cmd_sql_plus.open_sqlplus(user, pwd, host, port, alias, self.var_use_host_port.get())
        except Exception as e:
            messagebox.showerror(APP_TITLE, f"Lỗi mở SQL*Plus: {e}")

    def _open_log_view_mu(self):
        # đường dẫn tới script
        script = resource_path(os.path.join("screen", "MU", "log_viewer.py"))
        if not os.path.isfile(script):
            messagebox.showerror(APP_TITLE, f"Không tìm thấy: {script}")
            return
        try:
            subprocess.Popen([sys.executable, script], shell=False, cwd=os.path.dirname(script))
        except Exception as e:
            messagebox.showerror(APP_TITLE, f"Lỗi mở log_viewer.py: {e}")

def main(): app=ToolVIP(); app.mainloop()
if __name__=="__main__": main()
