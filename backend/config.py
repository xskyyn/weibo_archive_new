"""全局配置管理。"""
from __future__ import annotations

from pathlib import Path

# ---------------------------------------------------------------------------
# 路径配置
# ---------------------------------------------------------------------------
# 项目根目录 (backend 的上一级)
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 运行时数据目录 (自动创建)
WORKSPACE_DIR = PROJECT_ROOT / "workspace"

# 默认用户工作目录 (按 UID 隔离，运行时动态切换)
DEFAULT_USER_DIR = WORKSPACE_DIR / "default"
RESOURCE_DIR = DEFAULT_USER_DIR / "resources"
PIC_DIR = RESOURCE_DIR / "pic"
VIDEO_DIR = RESOURCE_DIR / "video"
AVATAR_DIR = RESOURCE_DIR / "avatar"
EXPORT_DIR = WORKSPACE_DIR / "exports"

for _dir in (WORKSPACE_DIR, DEFAULT_USER_DIR, RESOURCE_DIR, PIC_DIR,
             VIDEO_DIR, AVATAR_DIR, EXPORT_DIR):
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
VERSION = "0.1.0"