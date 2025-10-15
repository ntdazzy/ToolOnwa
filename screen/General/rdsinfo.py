# connect_rds_gui.py
# RDS Quick Connect - robust credential + fallback .rdp
# Windows only. Password stored plaintext in rds_hosts.json.
import os
import json
import tempfile
import threading
import subprocess
import time
import socket
import ssl
import hashlib
import winreg
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

DATA_FILE = os.path.join(os.path.dirname(__file__), "rds_hosts.json")
DEFAULT_TIMEOUT = 600  # seconds

# -----------------------------
# I/O hosts
# -----------------------------
def load_hosts():
    if not os.path.exists(DATA_FILE):
        return []
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def save_hosts(hosts):
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(hosts, f, ensure_ascii=False, indent=2)
    except Exception as e:
        messagebox.showerror("Error", f"Save hosts failed: {e}")

# -----------------------------
# cmdkey helpers
# -----------------------------
def _cmdkey_path():
    windir = os.environ.get("WINDIR", r"C:\Windows")
    sysnative = os.path.join(windir, "Sysnative", "cmdkey.exe")
    system32 = os.path.join(windir, "System32", "cmdkey.exe")
    return sysnative if os.path.exists(sysnative) else system32

def _user_variants(host, user):
    u0 = user.strip()
    u1 = u0.replace(".\\", "").strip()
    return [u0, u1, f"{host}\\{u1}"]

def _cmdkey_add_try(target, user, password):
    exe = _cmdkey_path()
    try:
        proc = subprocess.run([exe, f"/add:{target}", f"/user:{user}", f"/pass:{password}"],
                              capture_output=True, text=True)
        return proc.returncode, (proc.stderr.strip() or proc.stdout.strip())
    except Exception as e:
        return 1, str(e)

def _cmdkey_delete(target):
    exe = _cmdkey_path()
    try:
        subprocess.run([exe, f"/delete:{target}"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass

# -----------------------------
# trust RDP cert to avoid "Unknown publisher"
# -----------------------------
def _ensure_rdp_trust(host):
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((host, 3389), timeout=5) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                der = ssock.getpeercert(binary_form=True)
        thumb = hashlib.sha1(der).digest()
        key_path = rf"Software\Microsoft\Terminal Server Client\Servers\{host}"
        key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path)
        winreg.SetValueEx(key, "CertHash", 0, winreg.REG_BINARY, thumb)
        winreg.CloseKey(key)
        return True
    except Exception:
        return False

# -----------------------------
# attempt resolve hostname from IP
# -----------------------------
def _resolve_hostname_if_any(host):
    try:
        # if host is IP try reverse lookup
        if all(c.isdigit() or c=='.' for c in host):
            name, _, _ = socket.gethostbyaddr(host)
            return name
    except Exception:
        pass
    return None

def _target_variants(host):
    variants = [f"TERMSRV/{host}"]
    hn = _resolve_hostname_if_any(host)
    if hn:
        variants.append(f"TERMSRV/{hn}")
    return variants

# -----------------------------
# Add/Edit dialog
# -----------------------------
class AddDialog(simpledialog.Dialog):
    def __init__(self, parent, title=None, initial=None):
        self.initial = initial or {}
        super().__init__(parent, title)

    def body(self, master):
        tk.Label(master, text="Display name").grid(row=0, column=0, sticky="e")
        tk.Label(master, text="Host/IP").grid(row=1, column=0, sticky="e")
        tk.Label(master, text="Username").grid(row=2, column=0, sticky="e")
        tk.Label(master, text="Password").grid(row=3, column=0, sticky="e")
        tk.Label(master, text="Subsystem").grid(row=4, column=0, sticky="e")

        self.e_name = tk.Entry(master)
        self.e_host = tk.Entry(master)
        self.e_user = tk.Entry(master)
        self.e_pass = tk.Entry(master, show="*")
        self.e_sub = tk.Entry(master)

        self.e_name.grid(row=0, column=1, padx=6, pady=2)
        self.e_host.grid(row=1, column=1, padx=6, pady=2)
        self.e_user.grid(row=2, column=1, padx=6, pady=2)
        self.e_pass.grid(row=3, column=1, padx=6, pady=2)
        self.e_sub.grid(row=4, column=1, padx=6, pady=2)

        self.e_name.insert(0, self.initial.get("name", ""))
        self.e_host.insert(0, self.initial.get("host", ""))
        self.e_user.insert(0, self.initial.get("user", ""))
        self.e_pass.insert(0, self.initial.get("pass", ""))
        self.e_sub.insert(0, self.initial.get("subsystem", ""))
        return self.e_name

    def apply(self):
        self.result = {
            "name": self.e_name.get().strip() or self.e_host.get().strip(),
            "host": self.e_host.get().strip(),
            "user": self.e_user.get().strip(),
            "pass": self.e_pass.get().strip(),
            "subsystem": self.e_sub.get().strip(),
        }

# -----------------------------
# Main app
# -----------------------------
class App:
    def __init__(self, root):
        self.root = root
        root.title("RDS Quick Connect")
        self.hosts = load_hosts()
        self.build_ui()
        self.refresh_lists()

    def build_ui(self):
        frm = ttk.Frame(self.root, padding=8)
        frm.pack(fill="both", expand=True)

        left = ttk.Frame(frm); right = ttk.Frame(frm)
        left.pack(side="left", fill="y", padx=(0,8))
        right.pack(side="left", fill="both", expand=True)

        ttk.Label(left, text="Choose Subsystem").pack(anchor="w")
        self.lb_sub = tk.Listbox(left, height=8, exportselection=False)
        self.lb_sub.pack(fill="y")
        self.lb_sub.bind("<<ListboxSelect>>", lambda e: self.on_sub_select())

        btns = ttk.Frame(left); btns.pack(pady=6)
        ttk.Button(btns, text="Add", command=self.on_add).pack(side="left", padx=4)
        ttk.Button(btns, text="Remove", command=self.on_remove).pack(side="left", padx=4)

        ttk.Label(right, text="Hosts for selected subsystem").pack(anchor="w")
        self.lb_hosts = tk.Listbox(right, height=12, exportselection=False)
        self.lb_hosts.pack(fill="both", expand=True)

        rbtn = ttk.Frame(right); rbtn.pack(fill="x", pady=6)
        ttk.Button(rbtn, text="Connect (OK)", command=self.on_connect).pack(side="left", padx=4)
        ttk.Button(rbtn, text="Edit", command=self.on_edit).pack(side="left", padx=4)

    def refresh_lists(self):
        self.hosts = load_hosts()
        subs = sorted({h.get("subsystem","") for h in self.hosts if h.get("subsystem")})
        self.lb_sub.delete(0,"end")
        for s in subs: self.lb_sub.insert("end", s)
        if subs:
            self.lb_sub.selection_set(0)
            self.on_sub_select()
        else:
            self.lb_hosts.delete(0,"end")

    def on_sub_select(self):
        sel = self.lb_sub.curselection()
        if not sel: return
        subs = self.lb_sub.get(sel[0])
        filtered = [h for h in self.hosts if h.get("subsystem")==subs]
        self.lb_hosts.delete(0,"end")
        for h in filtered:
            self.lb_hosts.insert("end", f"{h.get('name')} ({h.get('host')})")

    def on_add(self):
        dlg = AddDialog(self.root, title="Add RDS entry")
        if getattr(dlg, "result", None):
            e = dlg.result
            if not e["host"] or not e["user"]:
                messagebox.showerror("Error", "Host and Username are required")
                return
            self.hosts.append(e)
            save_hosts(self.hosts)
            self.refresh_lists()

    def on_remove(self):
        s = self.lb_sub.curselection(); h = self.lb_hosts.curselection()
        if not s or not h: return
        subs = self.lb_sub.get(s[0])
        f = [x for x in self.hosts if x.get("subsystem")==subs]
        rm = f[h[0]]
        if messagebox.askyesno("Confirm", f"Remove {rm.get('name')}?"):
            self.hosts.remove(rm)
            save_hosts(self.hosts)
            self.refresh_lists()

    def on_edit(self):
        s = self.lb_sub.curselection(); h = self.lb_hosts.curselection()
        if not s or not h: return
        subs = self.lb_sub.get(s[0])
        f = [x for x in self.hosts if x.get("subsystem")==subs]
        target = f[h[0]]
        dlg = AddDialog(self.root, title="Edit RDS entry", initial=target)
        if getattr(dlg, "result", None):
            new = dlg.result
            idx = self.hosts.index(target)
            self.hosts[idx] = new
            save_hosts(self.hosts)
            self.refresh_lists()

    def on_connect(self):
        s = self.lb_sub.curselection(); h = self.lb_hosts.curselection()
        if not s or not h:
            messagebox.showinfo("Info", "Please choose subsystem and host")
            return
        subs = self.lb_sub.get(s[0])
        f = [x for x in self.hosts if x.get("subsystem")==subs]
        target = f[h[0]]
        threading.Thread(target=self.connect_and_launch, args=(target,), daemon=True).start()

    # -----------------------------
    # connect flow: try targets, user variants, rdp fallback
    # -----------------------------
    def connect_and_launch(self, entry):
        host = entry.get("host")
        user_in = entry.get("user")
        pw = entry.get("pass", "")
        if not host or not user_in:
            messagebox.showerror("Error", "Host or user missing")
            return

        # attempt seed cert trust (best-effort)
        try:
            _ensure_rdp_trust(host)
        except Exception:
            pass

        # build target list
        targets = _target_variants(host)  # e.g. TERMSRV/IP and maybe TERMSRV/hostname
        used_user = None
        used_target = None
        last_msg = ""

        # try all combinations
        for tgt in targets:
            for u in _user_variants(host, user_in):
                rc, msg = _cmdkey_add_try(tgt, u, pw)
                if rc == 0:
                    used_user = u
                    used_target = tgt
                    break
                last_msg = f"{tgt} | {u} -> {msg}"
            if used_user:
                break

        if not used_user:
            messagebox.showerror("Error", f"Failed to add credential:\n{last_msg}")
            return

        # prepare two rdp variants: CredSSP ON (recommended), then fallback OFF
        rdp_variants = []
        rdp_variants.append("\n".join([
            f"full address:s:{host}",
            "prompt for credentials:i:0",
            f"username:s:{used_user}",
            "authentication level:i:2",
            "enablecredsspsupport:i:1",
        ]))
        rdp_variants.append("\n".join([
            f"full address:s:{host}",
            "prompt for credentials:i:0",
            f"username:s:{used_user}",
            "authentication level:i:0",
            "enablecredsspsupport:i:0",
            "negotiate security layer:i:0",
        ]))

        launched = False
        tf_name = None
        for rdp_text in rdp_variants:
            tf = tempfile.NamedTemporaryFile(delete=False, suffix=".rdp", mode="w", encoding="ascii")
            tf.write(rdp_text)
            tf.close()
            try:
                subprocess.Popen(["mstsc.exe", tf.name])
                launched = True
                tf_name = tf.name
                break
            except Exception:
                try:
                    os.unlink(tf.name)
                except Exception:
                    pass
                continue

        if not launched:
            # cleanup credential(s) we added
            for tgt in targets:
                _cmdkey_delete(tgt)
            messagebox.showerror("Error", "Failed to start mstsc.")
            return

        # wait for mstsc to exit or timeout then cleanup
        start = time.time()
        while time.time() - start < DEFAULT_TIMEOUT:
            time.sleep(1)
            try:
                out = subprocess.check_output(['tasklist','/FI','IMAGENAME eq mstsc.exe','/FO','CSV'],
                                              encoding='cp1252', errors='ignore')
                # header + rows; if only header then no mstsc running
                if out.strip().count('mstsc.exe') <= 1:
                    break
            except Exception:
                break

        # delete credentials for all targets we attempted
        for tgt in targets:
            _cmdkey_delete(tgt)
        # delete rdp file
        try:
            if tf_name:
                os.unlink(tf_name)
        except Exception:
            pass

# -----------------------------
# run
# -----------------------------
if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.geometry("300x360")
    root.mainloop()
