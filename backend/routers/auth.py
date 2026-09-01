"""认证与账号模块：Cookie 导入、扫码登录、多账号切换/退出、目标切换。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend import auth_manager
from backend.database import set_db_target
from backend.login import QrLoginError, qr_login
from backend.schemas import CookieImport, SetTargetReq, SwitchAccountReq
from backend.scraper.client import WeiboClient
from backend.utils.logger import mask_cookie

router = APIRouter(prefix="/api/auth", tags=["Auth"])


def _current_client() -> WeiboClient:
    return WeiboClient()


# ---------------------------------------------------------------------------
# 账号状态与列表
# ---------------------------------------------------------------------------
@router.get("/config")
async def app_config():
    acc = auth_manager.active_account()
    client = _current_client()
    return {
        "version": None,
        "active": acc.get("id") if acc else None,
        "name": acc.get("name", "") if acc else "",
        "uid": acc.get("uid") if acc else None,
        "has_cookie": client.has_cookie,
        "cookie_keys": client.cookie_keys,
        "qr_enabled": True,
    }


@router.get("/status")
async def cookie_status():
    acc = auth_manager.active_account()
    client = _current_client()
    return {
        "ok": client.has_cookie,
        "has_cookie": client.has_cookie,
        "active": acc.get("id") if acc else None,
        "name": acc.get("name", "") if acc else "",
        "uid": acc.get("uid") if acc else None,
        "keys": client.cookie_keys,
        "xsrf": "XSRF-TOKEN" in client.cookie_keys,
    }


@router.get("/accounts")
async def list_accounts():
    return {
        "active": (auth_manager.active_account() or {}).get("id"),
        "accounts": auth_manager.list_accounts(),
    }


@router.post("/accounts/switch")
async def switch_account(body: SwitchAccountReq):
    acc = auth_manager.set_active(body.id)
    if not acc:
        raise HTTPException(404, "账号不存在")
    # 切换到该账号的自有工作区
    if acc.get("uid"):
        await set_db_target(acc["uid"])
    return {"ok": True, "account": acc}


@router.delete("/accounts/{account_id}")
async def remove_account(account_id: str):
    ok = auth_manager.remove_account(account_id)
    if not ok:
        raise HTTPException(404, "账号不存在")
    return {"ok": True}


# ---------------------------------------------------------------------------
# Cookie 导入 / 校验 / 退出
# ---------------------------------------------------------------------------
@router.post("/cookie")
async def import_cookie(body: CookieImport):
    cookies = body.merged()
    if not cookies:
        return {"ok": False, "msg": "Cookie 为空"}
    cookies["MLOGIN"] = "1"
    auth_manager.save_account(body.name or "手动导入", body.uid, cookies)
    return {"ok": True, "msg": "Cookie 导入成功", "keys": [k for k in cookies if k != "MLOGIN"]}


@router.post("/validate")
async def validate_cookie():
    client = _current_client()
    if not client.has_cookie:
        return {"ok": False, "msg": "请先登录/导入 Cookie"}
    try:
        token = await client.refresh_token()
        if not token:
            await client.close()
            return {"ok": False, "msg": "Cookie 校验失败，登录已失效"}
        # 用 Cookie 解析本人 uid 与昵称，更新账号信息并切换工作区
        try:
            from backend.scraper.client import resolve_self_profile
            uid, name = await resolve_self_profile(client)
        except Exception:
            from backend.scraper.client import resolve_container_id
            uid, name = (await resolve_container_id(client))[0], ""
        auth_manager.save_account(name or "账号", uid, dict(client._cookies))
        await set_db_target(uid)
        await client.close()
        return {"ok": True, "msg": "Cookie 校验成功", "uid": uid, "name": name}
    except Exception as e:
        await client.close()
        return {"ok": False, "msg": mask_cookie(str(e) or "校验失败")}


@router.post("/logout")
async def logout():
    auth_manager.logout_active()
    return {"ok": True, "msg": "已退出当前账号"}


# ---------------------------------------------------------------------------
# 扫码登录（纯 httpx passport.weibo.cn）
# ---------------------------------------------------------------------------
@router.post("/qr/start")
async def qr_start():
    try:
        return {"ok": True, **await qr_login.start()}
    except Exception as e:
        return {"ok": False, "msg": str(e)}


@router.get("/qr/{sid}/status")
async def qr_status(sid: str):
    try:
        return {"ok": True, **await qr_login.status(sid)}
    except Exception as e:
        return {"ok": False, "msg": str(e)}


@router.post("/qr/{sid}/confirm")
async def qr_confirm(sid: str):
    try:
        result = await qr_login.confirm(sid)
        cookies = result["cookies"]
        uid = result.get("uid")
        auth_manager.save_account("扫码账号", uid, cookies)
        if uid:
            await set_db_target(uid)
        qr_login.drop(sid)
        return {"ok": True, "msg": "登录成功", "uid": uid}
    except QrLoginError as e:
        return {"ok": False, "msg": str(e)}
    except Exception as e:
        qr_login.drop(sid)
        return {"ok": False, "msg": mask_cookie(str(e))}


# ---------------------------------------------------------------------------
# 目标用户切换（浏览/归档非登录账号的其他用户）
# ---------------------------------------------------------------------------
@router.post("/target")
async def set_target(body: SetTargetReq):
    from backend.database import AsyncSessionLocal, get_stats
    await set_db_target(body.uid)
    stats = {}
    async with AsyncSessionLocal() as db:
        stats = await get_stats(db)
    name = ""
    try:
        c = _current_client()
        profile = await c.get_json(
            f"https://m.weibo.cn/profile/info?uid={body.uid}",
            referer=f"https://m.weibo.cn/profile/{body.uid}",
        )
        u = profile.get("user", profile)
        name = u.get("screen_name", "")
        await c.close()
    except Exception:
        pass
    return {"ok": True, "uid": body.uid, "name": name, "current": True, "stats": stats}