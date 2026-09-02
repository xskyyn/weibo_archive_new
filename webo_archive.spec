# -*- mode: python ; coding: utf-8 -*-
"""WeiboArchive Windows 打包 spec（PyInstaller）。

用法（Windows，于项目根目录执行，需先构建前端 dist）：
    pyinstaller --clean --noconfirm webo_archive.spec

产物：dist/WeiboArchive.exe（onefile，无控制台窗口，内置 WebView 前端）
"""
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_data_files

ROOT = Path(".").resolve()

# ---------------------------------------------------------------------------
# 需要完整收集（含 C 扩展/子模块/数据文件）的第三方库
# ---------------------------------------------------------------------------
_HOOK_PKGS = [
    "fastapi", "starlette", "uvicorn", "pydantic",
    "sqlalchemy", "aiosqlite",
    "httpx", "httpcore", "h11", "anyio", "sniffio",
    "tenacity", "jinja2", "websockets", "multipart",
    "click", "certifi", "webview",
]

datas, binaries, hiddenimports = [], [], []
for pkg in _HOOK_PKGS:
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception:
        # 未安装的包直接跳过
        pass

# jieba 分词字典是数据文件，必须随包携带，否则中文分词失效
try:
    datas += collect_data_files("jieba")
except Exception:
    pass

# 前端构建产物 + 导出模板
datas.append((str(ROOT / "frontend/dist"), "frontend/dist"))
datas.append((str(ROOT / "backend/templates"), "backend/templates"))

# 动态/模块级导入补全
hiddenimports += [
    "uvicorn.logging",
    "uvicorn.loops.auto",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan.on",
    "aiosqlite",
]

a = Analysis(
    [str(ROOT / "backend/desktop.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="WeiboArchive",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # 无控制台窗口（GUI）
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ROOT / "build/icon.ico"),
)