#!/bin/bash
# WeiboArchive 一键启动脚本（Linux）
set -e
cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
  echo "[*] 首次运行，正在创建虚拟环境并安装依赖..."
  python3 -m venv .venv
  ./.venv/bin/pip install -U pip wheel setuptools
  ./.venv/bin/pip install -r requirements.txt
fi

if [ ! -d "frontend/dist" ]; then
  echo "[*] 前端尚未构建，正在构建..."
  (cd frontend && npm install && npm run build)
fi

exec ./.venv/bin/python -m backend.main