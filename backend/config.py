"""全局配置管理。"""
from __future__ import annotations

import json
import os
import socket
import sys
from pathlib import Path


def is_frozen() -> bool:
    """是否运行在打包后的环境（PyInstaller/Nuitka）。"""
    return bool(getattr(sys, "frozen", False))


def _settings_file() -> Path:
    """设置文件位置：独立于数据目录，避免切换数据目录后设置丢失。

    - 打包 Windows 版：%APPDATA%/WeiboArchive/settings.json
    - 源码运行：项目根下的 settings.json
    """
    if is_frozen() and sys.platform.startswith("win"):
        appdata = os.environ.get("APPDATA") or str(Path.home())
        return Path(appdata) / "WeiboArchive" / "settings.json"
    return Path(__file__).resolve().parent.parent / "settings.json"


SETTINGS_FILE = _settings_file()


def _load_settings() -> dict:
    if not SETTINGS_FILE.exists():
        return {}
    try:
        return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _saved_workspace_dir() -> Path | None:
    val = _load_settings().get("workspace_dir")
    if not val:
        return None
    return Path(val).expanduser()


def _data_root() -> Path:
    """数据根目录（优先级：环境变量 > 设置文件 > 默认）。

    - 打包 Windows 版：默认 %USERPROFILE%/WeiboArchive/workspace
    - 源码运行：项目根下的 workspace/
    可在应用内"设置"页修改，保存后重启生效。
    """
    env = os.environ.get("WEIBO_WORKSPACE")
    if env:
        return Path(env)
    saved = _saved_workspace_dir()
    if saved:
        return saved
    if is_frozen() and sys.platform.startswith("win"):
        userprofile = os.environ.get("USERPROFILE") or str(Path.home())
        return Path(userprofile) / "WeiboArchive" / "workspace"
    return Path(__file__).resolve().parent.parent / "workspace"


# ---------------------------------------------------------------------------
# 路径配置
# ---------------------------------------------------------------------------
# 项目根目录 (对应源码运行时的根；打包后为后端模块所在目录)
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 运行时数据目录 (自动创建；打包版位于用户目录，见 _data_root)
WORKSPACE_DIR = _data_root()

# 默认用户工作目录 (按 UID 隔离，运行时动态切换)
DEFAULT_USER_DIR = WORKSPACE_DIR / "default"
RESOURCE_DIR = DEFAULT_USER_DIR / "resources"
PIC_DIR = RESOURCE_DIR / "pic"
VIDEO_DIR = RESOURCE_DIR / "video"
AVATAR_DIR = RESOURCE_DIR / "avatar"
QR_CACHE_DIR = WORKSPACE_DIR / "qr_cache"
EXPORT_DIR = WORKSPACE_DIR / "exports"
# 运行日志目录（GUI 版 console=False，必须落盘，否则日志丢失）
LOGS_DIR = WORKSPACE_DIR / "logs"

for _dir in (WORKSPACE_DIR, DEFAULT_USER_DIR, RESOURCE_DIR, PIC_DIR,
             VIDEO_DIR, AVATAR_DIR, QR_CACHE_DIR, EXPORT_DIR, LOGS_DIR):
    _dir.mkdir(parents=True, exist_ok=True)

# 数据库文件 (运行时根据登录 UID 动态选择)
DATABASE_PATH = DEFAULT_USER_DIR / "weibo_archive.db"
DATABASE_URL = f"sqlite+aiosqlite:///{DATABASE_PATH}"

# 默认 Cookie 文件 (用户会从需求方获得真实 cookie.json)
COOKIE_FILE = PROJECT_ROOT / "cookie.json"

# ---------------------------------------------------------------------------
# 服务配置
# ---------------------------------------------------------------------------
HOST = "127.0.0.1"
PORT = 8964

# ---------------------------------------------------------------------------
# 抓取并发配置
# ---------------------------------------------------------------------------
# 最大并发 API 请求数 (asyncio.Semaphore)
CONCURRENCY = 5
# 页面间随机延迟区间 (秒)
DELAY_MIN = 0.7
DELAY_MAX = 1.5
# 每次启动归档时最多抓取多少页 (0 表示全量)
MAX_PAGES = 0
# 下载图片/视频的并发数
MEDIA_CONCURRENCY = 3

# ---------------------------------------------------------------------------
# 搜索配置
# ---------------------------------------------------------------------------
# FTS5 每页查询返回上限
SEARCH_PAGE_SIZE = 20

# ---------------------------------------------------------------------------
# 其他
# ---------------------------------------------------------------------------
APP_TITLE = "WeiboArchive 微博归档工具"
VERSION = "1.4.0"


# ---------------------------------------------------------------------------
# 设置读写（数据目录等，持久化到 SETTINGS_FILE）
# ---------------------------------------------------------------------------
def get_settings() -> dict:
    """返回当前生效的设置（含数据目录等）。"""
    return {
        "workspace_dir": str(WORKSPACE_DIR),
        "settings_file": str(SETTINGS_FILE),
        "version": VERSION,
        "frozen": is_frozen(),
    }


def save_workspace_dir(path: str) -> Path:
    """保存新的数据目录并返回新路径（当前进程需重启后生效）。"""
    new_dir = Path(path).expanduser()
    if not new_dir.is_absolute():
        new_dir = Path.cwd() / new_dir
    new_dir.mkdir(parents=True, exist_ok=True)
    data = _load_settings()
    data["workspace_dir"] = str(new_dir)
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = SETTINGS_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(SETTINGS_FILE)
    return new_dir


# 重启标志：数据目录等设置变更后由桌面壳检测并自动重启
RESTART_FLAG_FILE = SETTINGS_FILE.with_name("restart.flag")


def request_restart() -> None:
    RESTART_FLAG_FILE.parent.mkdir(parents=True, exist_ok=True)
    RESTART_FLAG_FILE.write_text("1", encoding="utf-8")


def consume_restart_flag() -> bool:
    if RESTART_FLAG_FILE.exists():
        try:
            RESTART_FLAG_FILE.unlink()
        except OSError:
            pass
        return True
    return False


def resolve_port(start: int = PORT, try_n: int = 20) -> int:
    """从 start 开始寻找第一个可用端口（端口冲突时自动递增），返回端口号。"""
    for offset in range(try_n):
        port = start + offset
        if port > 65535:
            break
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind((HOST, port))
                return port
            except OSError:
                continue
    return start