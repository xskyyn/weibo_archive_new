"""当前归档工作区管理：按目标 UID 隔离数据库与媒体目录。

每个被归档对象(目标用户 UID)拥有独立的 DB 与 resources 目录：
    workspace/{uid}/weibo_archive.db
    workspace/{uid}/resources/{pic,video,avatar}
"""
from __future__ import annotations

from pathlib import Path

from backend.config import WORKSPACE_DIR

_current_uid: int | None = None


def current_uid() -> int | None:
    return _current_uid


def set_current_uid(uid: int | None) -> None:
    global _current_uid
    _current_uid = uid


def user_dir() -> Path:
    uid = _current_uid
    return (WORKSPACE_DIR / str(uid)) if uid is not None else WORKSPACE_DIR / "default"


def resources_dir() -> Path:
    return user_dir() / "resources"


def pic_dir() -> Path:
    return resources_dir() / "pic"


def video_dir() -> Path:
    return resources_dir() / "video"


def avatar_dir() -> Path:
    return resources_dir() / "avatar"


def export_dir() -> Path:
    return WORKSPACE_DIR / "exports"


def db_path() -> Path:
    return user_dir() / "weibo_archive.db"


def db_url() -> str:
    return f"sqlite+aiosqlite:///{user_dir() / 'weibo_archive.db'}"


def ensure_dirs() -> None:
    for d in (user_dir(), resources_dir(), pic_dir(), video_dir(), avatar_dir(), export_dir()):
        d.mkdir(parents=True, exist_ok=True)