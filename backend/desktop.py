"""Windows 桌面启动器：内嵌 PyWebView 窗口加载本机 FastAPI 前端。

打包后的 .exe 真正入口就是本文件（见 PyInstaller spec).
启动流程：
  1. 后台线程启动 uvicorn (FastAPI)，自动探测可用端口；
  2. 内嵌浏览器窗口加载 http://127.0.0.1:<port>；
  3. 关闭窗口后停止后端服务，进程优雅退出，无残留。
"""
from __future__ import annotations

import socket
import sys
import threading
import time

import uvicorn

from backend.config import APP_TITLE, HOST, resolve_port
from backend.main import app, run_server
from backend.utils.logger import get_logger

logger = get_logger("weibo.desktop")


def _probe_port() -> int:
    """探测端口；若 8964 不可用则递增，保证单实例多开不冲突。"""
    return resolve_port()


def main() -> int:
    import webview  # 延迟导入：后台(非GUI, Linux)与无 webview 环境下不加载

    port = _probe_port()

    # 后台线程启动 FastAPI
    config = uvicorn.Config(app, host=HOST, port=port, log_level="info", reload=False)
    server = uvicorn.Server(config)
    thread = threading.Thread(target=lambda: server.run(), name="weibo-server", daemon=True)
    thread.start()

    # 等待后端真正就绪
    url = f"http://{HOST}:{port}"
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)

    logger.info("桌面窗口加载 %s", url)
    window = webview.create_window(
        APP_TITLE,
        url,
        width=1360,
        height=880,
        min_size=(1080, 720),
    )

    # 阻塞，直到所有窗口关闭
    webview.start()
    logger.info("窗口已关闭，正在停止后端服务…")

    server.should_exit = True
    # 给 uvicorn 一点时间退出
    thread.join(timeout=3)
    logger.info("后端服务已停止，进程退出。")
    return 0


if __name__ == "__main__":
    sys.exit(main())