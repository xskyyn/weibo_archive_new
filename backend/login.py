"""纯 httpx 扫码登录（passport.weibo.cn SSO），无需浏览器。

流程：
  1. qrcode/show  获取二维码图片 + qrid
  2. qrcode/scan  轮询，直到用户确认(20000)拿到 alt 授权码
  3. sso/login     用 alt 换取登录 Cookie(SUB/SUBP 等) 与 uid

注意：新浪接口偶有调整，真机验证时如返回异常可据此微调。
"""
from __future__ import annotations

import time
import uuid
from typing import Dict, Optional

import httpx

from backend.utils.logger import get_logger

logger = get_logger("weibo.login")

PASSPORT = "https://passport.weibo.cn/sso"
_TIMEOUT = httpx.Timeout(20.0, connect=10.0)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36 Edg/152.0.0.0"
    ),
    "Referer": "https://passport.weibo.cn/signin/login",
    "Accept": "application/json, text/plain, */*",
}


class QrLoginError(Exception):
    pass


class QrLoginManager:
    """管理进行中的扫码登录会话（内存态，带超时清理）。"""

    def __init__(self):
        self._sessions: Dict[str, dict] = {}
        self._ttl = 180  # 秒

    def _cleanup(self) -> None:
        now = time.time()
        self._sessions = {
            k: v for k, v in self._sessions.items() if now - v["created"] < self._ttl
        }

    def get(self, sid: str) -> Optional[dict]:
        return self._sessions.get(sid)

    async def start(self) -> dict:
        self._cleanup()
        async with httpx.AsyncClient(headers=_HEADERS, timeout=_TIMEOUT,
                                     follow_redirects=True) as client:
            r = await client.get(f"{PASSPORT}/qrcode/show",
                                 params={"st": str(int(time.time()))})
            if r.status_code != 200 or "json" not in r.headers.get("content-type", ""):
                final = str(r.url)
                raise QrLoginError(
                    f"扫码接口不可用 (status={r.status_code}, 最终地址={final})。"
                    "新浪已收紧匿名 SSO 接口，纯 HTTP 扫码可能被拦截。"
                )
            try:
                payload = r.json()
            except Exception:
                raise QrLoginError(f"扫码接口返回非 JSON: {r.text[:200]}")
            data = payload.get("data", {}) or {}
            qrid = data.get("qrid") or payload.get("qrid")
            qr_img = data.get("qrcode_image")
            if isinstance(qr_img, dict):
                qr_img = qr_img.get("location") or ""
            if not qrid or not qr_img:
                raise QrLoginError(f"二维码接口字段异常: {payload}")
            sid = uuid.uuid4().hex[:16]
            self._sessions[sid] = {
                "sid": sid,
                "qrid": qrid,
                "qr_url": qr_img if qr_img.startswith("http") else f"https:{qr_img}",
                "status": "wait",
                "alt": None,
                "uid": None,
                "created": time.time(),
            }
            return {
                "sid": sid,
                "qrid": qrid,
                "qr_url": self._sessions[sid]["qr_url"],
                "expires_in": self._ttl,
            }

    async def status(self, sid: str) -> dict:
        sess = self._sessions.get(sid)
        if sess is None:
            return {"state": "expired", "msg": "会话已失效，请重新获取二维码"}
        async with httpx.AsyncClient(headers=_HEADERS, timeout=_TIMEOUT,
                                     follow_redirects=True) as client:
            r = await client.get(f"{PASSPORT}/qrcode/scan",
                                 params={"qrid": sess["qrid"], "st": str(int(time.time()))})
            payload = r.json()
            code = str(payload.get("code", ""))
            data = payload.get("data", {}) or {}
            if code == "20000":
                sess["alt"] = data.get("alt")
                sess["uid"] = data.get("uid")
                sess["status"] = "confirmed"
                return {"state": "confirmed", "msg": "已确认，正在换取 Cookie…"}
            if code == "50113":
                return {"state": "scan", "msg": "已扫码，请在手机上确认"}
            return {"state": "wait", "msg": "等待扫码…"}

    async def confirm(self, sid: str) -> dict:
        sess = self._sessions.get(sid)
        if sess is None:
            raise QrLoginError("会话不存在或已过期")
        alt = sess.get("alt")
        if not alt:
            raise QrLoginError("尚未完成扫码确认")
        async with httpx.AsyncClient(headers=_HEADERS, timeout=_TIMEOUT,
                                     follow_redirects=True) as client:
            r = await client.get(f"{PASSPORT}/login",
                                 params={"entry": "mweibo", "alt": alt,
                                         "st": str(int(time.time()))})
            r.raise_for_status()
            cookies = dict(r.cookies)
            if not cookies:
                logger.error("登录响应无 Cookie: %s", r.text[:300])
                raise QrLoginError("登录响应未包含有效 Cookie，请重试")
            # Cookie 通常需带上 MLOGIN 标记与 XSRF 占位
            cookies.setdefault("MLOGIN", "1")
            cookies.setdefault("XSRF-TOKEN", "")
            return {
                "ok": True,
                "cookies": cookies,
                "uid": sess.get("uid"),
            }

    def drop(self, sid: str) -> None:
        self._sessions.pop(sid, None)


qr_login = QrLoginManager()