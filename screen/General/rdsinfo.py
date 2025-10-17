"""
Màn hình quản lý RDS: xem, chỉnh sửa và copy thông tin kết nối đã lưu.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable, Dict, List, Optional

import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from core import i18n

APP_TITLE_KEY = "common.app_title"
MODULE_DIR = Path(__file__).resolve().parent
ROOT_DIR = MODULE_DIR.parent.parent
DATA_FILE = MODULE_DIR / "rds_hosts.json"
ICON_PATH = ROOT_DIR / "icons" / "logo.ico"


def load_hosts() -> List[Dict[str, str]]:
    """Đọc danh sách host đã lưu từ rds_hosts.json."""
    if not DATA_FILE.exists():
        return []
    try:
        with DATA_FILE.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, list):
            return data
    except Exception:
        pass
    return []


def save_hosts(hosts: List[Dict[str, str]]) -> None:
    """Lưu danh sách host trở lại file JSON."""
    try:
        with DATA_FILE.open("w", encoding="utf-8") as fh:
            json.dump(hosts, fh, ensure_ascii=False, indent=2)
    except Exception as exc:
        messagebox.showerror(
            i18n.translate(APP_TITLE_KEY),
            i18n.translate("rds.msg.save_error", error=str(exc)),
        )


class AddDialog(simpledialog.Dialog):
    """Dialog thêm/sửa cấu hình RDS."""

    def __init__(self, parent: tk.Misc, initial: Optional[Dict[str, str]] = None):
        """Khởi tạo dialog với dữ liệu ban đầu nếu có."""
        self.initial = initial or {}
        super().__init__(parent, title=i18n.translate("rds.btn.edit" if initial else "rds.btn.add"))

    def body(self, master: tk.Misc) -> Optional[tk.Widget]:
        """Tạo form nhập liệu cho dialog."""
        ttk.Label(master, text=i18n.translate("rds.field.display_name")).grid(row=0, column=0, sticky="e", padx=4, pady=2)
        ttk.Label(master, text=i18n.translate("rds.field.host")).grid(row=1, column=0, sticky="e", padx=4, pady=2)
        ttk.Label(master, text=i18n.translate("rds.field.username")).grid(row=2, column=0, sticky="e", padx=4, pady=2)
        ttk.Label(master, text=i18n.translate("rds.field.password")).grid(row=3, column=0, sticky="e", padx=4, pady=2)
        ttk.Label(master, text=i18n.translate("rds.field.subsystem")).grid(row=4, column=0, sticky="e", padx=4, pady=2)

        self.var_display = tk.StringVar(value=self.initial.get("display", ""))
        self.var_host = tk.StringVar(value=self.initial.get("host", ""))
        self.var_user = tk.StringVar(value=self.initial.get("user", ""))
        self.var_pass = tk.StringVar(value=self.initial.get("pass", ""))
        self.var_sub = tk.StringVar(value=self.initial.get("subsystem", ""))

        ttk.Entry(master, textvariable=self.var_display).grid(row=0, column=1, sticky="ew", padx=6, pady=2)
        ttk.Entry(master, textvariable=self.var_host).grid(row=1, column=1, sticky="ew", padx=6, pady=2)
        ttk.Entry(master, textvariable=self.var_user).grid(row=2, column=1, sticky="ew", padx=6, pady=2)
        ttk.Entry(master, textvariable=self.var_pass, show="*").grid(row=3, column=1, sticky="ew", padx=6, pady=2)
        ttk.Entry(master, textvariable=self.var_sub).grid(row=4, column=1, sticky="ew", padx=6, pady=2)

        master.columnconfigure(1, weight=1)
        return None

    def validate(self) -> bool:
        """Kiểm tra dữ liệu bắt buộc."""
        if not self.var_host.get().strip() or not self.var_user.get().strip():
            messagebox.showwarning(
                i18n.translate(APP_TITLE_KEY),
                i18n.translate("rds.msg.missing_fields"),
            )
            return False
        return True

    def apply(self) -> None:
        """Trả về dữ liệu người dùng đã nhập."""
        self.result = {
            "display": self.var_display.get().strip(),
            "host": self.var_host.get().strip(),
            "user": self.var_user.get().strip(),
            "pass": self.var_pass.get(),
            "subsystem": self.var_sub.get().strip(),
        }


class HostDetailWindow(tk.Toplevel):
    """Cửa sổ hiển thị chi tiết thông tin của một host RDS."""

    def __init__(
        self,
        parent: tk.Misc,
        data: Dict[str, str],
        on_edit: Callable[[Dict[str, str]], None],
    ):
        """Tạo cửa sổ chi tiết cho bản ghi RDS cụ thể."""
        super().__init__(parent)
        self.data = data
        self._on_edit = on_edit

        self._lang_listener = self._handle_language_change
        i18n.add_listener(self._lang_listener)

        self.title(i18n.translate("rds.detail.title"))
        self.geometry("410x250")
        self.resizable(False, False)
        self._set_icon()

        container = ttk.Frame(self, padding=10)
        container.pack(fill="both", expand=True)
        container.columnconfigure(0, weight=1, minsize=140)
        container.columnconfigure(1, weight=1, minsize=160)

        self.lbl_display = ttk.Label(container)
        self.lbl_host = ttk.Label(container)
        self.lbl_user = ttk.Label(container)
        self.lbl_pass = ttk.Label(container)
        self.lbl_sub = ttk.Label(container)

        self.lbl_display.grid(row=0, column=0, sticky="w", pady=2)
        self.lbl_host.grid(row=1, column=0, sticky="w", pady=2)
        self.lbl_user.grid(row=2, column=0, sticky="w", pady=2)
        self.lbl_pass.grid(row=3, column=0, sticky="w", pady=2)
        self.lbl_sub.grid(row=4, column=0, sticky="w", pady=2)

        self.val_display = ttk.Label(container, anchor="w")
        self.val_host = ttk.Label(container, anchor="w")
        self.val_user = ttk.Label(container, anchor="w")
        self.val_pass = ttk.Label(container, anchor="w")
        self.val_sub = ttk.Label(container, anchor="w")

        self.val_display.grid(row=0, column=1, sticky="w")
        self.val_host.grid(row=1, column=1, sticky="w")
        self.val_user.grid(row=2, column=1, sticky="w")
        self.val_pass.grid(row=3, column=1, sticky="w")
        self.val_sub.grid(row=4, column=1, sticky="w")

        btn_frame = ttk.Frame(container)
        btn_frame.grid(row=5, column=0, columnspan=2, pady=(10, 0), sticky="ew")
        for col in range(3):
            btn_frame.columnconfigure(col, weight=1, minsize=110)

        self.btn_copy_host = ttk.Button(btn_frame, command=lambda: self._copy_to_clipboard("host"), width=14)
        self.btn_copy_user = ttk.Button(btn_frame, command=lambda: self._copy_to_clipboard("user"), width=14)
        self.btn_copy_pass = ttk.Button(btn_frame, command=lambda: self._copy_to_clipboard("pass"), width=14)
        self.btn_edit = ttk.Button(btn_frame, command=self._edit, width=18)

        self.btn_copy_host.grid(row=0, column=0, padx=4, pady=2, sticky="ew")
        self.btn_copy_user.grid(row=0, column=1, padx=4, pady=2, sticky="ew")
        self.btn_copy_pass.grid(row=0, column=2, padx=4, pady=2, sticky="ew")
        self.btn_edit.grid(row=1, column=0, columnspan=3, pady=(10, 0), padx=4, sticky="ew")

        self._apply_language()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _copy_to_clipboard(self, field: str) -> None:
        """Copy một trường cụ thể vào clipboard."""
        value = self.data.get(field, "")
        if not value:
            return
        self.clipboard_clear()
        self.clipboard_append(value)
        field_labels = {
            "display": "rds.field.display_name",
            "host": "rds.field.host",
            "user": "rds.field.username",
            "pass": "rds.field.password",
            "subsystem": "rds.field.subsystem",
        }
        label = i18n.translate(field_labels.get(field, "rds.field.display_name"))
        messagebox.showinfo(
            i18n.translate(APP_TITLE_KEY),
            i18n.translate("rds.msg.copy_success", field=label),
            parent=self,
        )

    def _edit(self) -> None:
        """Mở dialog chỉnh sửa và cập nhật lại dữ liệu hiển thị."""
        dialog = AddDialog(self, initial=self.data)
        if dialog.result:
            self._on_edit(dialog.result)
            self.data = dialog.result
            self._apply_language()

    def _apply_language(self) -> None:
        """Áp dụng chuỗi đa ngôn ngữ cho giao diện chi tiết."""
        self.title(i18n.translate("rds.detail.title"))
        self.lbl_display.configure(text=i18n.translate("rds.field.display_name") + ":")
        self.lbl_host.configure(text=i18n.translate("rds.field.host") + ":")
        self.lbl_user.configure(text=i18n.translate("rds.field.username") + ":")
        self.lbl_pass.configure(text=i18n.translate("rds.field.password") + ":")
        self.lbl_sub.configure(text=i18n.translate("rds.field.subsystem") + ":")

        self.val_display.configure(text=self.data.get("display", ""))
        self.val_host.configure(text=self.data.get("host", ""))
        self.val_user.configure(text=self.data.get("user", ""))
        self.val_pass.configure(text=self.data.get("pass", ""))
        self.val_sub.configure(text=self.data.get("subsystem", ""))

        self.btn_copy_host.configure(text=i18n.translate("rds.btn.copy_host"))
        self.btn_copy_user.configure(text=i18n.translate("rds.btn.copy_user"))
        self.btn_copy_pass.configure(text=i18n.translate("rds.btn.copy_pass"))
        self.btn_edit.configure(text=i18n.translate("rds.btn.edit"))

    def _handle_language_change(self, _: str) -> None:
        """Callback cập nhật UI khi thay đổi ngôn ngữ."""
        self._apply_language()

    def _set_icon(self) -> None:
        """Áp dụng icon logo nếu có."""
        if ICON_PATH.exists():
            try:
                self.iconbitmap(str(ICON_PATH))
            except Exception:
                pass

    def _on_close(self) -> None:
        """Hủy listener và đóng cửa sổ."""
        i18n.remove_listener(self._lang_listener)
        self.destroy()


class RDSInfoWindow(tk.Toplevel):
    """Cửa sổ chính hiển thị danh sách subsystem và host RDS."""

    def __init__(self, parent: Optional[tk.Misc] = None):
        """Khởi tạo cửa sổ quản lý RDS với dữ liệu hiện có."""
        super().__init__(parent)
        self.title(i18n.translate("rds.title"))
        self.geometry("420x360")
        self.minsize(420, 360)
        self._set_icon()

        self.hosts: List[Dict[str, str]] = load_hosts()
        self._active_subsystem: Optional[str] = None

        self._lang_listener = self._handle_language_change
        i18n.add_listener(self._lang_listener)

        container = ttk.Frame(self, padding=8)
        container.pack(fill="both", expand=True)
        container.columnconfigure(1, weight=1)
        container.rowconfigure(1, weight=1)

        self.frm_subsystems = ttk.LabelFrame(container, padding=6)
        self.frm_hosts = ttk.LabelFrame(container, padding=6)
        self.frm_subsystems.grid(row=0, column=0, rowspan=2, sticky="nsew", padx=(0, 6))
        self.frm_hosts.grid(row=0, column=1, sticky="nsew")

        for frame in (self.frm_subsystems, self.frm_hosts):
            frame.columnconfigure(0, weight=1)
            frame.rowconfigure(0, weight=1)

        self.lst_subsystems = tk.Listbox(self.frm_subsystems, exportselection=False, height=12)
        self.lst_subsystems.grid(row=0, column=0, sticky="nsew")
        self.lst_subsystems.bind("<<ListboxSelect>>", lambda _: self._on_subsystem_change())

        self.lst_hosts = tk.Listbox(self.frm_hosts, exportselection=False, height=12)
        self.lst_hosts.grid(row=0, column=0, sticky="nsew")
        self.lst_hosts.bind("<Double-Button-1>", lambda _: self._open_detail())

        btn_frame = ttk.Frame(container)
        btn_frame.grid(row=1, column=1, sticky="new", pady=(6, 0))
        for col in range(2):
            btn_frame.columnconfigure(col, weight=1, minsize=120)

        self.btn_view = ttk.Button(btn_frame, command=self._open_detail, width=14)
        self.btn_edit = ttk.Button(btn_frame, command=self._edit_host, width=14)
        self.btn_add = ttk.Button(btn_frame, command=self._add_host, width=14)
        self.btn_remove = ttk.Button(btn_frame, command=self._remove_host, width=14)

        self.btn_view.grid(row=0, column=0, padx=4, pady=2, sticky="ew")
        self.btn_edit.grid(row=0, column=1, padx=4, pady=2, sticky="ew")
        self.btn_add.grid(row=1, column=0, padx=4, pady=2, sticky="ew")
        self.btn_remove.grid(row=1, column=1, padx=4, pady=2, sticky="ew")

        self._apply_language()
        self._refresh_subsystems()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _t(self, key: str, **kwargs) -> str:
        """Truy xuất chuỗi dịch với tiền tố rds."""
        return i18n.translate(key, **kwargs)

    def _apply_language(self) -> None:
        """Cập nhật text cho toàn bộ giao diện chính."""
        self.title(self._t("rds.title"))
        self.frm_subsystems.configure(text=self._t("rds.section.subsystems"))
        self.frm_hosts.configure(text=self._t("rds.section.hosts"))
        self.btn_view.configure(text=self._t("rds.btn.open_detail"))
        self.btn_edit.configure(text=self._t("rds.btn.edit"))
        self.btn_add.configure(text=self._t("rds.btn.add"))
        self.btn_remove.configure(text=self._t("rds.btn.remove"))

    def _handle_language_change(self, _: str) -> None:
        """Callback cập nhật giao diện khi đổi ngôn ngữ."""
        self._apply_language()
        self._refresh_subsystems()

    def _set_icon(self) -> None:
        """Áp dụng icon logo nếu có."""
        if ICON_PATH.exists():
            try:
                self.iconbitmap(str(ICON_PATH))
            except Exception:
                pass

    def _refresh_subsystems(self) -> None:
        """Nạp lại danh sách subsystem từ dữ liệu."""
        subsystems = sorted({item.get("subsystem", "") for item in self.hosts if item.get("subsystem")})
        self.lst_subsystems.delete(0, tk.END)
        for subsystem in subsystems:
            self.lst_subsystems.insert(tk.END, subsystem)
        if subsystems:
            if self._active_subsystem in subsystems:
                idx = subsystems.index(self._active_subsystem)
            else:
                idx = 0
            self.lst_subsystems.selection_set(idx)
            self._active_subsystem = subsystems[idx]
        else:
            self._active_subsystem = None
        self._refresh_hosts()

    def _refresh_hosts(self) -> None:
        """Nạp lại danh sách host theo subsystem đang chọn."""
        self.lst_hosts.delete(0, tk.END)
        if not self._active_subsystem:
            return
        items = [item for item in self.hosts if item.get("subsystem") == self._active_subsystem]
        for entry in items:
            display = entry.get("display") or entry.get("host") or ""
            self.lst_hosts.insert(tk.END, display)

    def _on_subsystem_change(self) -> None:
        """Xử lý khi người dùng chọn subsystem mới."""
        selection = self.lst_subsystems.curselection()
        if not selection:
            self._active_subsystem = None
            self.lst_hosts.delete(0, tk.END)
            return
        self._active_subsystem = self.lst_subsystems.get(selection[0])
        self._refresh_hosts()

    def _get_selected_host(self) -> Optional[Dict[str, str]]:
        """Trả về bản ghi host đang chọn."""
        if not self._active_subsystem:
            return None
        host_idx = self.lst_hosts.curselection()
        if not host_idx:
            return None
        name = self.lst_hosts.get(host_idx[0])
        for entry in self.hosts:
            display = entry.get("display") or entry.get("host") or ""
            if entry.get("subsystem") == self._active_subsystem and display == name:
                return entry
        return None

    def _open_detail(self) -> None:
        """Mở cửa sổ chi tiết host."""
        entry = self._get_selected_host()
        if not entry:
            messagebox.showinfo(self._t(APP_TITLE_KEY), self._t("rds.msg.no_host"), parent=self)
            return

        def _commit(updated: Dict[str, str]) -> None:
            self._update_host(entry, updated)

        HostDetailWindow(self, entry.copy(), on_edit=_commit)

    def _add_host(self) -> None:
        """Thêm cấu hình mới."""
        dialog = AddDialog(self)
        if dialog.result:
            self.hosts.append(dialog.result)
            save_hosts(self.hosts)
            self._active_subsystem = dialog.result.get("subsystem")
            self._refresh_subsystems()

    def _edit_host(self) -> None:
        """Chỉnh sửa host đang chọn."""
        entry = self._get_selected_host()
        if not entry:
            messagebox.showinfo(self._t(APP_TITLE_KEY), self._t("rds.msg.no_host"), parent=self)
            return
        dialog = AddDialog(self, initial=entry)
        if dialog.result:
            self._update_host(entry, dialog.result)

    def _update_host(self, original: Dict[str, str], updated: Dict[str, str]) -> None:
        """Cập nhật dữ liệu host rồi lưu lại."""
        idx = self.hosts.index(original)
        self.hosts[idx] = updated
        save_hosts(self.hosts)
        self._active_subsystem = updated.get("subsystem")
        self._refresh_subsystems()

    def _remove_host(self) -> None:
        """Xóa host đang chọn."""
        entry = self._get_selected_host()
        if not entry:
            messagebox.showinfo(self._t(APP_TITLE_KEY), self._t("rds.msg.no_host"), parent=self)
            return
        display = entry.get("display") or entry.get("host") or ""
        if not messagebox.askyesno(
            self._t(APP_TITLE_KEY),
            self._t("rds.msg.delete_confirm", name=display),
            parent=self,
        ):
            return
        self.hosts.remove(entry)
        save_hosts(self.hosts)
        self._refresh_subsystems()

    def _on_close(self) -> None:
        """Gỡ listener và đóng cửa sổ chính."""
        i18n.remove_listener(self._lang_listener)
        self.destroy()


def open_rds_window(parent: Optional[tk.Misc] = None) -> RDSInfoWindow:
    """Hàm tiện ích mở màn hình RDS."""
    window = RDSInfoWindow(parent=parent)
    window.focus_set()
    return window


if __name__ == "__main__":
    root = tk.Tk()
    open_rds_window(root)
    root.mainloop()
