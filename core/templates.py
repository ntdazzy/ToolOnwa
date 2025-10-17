"""Quan ly thu vien mau cau lenh SQL bang JSON."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from threading import RLock
from typing import Any, Dict, List, Optional

TEMPLATE_FILE = Path(__file__).resolve().parent.parent / "configs" / "templates.json"
VALID_TYPES = {"insert", "update", "sql"}

_LOCK = RLock()


def _ensure_file() -> None:
    """Tao tep mau neu chua ton tai."""
    with _LOCK:
        if TEMPLATE_FILE.exists():
            return
        TEMPLATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with TEMPLATE_FILE.open("w", encoding="utf-8") as f:
            json.dump({"templates": []}, f, ensure_ascii=False, indent=2)


def _load_all() -> List[Dict[str, Any]]:
    """Doc toan bo danh sach mau tu tep JSON."""
    _ensure_file()
    try:
        with TEMPLATE_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f) or {}
    except Exception:
        return []
    templates = data.get("templates")
    if isinstance(templates, list):
        return [tpl for tpl in templates if isinstance(tpl, dict)]
    return []


def _save_all(items: List[Dict[str, Any]]) -> bool:
    """Ghi danh sach mau xuong tep, tra ve True neu thanh cong."""
    try:
        TEMPLATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with TEMPLATE_FILE.open("w", encoding="utf-8") as f:
            json.dump({"templates": items}, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def list_templates(template_type: str | None = None) -> List[Dict[str, Any]]:
    """Lay danh sach mau theo loai tuy chon."""
    items = _load_all()
    if not template_type:
        return items
    return [tpl for tpl in items if tpl.get("type") == template_type]


def add_template(
    name: str,
    template_type: str,
    content: str,
    description: str = "",
) -> Optional[Dict[str, Any]]:
    """Them mot mau moi vao thu vien."""
    if not content or not name:
        return None
    t_type = template_type if template_type in VALID_TYPES else "sql"
    template = {
        "id": uuid.uuid4().hex,
        "name": name.strip(),
        "type": t_type,
        "description": (description or "").strip(),
        "content": content,
        "created_at": datetime.utcnow().isoformat(timespec="seconds"),
    }
    with _LOCK:
        items = _load_all()
        items.append(template)
        if not _save_all(items):
            return None
    return template


def remove_template(template_id: str) -> bool:
    """Xoa mot mau theo id."""
    if not template_id:
        return False
    with _LOCK:
        items = _load_all()
        new_items = [tpl for tpl in items if tpl.get("id") != template_id]
        if len(new_items) == len(items):
            return False
        return _save_all(new_items)


def get_template(template_id: str) -> Optional[Dict[str, Any]]:
    """Lay thong tin chi tiet cua mot mau."""
    if not template_id:
        return None
    items = _load_all()
    for tpl in items:
        if tpl.get("id") == template_id:
            return tpl
    return None
