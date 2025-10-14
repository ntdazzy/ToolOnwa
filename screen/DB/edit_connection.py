# -*- coding: utf-8 -*-
"""
screen/DB/edit_connection.py
"""
from __future__ import annotations
import os, re, json, threading
import tkinter as tk
from tkinter import ttk, messagebox
from tkinter.scrolledtext import ScrolledText

# ---------- helpers (TNS) ----------
_ALIAS_RE = re.compile(r"^\s*([A-Za-z0-9_.-]+)\s*=\s*\(", re.MULTILINE)

def parse_tnsnames_blocks(text: str) -> dict[str, str]:
    results = {}
    marks = [(m.group(1), m.start()) for m in _ALIAS_RE.finditer(text)]
    if not marks:
        return results
    marks.append(("#END#", len(text)))
    for i in range(len(marks) - 1):
        alias, start = marks[i]
        _, end = marks[i + 1]
        results[alias] = text[start:end].strip()
    return results

def render_alias_block(alias: str, host: str, port: str, service: str) -> str:
    host = host.strip(); port = port.strip(); service = service.strip()
    return (
        f"{alias} =\n"
        f"  (DESCRIPTION =\n"
        f"    (ADDRESS_LIST =\n"
        f"      (ADDRESS = (PROTOCOL = TCP)(HOST = {host})(PORT = {port}))\n"
        f"    )\n"
        f"    (CONNECT_DATA =\n"
        f"      (SERVICE_NAME = {service})\n"
        f"    )\n"
        f"  )\n"
    )

def upsert_alias_block(ora_path: str, alias: str, host: str, port: str, service: str) -> None:
    data = ""
    if os.path.isfile(ora_path):
        with open(ora_path, "r", encoding="utf-8", errors="ignore") as f:
            data = f.read()
    blocks = parse_tnsnames_blocks(data) if data else {}
    new_block = render_alias_block(alias, host, port, service)

    if data and alias in blocks:
        parts = list(_ALIAS_RE.finditer(data))
        start_idx, end_idx = None, None
        for i, m in enumerate(parts):
            if m.group(1) == alias:
                start_idx = m.start()
                end_idx = parts[i+1].start() if i+1 < len(parts) else len(data)
                break
        if start_idx is None:
            data = data.rstrip() + "\n\n" + new_block
        else:
            data = data[:start_idx] + new_block + data[end_idx:]
    else:
        data = (data.rstrip() + "\n\n" + new_block) if data else new_block

    # đảm bảo thư mục tồn tại
    os.makedirs(os.path.dirname(ora_path) or ".", exist_ok=True)
    with open(ora_path, "w", encoding="utf-8") as f:
        f.write(data)

# ---------- dialog ----------
class EditConnectionDialog(tk.Toplevel):
    def __init__(self, parent, initial: dict, paths: dict, tns_blocks: dict | None = None):
        super().__init__(parent)
        self.title("Cập nhật thông tin kết nối")
        self.resizable(False, False)
        self.transient(parent); self.grab_set()

        self.parent = parent
        self.paths = paths                               # {'config','db_list','tnsnames'}
        self.tns_blocks = tns_blocks or {}
        self._last_error = ""

        # state
        self.var_user    = tk.StringVar(value=initial.get("user",""))
        self.var_pwd     = tk.StringVar(value=initial.get("password",""))
        self.var_alias   = tk.StringVar(value=initial.get("alias",""))
        self.var_service = tk.StringVar(value=initial.get("service",""))  # nếu rỗng sẽ fallback alias
        self.var_host    = tk.StringVar(value=initial.get("host",""))
        self.var_port    = tk.StringVar(value=initial.get("port",""))
        self.var_use_hostport = tk.BooleanVar(value=True)                 # bật dùng host:port
        self.current_display = initial.get("current_display")             # cho mode edit

        self._build_ui()
        self._center(parent)

    # ---------- UI ----------
    def _build_ui(self):
        root = ttk.Frame(self, padding=8); root.grid(sticky="nsew")
        root.columnconfigure(0, weight=1)

        grp = ttk.LabelFrame(root, text="Thông tin kết nối", padding=8)
        grp.grid(sticky="ew")
        for i in range(3): grp.columnconfigure(i, weight=1 if i>0 else 0)

        ttk.Label(grp, text="User").grid(row=0, column=0, sticky="w", padx=(0,6), pady=2)
        ttk.Entry(grp, textvariable=self.var_user).grid(row=0, column=1, columnspan=2, sticky="ew", pady=2)

        ttk.Label(grp, text="Password").grid(row=1, column=0, sticky="w", padx=(0,6), pady=2)
        self._ent_pwd = ttk.Entry(grp, textvariable=self.var_pwd, show="*")
        self._ent_pwd.grid(row=1, column=1, sticky="ew", pady=2)
        self._show_pwd = tk.BooleanVar(value=False)
        ttk.Checkbutton(grp, text="Hiện mật khẩu", variable=self._show_pwd,
                        command=lambda: self._ent_pwd.configure(show="" if self._show_pwd.get() else "*")).grid(row=1, column=2, sticky="w")

        ttk.Label(grp, text="Alias").grid(row=2, column=0, sticky="w", padx=(0,6), pady=2)
        ttk.Entry(grp, textvariable=self.var_alias).grid(row=2, column=1, columnspan=2, sticky="ew", pady=2)

        # ttk.Label(grp, text="Service Name").grid(row=3, column=0, sticky="w", padx=(0,6), pady=2)
        # ttk.Entry(grp, textvariable=self.var_service).grid(row=3, column=1, columnspan=2, sticky="ew", pady=2)

        ttk.Label(grp, text="Host/Port").grid(row=4, column=0, sticky="w", padx=(0,6), pady=2)
        ttk.Entry(grp, textvariable=self.var_host).grid(row=4, column=1, sticky="ew", pady=2, padx=(0,3))
        ttk.Entry(grp, textvariable=self.var_port, width=8).grid(row=4, column=2, sticky="ew", pady=2, padx=(3,0))

        # ttk.Checkbutton(grp, text="Dùng host:port khi kết nối", variable=self.var_use_hostport)\
            # .grid(row=5, column=0, columnspan=3, sticky="w", pady=(4,0))

        ttk.Button(grp, text="Check Connection", command=self._check_connection)\
            .grid(row=6, column=0, columnspan=3, sticky="ew", pady=(6,2))

        bottom = ttk.Frame(grp); bottom.grid(row=7, column=0, columnspan=3, sticky="ew")
        bottom.columnconfigure(0, weight=1)
        self.lbl_status = ttk.Label(bottom, text="Chưa kết nối", anchor="w", relief="sunken")
        self.lbl_status.grid(row=0, column=0, sticky="ew", padx=(0,6), pady=(4,0))
        ttk.Button(bottom, text="Chi tiết", command=self._show_error_details, width=8).grid(row=0, column=1, sticky="e", pady=(4,0))

        actions = ttk.Frame(root, padding=(0,8,0,0)); actions.grid(sticky="ew")
        for i in range(3): actions.columnconfigure(i, weight=1)
        ttk.Button(actions, text="Add", command=self._on_add).grid(row=0, column=0, sticky="ew", padx=6)
        ttk.Button(actions, text="Edit", command=self._on_edit).grid(row=0, column=1, sticky="ew", padx=6)
        ttk.Button(actions, text="Cancel", command=self.destroy).grid(row=0, column=2, sticky="ew", padx=6)

    # ---------- utils ----------
    def _center(self, parent):
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        x = parent.winfo_rootx() + (parent.winfo_width() - w)//2
        y = parent.winfo_rooty() + (parent.winfo_height() - h)//2
        self.geometry(f"+{x}+{y}")

    def _show_error_details(self):
        if not self._last_error:
            messagebox.showinfo("Tool VIP", "Không có chi tiết lỗi.")
            return
        win = tk.Toplevel(self); win.title("Chi tiết"); win.resizable(False, False)
        st = ScrolledText(win, wrap="word", width=80, height=18); st.grid(row=0, column=0, padx=10, pady=10)
        st.insert("1.0", self._last_error); st.configure(state="disabled")
        ttk.Button(win, text="Close", command=win.destroy).grid(row=1, column=0, sticky="e", padx=10, pady=(0,10))

    def _set_status(self, text: str, details: str | None = None):
        self.lbl_status.configure(text=text)
        self._last_error = details or ""

    def _dsn(self) -> str:
        host = self.var_host.get().strip()
        port = self.var_port.get().strip()
        alias = self.var_alias.get().strip()
        service = (self.var_service.get().strip() or alias)
        if self.var_use_hostport.get() and host and port and service:
            return f"{host}:{port}/{service}"
        # fallback
        return service or alias

    # ---------- actions ----------
    def _check_connection(self):
        user = self.var_user.get().strip()
        pwd  = self.var_pwd.get().strip()
        dsn  = self._dsn()
        if not (user and pwd and dsn):
            messagebox.showwarning("Tool VIP", "Thiếu thông tin kết nối.")
            return

        loading = tk.Toplevel(self); loading.title("Checking..."); loading.resizable(False, False)
        ttk.Label(loading, text="Checking connection...").grid(row=0, column=0, padx=12, pady=(12,6))
        pb = ttk.Progressbar(loading, mode="indeterminate", length=220); pb.grid(row=1, column=0, padx=12, pady=(0,12)); pb.start(10)
        loading.transient(self); loading.grab_set(); loading.update_idletasks()
        x = self.winfo_rootx() + (self.winfo_width() - loading.winfo_width())//2
        y = self.winfo_rooty() + (self.winfo_height() - loading.winfo_height())//2
        loading.geometry(f"+{x}+{y}")

        result = {"ok": False, "msg": ""}

        def worker():
            try:
                driver = None
                missing = []
                try:
                    import oracledb as driver  # preferred
                except Exception as e1:
                    missing.append(f"oracledb: {e1}")
                    try:
                        import cx_Oracle as driver  # fallback
                    except Exception as e2:
                        missing.append(f"cx_Oracle: {e2}")
                if driver is None:
                    result["msg"] = (
                        "Driver not found. Cài 1 trong 2:\n"
                        "  pip install oracledb\n"
                        "hoặc:\n"
                        "  pip install cx_Oracle"
                    )
                    return
                conn = driver.connect(user=user, password=pwd, dsn=dsn)
                conn.close()
                result["ok"] = True
            except Exception as e:
                result["msg"] = str(e)
            finally:
                self.after(0, lambda: finish(result))

        def finish(res):
            pb.stop(); loading.destroy()
            if res["ok"]:
                self._set_status("Kết nối thành công")
                messagebox.showinfo("Tool VIP", "Kết nối thành công")
            else:
                self._set_status("Kết nối thất bại", details=res["msg"])
                messagebox.showerror("Tool VIP", f"Kết nối thất bại:\n{res['msg'] or 'Không rõ lỗi.'}")

        threading.Thread(target=worker, daemon=True).start()

    def _add_or_update_db_list(self, mode: str):
        # đọc file db_list
        data = {}
        try:
            with open(self.paths["db_list"], "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}
        items = [str(x) for x in data.get("items", [])]

        user = self.var_user.get().strip()
        pwd  = self.var_pwd.get().strip()
        alias= self.var_alias.get().strip()
        # build display
        if mode == "add":
            idx = 1
            for s in items:
                m = re.match(r"^(\d+)\.", s)
                if m:
                    idx = max(idx, int(m.group(1))+1)
            display = f"{idx}.{user}/{pwd}@{alias}"
            if any(s.endswith(f"{user}/{pwd}@{alias}") or s.split(".",1)[-1]==f"{user}/{pwd}@{alias}" for s in items):
                pass
            else:
                items.append(display)
        else:
            old = self.current_display or ""
            m = re.match(r"^(\d+)\.", old.strip())
            idx_str = m.group(1) if m else None
            display = f"{idx_str}.{user}/{pwd}@{alias}" if idx_str else f"{user}/{pwd}@{alias}"
            replaced = False
            for i, s in enumerate(items):
                if s == old:
                    items[i] = display
                    replaced = True
                    break
            if not replaced:
                items.append(display)

        data["items"] = items
        os.makedirs(os.path.dirname(self.paths["db_list"]) or ".", exist_ok=True)
        with open(self.paths["db_list"], "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _on_add(self):
        self._check_connection()
        self.after(400, self._finalize_add)

    def _finalize_add(self):
        if self._last_error and not messagebox.askyesno("Tool VIP", "Kết nối thất bại. Vẫn lưu?"):
            return
        alias   = self.var_alias.get().strip()
        service = (self.var_service.get().strip() or alias)
        host    = self.var_host.get().strip()
        port    = self.var_port.get().strip()
        if alias and host and port and service:
            try:
                upsert_alias_block(self.paths["tnsnames"], alias, host, port, service)
            except Exception as e:
                messagebox.showwarning("Tool VIP", f"Lỗi ghi tnsnames.ora:\n{e}")
        self._add_or_update_db_list("add")
        messagebox.showinfo("Tool VIP", "Đã lưu")
        self.destroy()

    def _on_edit(self):
        self._check_connection()
        self.after(400, self._finalize_edit)

    def _finalize_edit(self):
        if self._last_error and not messagebox.askyesno("Tool VIP", "Kết nối thất bại. Vẫn lưu?"):
            return
        alias   = self.var_alias.get().strip()
        service = (self.var_service.get().strip() or alias)
        host    = self.var_host.get().strip()
        port    = self.var_port.get().strip()
        if alias and host and port and service:
            try:
                upsert_alias_block(self.paths["tnsnames"], alias, host, port, service)
            except Exception as e:
                messagebox.showwarning("Tool VIP", f"Lỗi ghi tnsnames.ora:\n{e}")
        self._add_or_update_db_list("edit")
        messagebox.showinfo("Tool VIP", "Đã lưu")
        self.destroy()

def open_dialog(parent, initial: dict, paths: dict, tns_blocks: dict | None = None):
    """
    parent: Tk root/Toplevel
    initial: {'user','password','alias','service','host','port','current_display'}
    paths:   {'config':..., 'db_list':..., 'tnsnames':...}
    """
    dlg = EditConnectionDialog(parent, initial, paths, tns_blocks)
    parent.wait_window(dlg)
    return True
