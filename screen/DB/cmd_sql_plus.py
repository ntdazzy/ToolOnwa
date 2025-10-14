# -*- coding: utf-8 -*-
"""
cmd_sql_plus.py
- Build SQL*Plus command string from form values.
- Open new Command Prompt, auto-paste, and run it.
- Toggle: use_host_port -> if True and host+port provided, use "host:port/alias", else only "alias".
"""
from __future__ import annotations
import subprocess

def _build_connect_str(user: str, password: str, host: str, port: str, alias: str, use_host_port: bool) -> str:
    user = user.strip(); password = password.strip()
    alias = alias.strip(); host = host.strip(); port = port.strip()
    dsn = f"{host}:{port}/{alias}" if (use_host_port and host and port) else alias
    return f"SQLPLUS {user}/{password}@{dsn}"

def open_sqlplus(user: str, password: str, host: str, port: str, alias: str, use_host_port: bool=False) -> None:
    """
    Prepare a sqlplus command and paste it into a new cmd window, then execute.
    """
    cmdline = _build_connect_str(user, password, host, port, alias, use_host_port)

    ps_script = rf"$c = '{cmdline}'; " \
                rf"Set-Clipboard -Value $c; " \
                rf"Start-Process cmd; " \
                rf"Start-Sleep -Milliseconds 600; " \
                rf"$ws = New-Object -ComObject WScript.Shell; " \
                rf"$ws.SendKeys('^v'); " \
                rf"Start-Sleep -Milliseconds 150; " \
                rf"$ws.SendKeys('{{ENTER}}');"

    subprocess.Popen(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script], shell=False)
