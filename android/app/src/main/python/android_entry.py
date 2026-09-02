"""Android 端 Python 入口：在后台线程启动/停止 FastAPI 服务。

由 BackendService 通过 Chaquopy 调用。服务运行在独立线程的 asyncio 事件循环中，
Android 上无法安装信号处理器（uvicorn 在非主线程会自动跳过），因此可安全阻塞运行。
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

_server = None


def start_server(port: int = 8964) -> None:
    global _server
    import uvicorn

    from backend.main import app

    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="info", reload=False)
    server = uvicorn.Server(config)
    _server = server
    server.run()


def stop_server() -> None:
    global _server
    if _server is not None:
        _server.should_exit = True
        _server = None
