# -*- coding: utf-8 -*-
"""
Edit Connection dialog for Tool VIP
Requirements implemented:
- Load initial values from caller.
- "Check Connection" tests Oracle connectivity (oracledb or cx_Oracle).
- Add: append to configs/db_list.json and append new alias block to tnsnames.ora if missing.
- Edit: update selected item in db_list.json and update existing alias block in tnsnames.ora.
- If connection test fails, ask user to confirm saving anyway.
- Status area uses black, normal text; "Chi tiết" button always visible.
- This module exposes open_dialog(parent, initial, paths, tns_blocks) for use from main.py.
"""
from __future__ import annotations
import os, re, json, threading
import tkinter as tk
from tkinter import ttk, messagebox
from tkinter.scrolledtext import ScrolledText

# ---------- helpers reused from main ----------
_ALIAS_RE = re.compile(r"^\s*([A-Za-z0-9_.-]+)\s*=\s*\(", re.MULTILINE)

def parse_tnsnames_blocks(text: str):
    results = {}
    positions = [(m.group(1), m.start()) for m in _ALIAS_RE.finditer(text)]
    if not positions:
        return results
    positions.append(("#END#", len(text)))
    for i in range(len(positions)-1):
        alias, start = positions[i]
        _, end = positions[i+1]
        block = text[start:end].strip()
        results[alias] = block
    return results

def render_alias_block(alias: str, host: str, port: str, service: str) -> str:
    host = host.strip(); port = port.strip(); service = service.strip()
    return (f"{alias} =\n"
            f"  (DESCRIPTION =\n"
            f"    (ADDRESS_LIST =\n"
            f"      (ADDRESS = (PROTOCOL = TCP)(HOST = {host})(PORT = {port}))\n"
            f"    )\n"
            f"    (CONNECT_DATA =\n"
            f"      (SERVICE_NAME = {service})\n"
            f"    )\n"
            f"  )\n")

def upsert_alias_block(ora_path: str, alias: str, host: str, port: str, service: str):
    data = ""
    if os.path.isfile(ora_path):
        with open(ora_path, "r", encoding="utf-8", errors="ignore") as f:
            data = f.read()
    blocks = parse_tnsnames_blocks(data) if data else {}
    new_block = render_alias_block(alias, host, port, service)
    if alias in blocks:
        # replace existing block
        # find exact span to replace by rebuilding with markers
        parts = list(_ALIAS_RE.finditer(data))
        # identify start and end
        start_idx, end_idx = None, None
        for i, m in enumerate(parts):
            if m.group(1) == alias:
                start_idx = m.start()
                end_idx = parts[i+1].start() if i+1 < len(parts) else len(data)
                break
        if start_idx is None:
            # fallback: append
            data = data.rstrip() + "\n\n" + new_block
        else:
            data = data[:start_idx] + new_block + data[end_idx:]
    else:
        data = (data.rstrip() + "\n\n" + new_block) if data else new_block
    with open(ora_path, "w", encoding="utf-8") as f:
        f.write(data)

def next_index_for_items(items):
    mx = 0
    for s in items:
        m = re.match(r"^(\d+)\.", str(s).strip())
        if m:
            mx = max(mx, int(m.group(1)))
    return mx + 1

def format_display(user: str, pwd: str, alias: str, idx: int | None) -> str:
    core = f"{user}/{pwd}@{alias}"
    return f"{idx}.{core}" if idx is not None else core

# ---------- dialog ----------
class EditConnectionDialog(tk.Toplevel):
    def __init__(self, parent, initial: dict, paths: dict, tns_blocks: dict | None = None):
        super().__init__(parent)
        self.title("Cập nhật thông tin kết nối")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.parent = parent
        self.paths = paths
        self.tns_blocks = tns_blocks or {}
        self._last_error = ""

        # state
        self.var_user = tk.StringVar(value=initial.get("user",""))
        self.var_pwd  = tk.StringVar(value=initial.get("password",""))
        self.var_alias= tk.StringVar(value=initial.get("alias",""))
        self.var_host = tk.StringVar(value=initial.get("host",""))
        self.var_port = tk.StringVar(value=initial.get("port",""))
        self.current_display = initial.get("current_display")  # for edit mode

        self._build_ui()
        self._center(parent)

    def _build_ui(self):
        root = ttk.Frame(self, padding=8)
        root.grid(sticky="nsew")
        root.columnconfigure(0, weight=1)

        grp = ttk.LabelFrame(root, text="Thông tin kết nối", padding=8)
        grp.grid(sticky="ew")
        for i in range(3): grp.columnconfigure(i, weight=1 if i>0 else 0)

        ttk.Label(grp, text="User ID").grid(row=0, column=0, sticky="w", padx=(0,6), pady=2)
        e_user = ttk.Entry(grp, textvariable=self.var_user); e_user.grid(row=0, column=1, columnspan=2, sticky="ew", pady=2)

        ttk.Label(grp, text="Password").grid(row=1, column=0, sticky="w", padx=(0,6), pady=2)
        e_pwd = ttk.Entry(grp, textvariable=self.var_pwd, show="*"); e_pwd.grid(row=1, column=1, columnspan=2, sticky="ew", pady=2)

        ttk.Label(grp, text="Data Source").grid(row=2, column=0, sticky="w", padx=(0,6), pady=2)
        e_alias = ttk.Entry(grp, textvariable=self.var_alias); e_alias.grid(row=2, column=1, columnspan=2, sticky="ew", pady=2)

        ttk.Label(grp, text="Host/Port").grid(row=3, column=0, sticky="w", padx=(0,6), pady=2)
        e_host = ttk.Entry(grp, textvariable=self.var_host); e_host.grid(row=3, column=1, sticky="ew", pady=2, padx=(0,3))
        e_port = ttk.Entry(grp, textvariable=self.var_port, width=8); e_port.grid(row=3, column=2, sticky="ew", pady=2, padx=(3,0))

        btn_check = ttk.Button(grp, text="Check Connection", command=self._check_connection)
        btn_check.grid(row=4, column=0, columnspan=3, sticky="ew", pady=(6,2))

        bottom = ttk.Frame(grp); bottom.grid(row=5, column=0, columnspan=3, sticky="ew")
        bottom.columnconfigure(0, weight=1)
        self.lbl_status = ttk.Label(bottom, text="Chưa kết nối", anchor="w", relief="sunken")
        self.lbl_status.grid(row=0, column=0, sticky="ew", padx=(0,6), pady=(4,0))

        self.btn_details = ttk.Button(bottom, text="Chi tiết", width=8, command=self._show_error_details)
        self.btn_details.grid(row=0, column=1, sticky="e", pady=(4,0))

        # action row
        actions = ttk.Frame(root, padding=(0,8,0,0))
        actions.grid(sticky="ew")
        for i in range(3): actions.columnconfigure(i, weight=1)
        ttk.Button(actions, text="Add", command=self._on_add).grid(row=0, column=0, sticky="ew", padx=6)
        ttk.Button(actions, text="Edit", command=self._on_edit).grid(row=0, column=1, sticky="ew", padx=6)
        ttk.Button(actions, text="Cancel", command=self.destroy).grid(row=0, column=2, sticky="ew", padx=6)

    def _center(self, parent):
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        x = parent.winfo_rootx() + (parent.winfo_width() - w)//2
        y = parent.winfo_rooty() + (parent.winfo_height() - h)//2
        self.geometry(f"+{x}+{y}")

    # ----- actions -----
    def _dsn(self):
        host = self.var_host.get().strip()
        port = self.var_port.get().strip()
        alias = self.var_alias.get().strip()
        return f"{host}:{port}/{alias}" if host and port else alias

    def _check_connection(self) -> bool:
        user = self.var_user.get().strip()
        pwd  = self.var_pwd.get().strip()
        dsn  = self._dsn()
        if not (user and pwd and dsn):
            messagebox.showwarning("Tool VIP", "Thiếu thông tin kết nối."); 
            return False

        loading = tk.Toplevel(self); loading.title("Checking..."); loading.resizable(False, False)
        ttk.Label(loading, text="Checking connection...").grid(row=0,column=0,padx=12,pady=(12,6))
        pb=ttk.Progressbar(loading,mode="indeterminate",length=220); pb.grid(row=1,column=0,padx=12,pady=(0,12)); pb.start(10)
        loading.transient(self); loading.grab_set(); loading.update_idletasks()
        x=self.winfo_rootx()+(self.winfo_width()-loading.winfo_width())//2; y=self.winfo_rooty()+(self.winfo_height()-loading.winfo_height())//2
        loading.geometry(f"+{x}+{y}")

        result = {"ok": False, "msg": ""}
        def worker():
            try:
                try:
                    import oracledb as driver
                except Exception:
                    import cx_Oracle as driver  # type: ignore
                conn = driver.connect(user=user, password=pwd, dsn=dsn)
                conn.close(); result["ok"] = True
            except Exception as e:
                result["msg"] = str(e)
            finally:
                self.after(0, lambda: finish(result))
        def finish(res):
            pb.stop(); loading.destroy()
            if res["ok"]:
                self._set_status("Kết nối thành công")
            else:
                self._set_status("Kết nối thất bại", details=res["msg"])
        threading.Thread(target=worker, daemon=True).start()
        # No immediate boolean since async; return True to not block UI paths
        return True

    def _set_status(self, text, details: str | None = None):
        self.lbl_status.configure(text=text, foreground="black")
        self._last_error = details or ""

    def _ensure_configs(self):
        base = os.path.dirname(self.paths["config"])  # configs dir
        os.makedirs(base, exist_ok=True)
        if not os.path.isfile(self.paths["db_list"]):
            with open(self.paths["db_list"], "w", encoding="utf-8") as f:
                json.dump({"items": []}, f, indent=2, ensure_ascii=False)

    def _add_or_update_db_list(self, mode: str):
        self._ensure_configs()
        with open(self.paths["db_list"], "r", encoding="utf-8") as f:
            data = json.load(f)
        items = [str(x) for x in data.get("items", [])]

        alias = self.var_alias.get().strip()
        user  = self.var_user.get().strip()
        pwd   = self.var_pwd.get().strip()

        # build display
        if mode == "add":
            idx = 1
            for s in items:
                m = re.match(r"^(\d+)\.", s)
                if m:
                    idx = max(idx, int(m.group(1))+1)
            display = f"{idx}.{user}/{pwd}@{alias}"
            # prevent exact duplicate
            if any(s.endswith(f"{user}/{pwd}@{alias}") or s.split(".",1)[-1]==f"{user}/{pwd}@{alias}" for s in items):
                # already exists; do nothing
                pass
            else:
                items.append(display)
        else:  # edit
            # keep original index if possible
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
                # fallback: append
                items.append(display)

        data["items"] = items
        with open(self.paths["db_list"], "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _confirm_on_fail(self) -> bool:
        if not self._last_error:
            return True
        return messagebox.askyesno("Tool VIP", "Kết nối thất bại. Bạn có muốn lưu vẫn không?")

    def _on_add(self):
        # test connection first
        self._check_connection()
        self.after(400, self._finalize_add)

    def _finalize_add(self):
        if not self._confirm_on_fail():
            return
        # upsert tns alias if new
        alias = self.var_alias.get().strip()
        host  = self.var_host.get().strip()
        port  = self.var_port.get().strip()
        if alias and host and port:
            upsert_alias_block(self.paths["tnsnames"], alias, host, port, alias)
        # update db_list
        self._add_or_update_db_list("add")
        messagebox.showinfo("Tool VIP", "Đã lưu (Add).")
        self.destroy()

    def _on_edit(self):
        self._check_connection()
        self.after(400, self._finalize_edit)

    def _finalize_edit(self):
        if not self._confirm_on_fail():
            return
        alias = self.var_alias.get().strip()
        host  = self.var_host.get().strip()
        port  = self.var_port.get().strip()
        if alias and host and port:
            upsert_alias_block(self.paths["tnsnames"], alias, host, port, alias)
        self._add_or_update_db_list("edit")
        messagebox.showinfo("Tool VIP", "Đã lưu (Edit).")
        self.destroy()

    def _show_error_details(self):
        if not self._last_error:
            messagebox.showinfo("Tool VIP", "Không có chi tiết lỗi.")
            return
        win = tk.Toplevel(self); win.title("Chi tiết"); win.resizable(False, False)
        w, h = 720, 360
        x = self.winfo_rootx() + (self.winfo_width() - w)//2
        y = self.winfo_rooty() + (self.winfo_height() - h)//2
        win.geometry(f"{w}x{h}+{x}+{y}")
        frm = ttk.Frame(win, padding=10); frm.pack(fill="both", expand=True)
        txt = ScrolledText(frm, wrap="word"); txt.pack(fill="both", expand=True)
        txt.insert("1.0", self._last_error); txt.config(state="disabled")
        ttk.Button(frm, text="Close", command=win.destroy).pack(anchor="e", pady=(8,0))

def open_dialog(parent, initial: dict, paths: dict, tns_blocks: dict | None = None):
    """
    parent: Tk root or Toplevel
    initial: {'user','password','alias','host','port','current_display'}  # strings
    paths:   {'config': <configs/config.json>, 'db_list': <configs/db_list.json>, 'tnsnames': <ora/tnsnames.ora>}
    tns_blocks: optional existing tns dict for faster checks
    """
    dlg = EditConnectionDialog(parent, initial, paths, tns_blocks)
    parent.wait_window(dlg)
    return True
