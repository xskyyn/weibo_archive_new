"""WeiboArchive FastAPI 启动入口与生命周期管理。"""
from __future__ import annotations

import uvicorn
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.config import APP_TITLE, HOST, PORT, VERSION, WORKSPACE_DIR
from backend.database import init_db
from backend.routers import auth, export, posts, task
from backend.utils.logger import get_logger, setup_logging

logger = get_logger("weibo.main")
setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    logger.info("数据库与 FTS5 全文搜索引擎初始化完成。")
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

# 静态资源服务（前端构建产物 + 下载的媒体）
app.mount("/media", StaticFiles(directory=str(WORKSPACE_DIR)), name="media")

FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"


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


if __name__ == "__main__":
    import webbrowser
    webbrowser.open(f"http://{HOST}:{PORT}")
    uvicorn.run("backend.main:app", host=HOST, port=PORT, reload=False)