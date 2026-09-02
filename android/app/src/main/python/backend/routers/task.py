"""归档任务控制与 WebSocket 实时通信。"""
from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.schemas import StartTaskReq
from backend.scraper.task_manager import task_manager

router = APIRouter(prefix="/api/task", tags=["Task"])


@router.post("/start")
async def start_task(req: StartTaskReq | None = None):
    uid = req.uid if req else None
    await task_manager.start(uid)
    return {"status": task_manager.status}


@router.post("/stop")
async def stop_task():
    await task_manager.stop()
    return {"status": task_manager.status}


@router.post("/resume")
async def resume_task():
    await task_manager.resume()
    return {"status": task_manager.status}


@router.get("/status")
async def get_status():
    return {
        "status": task_manager.status,
        "uid": task_manager.current_uid,
        "total_fetched": task_manager.total_fetched,
        "page": task_manager.current_page,
    }


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await task_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        task_manager.disconnect(websocket)