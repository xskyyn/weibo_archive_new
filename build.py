#!/usr/bin/env python3
"""构建脚本：将前端编译到 frontend/dist，供后端静态托管。"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main() -> int:
    print("[*] 构建前端...")
    rc = subprocess.run(
        ["npm", "run", "build"], cwd=str(ROOT / "frontend"), check=False
    ).returncode
    if rc != 0:
        print("[!] 前端构建失败。")
        return rc
    print("[+] 前端构建完成 → frontend/dist")
    return 0


if __name__ == "__main__":
    sys.exit(main())