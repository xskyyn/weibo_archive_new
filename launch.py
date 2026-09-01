#!/usr/bin/env python3
"""WeiboArchive 打包启动脚本：启动本地 FastAPI 服务并打开浏览器。"""
import os
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
HOST = "127.0.0.1"
PORT = 8964


def is_port_in_use(port: int) -> bool:
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex((HOST, port)) == 0


def main() -> int:
    # 若服务已在运行则直接打开浏览器
    if is_port_in_use(PORT):
        print(f"[*] 服务已在 {PORT} 端口运行，直接打开浏览器。")
        webbrowser.open(f"http://{HOST}:{PORT}")
        return 0

    venv_python = (ROOT / ".venv" / ("Scripts" if os.name == "nt" else "bin") / "python")
    python = str(venv_python) if venv_python.exists() else sys.executable

    # 延迟打开浏览器，等服务起来
    threading.Timer(2.5, lambda: webbrowser.open(f"http://{HOST}:{PORT}")).start()

    env = dict(os.environ)
    env.setdefault("PYTHONUNBUFFERED", "1")
    proc = subprocess.run([python, "-m", "backend.main"], cwd=str(ROOT), env=env)
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main())