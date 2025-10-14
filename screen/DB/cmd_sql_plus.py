# -*- coding: utf-8 -*-
"""
cmd_sql_plus.py
"""
from __future__ import annotations
import re, subprocess

CREATE_NEW_CONSOLE = 0x00000010  # Windows only

def _quote_user(u: str) -> str:
    # Bọc user nếu có ký tự đặc biệt
    if re.search(r'[^A-Za-z0-9_$#]', u):
        u = u.replace('"', '""')
        return f'"{u}"'
    return u

def _quote_pwd(p: str) -> str:
    # Luôn bọc password
    p = p.replace('"', '""')
    return f'"{p}"'

def build_dsn(host: str, port: str, alias_or_service: str, use_host_port: bool) -> str:
    host = host.strip(); port = port.strip(); a = alias_or_service.strip()
    return f"{host}:{port}/{a}" if (use_host_port and host and port and a) else a

def build_connect_string(user: str, password: str, host: str, port: str, alias_or_service: str, use_host_port: bool) -> str:
    u = _quote_user(user.strip()); p = _quote_pwd(password.strip())
    dsn = build_dsn(host, port, alias_or_service, use_host_port)
    return f"{u}/{p}@{dsn}"

def open_sqlplus(user: str, password: str, host: str, port: str, alias_or_service: str, use_host_port: bool):
    conn = build_connect_string(user, password, host, port, alias_or_service, use_host_port)
    try:
        subprocess.Popen(["sqlplus", conn], shell=False, creationflags=CREATE_NEW_CONSOLE)
    except FileNotFoundError:
        subprocess.Popen(["sqlplus.exe", conn], shell=False, creationflags=CREATE_NEW_CONSOLE)
