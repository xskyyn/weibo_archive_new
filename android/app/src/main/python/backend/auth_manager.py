"""账号管理：多账号 Cookie 持久化、切换、退出。

元数据存于 accounts.json（不含 Cookie 明文），Cookie 按账号存于
accounts/<id>/cookie.json，避免明文密钥混入元数据。
Cookie 仍是敏感凭证，仅存本机。
"""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from backend.config import WORKSPACE_DIR

ACCOUNTS_FILE = WORKSPACE_DIR / "accounts.json"
ACCOUNTS_DIR = WORKSPACE_DIR / "accounts"


def _defaults() -> dict:
    return {"active": None, "accounts": []}


def _load() -> dict:
    if not ACCOUNTS_FILE.exists():
        return _defaults()
    try:
        with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return _defaults()


def _save(data: dict) -> None:
    ACCOUNTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = ACCOUNTS_FILE.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp.replace(ACCOUNTS_FILE)


def _cookie_path(acc_id: str) -> Path:
    return ACCOUNTS_DIR / acc_id / "cookie.json"


def _has_cookie(acc: dict) -> bool:
    return _cookie_path(acc["id"]).exists()


# -- 查询 -----------------------------------------------------------
def list_accounts() -> list[dict]:
    """返回账号元信息（不含 Cookie 明文）。"""
    data = _load()
    out = []
    for acc in data["accounts"]:
        out.append({
            "id": acc["id"],
            "name": acc.get("name", ""),
            "uid": acc.get("uid"),
            "has_cookie": _has_cookie(acc),
            "updated_at": acc.get("updated_at"),
        })
    return out


def active_account() -> Optional[dict]:
    data = _load()
    acc_id = data.get("active")
    for acc in data["accounts"]:
        if acc["id"] == acc_id:
            return dict(acc)
    return None


def active_uid() -> Optional[int]:
    acc = active_account()
    return acc.get("uid") if acc else None


def active_cookie_path() -> Path:
    acc = active_account()
    if acc is None:
        return WORKSPACE_DIR / "noactive" / "cookie.json"
    return _cookie_path(acc["id"])


# -- 变更 -----------------------------------------------------------
def save_account(name: str, uid: Optional[int], cookies: Dict[str, str]) -> dict:
    """保存/更新账号。传入相同 uid 时复用已有条目，否则新建并设为当前。"""
    data = _load()
    acc_id = None
    # 同一 uid 复用(刷新 Cookie)，避免重复条目
    for acc in data["accounts"]:
        if uid is not None and acc.get("uid") == uid:
            acc_id = acc["id"]
            acc["name"] = name or acc.get("name", "")
            acc["updated_at"] = int(time.time())
            break
    if acc_id is None:
        acc_id = uuid.uuid4().hex[:12]
        data["accounts"].append({
            "id": acc_id, "name": name, "uid": uid, "updated_at": int(time.time()),
        })
    data["active"] = acc_id
    # 写 Cookie 明文到账号专属文件
    p = _cookie_path(acc_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(cookies, f, ensure_ascii=False, indent=2)
    _save(data)
    return {"id": acc_id, "name": name, "uid": uid}


def set_active(acc_id: str) -> Optional[dict]:
    data = _load()
    for acc in data["accounts"]:
        if acc["id"] == acc_id:
            data["active"] = acc_id
            _save(data)
            return dict(acc)
    return None


def remove_account(acc_id: str) -> bool:
    data = _load()
    before = len(data["accounts"])
    data["accounts"] = [a for a in data["accounts"] if a["id"] != acc_id]
    if len(data["accounts"]) == before:
        return False
    if data.get("active") == acc_id:
        data["active"] = (data["accounts"][0]["id"] if data["accounts"] else None)
    p = _cookie_path(acc_id)
    if p.exists():
        p.unlink()
    _save(data)
    return True


def logout_active() -> bool:
    """清除当前账号的 Cookie（保留账号条目以便下次重新登录）。"""
    acc = active_account()
    if acc is None:
        return False
    p = _cookie_path(acc["id"])
    if p.exists():
        p.unlink()
    return True