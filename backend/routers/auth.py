"""认证与登录模块：Cookie 导入、校验、状态查询。"""
from __future__ import annotations

from fastapi import APIRouter

from backend.config import COOKIE_FILE, VERSION
from backend.schemas import CookieImport
from backend.scraper.client import WeiboClient
from backend.utils.logger import mask_cookie

router = APIRouter(prefix="/api/auth", tags=["Auth"])


def _anon_client() -> WeiboClient:
    return WeiboClient(COOKIE_FILE)


@router.post("/cookie")
async def import_cookie(body: CookieImport):
    """导入用户提供的 Cookie。"""
    cookies = body.merged()
    if not cookies:
        return {"ok": False, "msg": "Cookie 为空"}
    client = _anon_client()
    client.import_cookies(cookies)
    return {"ok": True, "msg": "Cookie 导入成功", "keys": client.cookie_keys}


@router.get("/status")
async def cookie_status():
    """查询当前是否有 Cookie 及其关键字段。"""
    client = _anon_client()
    keys = client.cookie_keys
    return {
        "ok": len(keys) > 0,
        "has_cookie": len(keys) > 0,
        "keys": keys,
        "xsrf": "XSRF-TOKEN" in keys,
    }


@router.post("/validate")
async def validate_cookie():
    """调用 m.weibo.cn/api/config 校验 Cookie 有效性与登录态。"""
    client = _anon_client()
    if not client.has_cookie:
        return {"ok": False, "msg": "请先导入 Cookie"}
    try:
        token = await client.refresh_token()
        await client.close()
        return {"ok": token is not None, "msg": "Cookie 校验成功" if token else "校验失败"}
    except Exception as e:
        await client.close()
        return {"ok": False, "msg": mask_cookie(str(e) or "验证失败")}


@router.get("/config")
async def app_config():
    """返回应用配置（前端启动自检用）。"""
    client = _anon_client()
    return {
        "version": VERSION,
        "has_cookie": client.has_cookie,
        "cookie_keys": client.cookie_keys,
    }