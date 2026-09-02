"""应用设置：数据目录查看/修改、目录选择、重启。"""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException

from backend import config
from backend.schemas import WorkspaceDirReq

router = APIRouter(prefix="/api/settings", tags=["Settings"])


@router.get("")
async def get_settings():
    return config.get_settings()


@router.put("/workspace")
async def set_workspace(body: WorkspaceDirReq):
    path = body.workspace_dir.strip().strip('"')
    if not path:
        raise HTTPException(400, "数据目录不能为空")
    try:
        new_dir = config.save_workspace_dir(path)
    except Exception as e:
        raise HTTPException(400, f"无法使用该目录：{e}")
    return {
        "ok": True,
        "workspace_dir": str(new_dir),
        "restart_required": True,
        "msg": "数据目录已保存，重启后生效",
    }


@router.post("/pick-dir")
async def pick_dir():
    """打开系统目录选择对话框（桌面版），返回用户选择的路径。"""
    try:
        import webview

        if not webview.windows:
            return {"ok": False, "msg": "当前环境不支持目录选择，请手动输入路径"}

        def _pick():
            return webview.windows[0].create_file_dialog(webview.FOLDER_DIALOG)

        result = await asyncio.to_thread(_pick)
        if result:
            return {"ok": True, "path": str(result[0])}
        return {"ok": False, "msg": "已取消选择"}
    except Exception as e:
        return {"ok": False, "msg": f"无法打开目录选择对话框：{e}"}


@router.post("/restart")
async def restart_app():
    """写入重启标志并关闭桌面窗口，由桌面壳检测后自动重启。"""
    config.request_restart()
    try:
        import webview

        for w in list(webview.windows):
            w.destroy()
    except Exception:
        pass
    return {"ok": True, "msg": "正在重启应用…"}
