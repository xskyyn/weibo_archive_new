"""WeiboArchive FastAPI 启动入口与生命周期管理。"""
from __future__ import annotations

import sys
import uvicorn
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend import auth_manager, workspace
from backend.config import APP_TITLE, HOST, LOGS_DIR, PORT, VERSION, WORKSPACE_DIR, resolve_port
from backend.database import set_db_target
from backend.routers import auth, export, posts, settings, task
from backend.utils.logger import get_logger, setup_logging

logger = get_logger("weibo.main")
setup_logging(log_dir=LOGS_DIR)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时切换到当前账号对应的自有工作区
    uid = auth_manager.active_uid()
    await set_db_target(uid)
    logger.info("数据库与 FTS5 全文搜索引擎初始化完成 (目标 uid=%s, 工作区=%s)", uid, workspace.user_dir())
    yield


app = FastAPI(title=APP_TITLE, version=VERSION, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(task.router)
app.include_router(posts.router)
app.include_router(export.router)
app.include_router(settings.router)

# 静态资源服务（前端构建产物 + 下载的媒体）
app.mount("/media", StaticFiles(directory=str(WORKSPACE_DIR)), name="media")


def _frontend_dist() -> Path:
    """定位前端构建产物目录。

    - 源码运行：frontend/dist
    - PyInstaller onefile：解压目录 sys._MEIPASS/frontend/dist
    - PyInstaller onedir：可执行文件同目录 frontend/dist
    """
    if getattr(sys, "frozen", False):
        candidates = []
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.append(Path(meipass) / "frontend" / "dist")
        candidates.append(Path(sys.executable).resolve().parent / "frontend" / "dist")
        for c in candidates:
            if (c / "index.html").exists():
                return c
    return Path(__file__).resolve().parent.parent / "frontend" / "dist"


FRONTEND_DIST = _frontend_dist()


@app.get("/api/version")
async def api_version():
    return {"name": APP_TITLE, "version": VERSION}


@app.get("/")
async def index():
    index_file = FRONTEND_DIST / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return {
        "name": APP_TITLE,
        "version": VERSION,
        "docs": "/docs",
    }


# 匹配前端路由（hash 模式下非必须，保留 SPA 兜底）
if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="frontend")


def run_server(host: str = HOST, port: int = 0, block: bool = True):
    """启动 FastAPI 服务。port=0 表示自动探测可用端口。

    在独立线程中运行时，请手动指定一个已解析端口。
    """
    if not port:
        port = resolve_port()
    logger.info("服务已启动 http://%s:%s (前端: %s)", host, port, FRONTEND_DIST)
    uvicorn.run(app, host=host, port=port, reload=False)


if __name__ == "__main__":
    import webbrowser

    port = resolve_port()
    webbrowser.open(f"http://{HOST}:{port}")
    run_server(host=HOST, port=port)