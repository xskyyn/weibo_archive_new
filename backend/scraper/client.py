"""httpx 异步客户端封装：Cookie 管理、Token 刷新、指数退避重试与风控识别。"""
from __future__ import annotations

import asyncio
import json
import logging
import random
import time
from pathlib import Path
from typing import Any, Callable, Dict, Optional

import httpx
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from backend.config import (
    COOKIE_FILE, DELAY_MAX, DELAY_MIN,
)
from backend.utils.logger import get_logger

logger = get_logger("weibo.client")


# ---------------------------------------------------------------------------
# 风控异常
# ---------------------------------------------------------------------------
class WeiboAuthError(Exception):
    """Cookie 无效或登录失效。"""


class WeiboCaptchaError(Exception):
    """触发验证码 (code: -100)，需要人工介入或降级。"""

    def __init__(self, url: str = "", msg: str = "需要验证码"):
        self.url = url
        self.msg = msg
        super().__init__(f"{msg}: {url}")


class WeiboRateLimitError(Exception):
    """触发频率限制或临时封禁 (HTTP 418/403/429)。"""


class WeiboInvalidCookieError(Exception):
    """Cookie 缺失或格式无效。"""


# ---------------------------------------------------------------------------
# 请求客户端
# ---------------------------------------------------------------------------
class WeiboClient:
    def __init__(self, cookie_path: Path = COOKIE_FILE):
        self.cookie_path = Path(cookie_path)
        self._cookies: Dict[str, Any] = self._load_cookies()
        self._client: Optional[httpx.AsyncClient] = None
        self._is_token_refreshing = False
        self._stop_requested = False
        # 供任务管理器进行验证码人工介入回调
        self.on_captcha: Optional[Callable[[str], None]] = None

        self.timeout = httpx.Timeout(30.0, connect=10.0)
        self._client = httpx.AsyncClient(
            headers=self._get_default_headers(),
            timeout=self.timeout,
            follow_redirects=True,
        )

    # -- Cookie -----------------------------------------------------------
    def _load_cookies(self) -> Dict[str, Any]:
        if not self.cookie_path.exists():
            logger.warning("未找到 cookie.json，请先登录导入。")
            return {}
        with open(self.cookie_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and "weibo.cn" in data:
            cookies = data["weibo.cn"]
        else:
            cookies = data
        cookies["MLOGIN"] = 1
        return cookies

    def _save_cookies(self) -> None:
        self.cookie_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.cookie_path, "w", encoding="utf-8") as f:
            json.dump(self._cookies, f, ensure_ascii=False, indent=2)

    @property
    def has_cookie(self) -> bool:
        return bool(self._cookies)

    @property
    def cookie_keys(self) -> list:
        return [k for k in self._cookies.keys() if k != "MLOGIN"]

    def import_cookies(self, cookies: Dict[str, str]) -> None:
        """导入用户提供的 cookie 字典。"""
        new = dict(cookies)
        new["MLOGIN"] = 1
        self._cookies = new
        self._save_cookies()
        logger.info("Cookie 已导入并保存。")

    # -- 请求构建 ----------------------------------------------------------
    @staticmethod
    def _get_default_headers() -> Dict[str, str]:
        return {
            "accept": "application/json, text/plain, */*",
            "accept-language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7",
            "client-version": "v1.1.243",
            "priority": "u=1, i",
            "sec-ch-ua": '"Chromium";v="152", "Not?A_Brand";v="24", "Microsoft Edge";v="152"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Linux"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "server-version": "v2026.08.27.1",
            "user-agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36 Edg/152.0.0.0"
            ),
            "x-requested-with": "XMLHttpRequest",
        }

    def _get_request_headers(self, referer: str = "") -> Dict[str, str]:
        headers: Dict[str, str] = {}
        if referer:
            headers["referer"] = referer
        cookie_str = "; ".join(
            f"{k}={v}" for k, v in self._cookies.items() if k != "MLOGIN"
        )
        headers["cookie"] = cookie_str
        headers["x-xsrf-token"] = self._cookies.get("XSRF-TOKEN", "")
        return headers

    # -- weibo.com AJAX 微博列表 ---------------------------------------------
    async def fetch_statuses(self, uid: int, page: int) -> Dict[str, Any]:
        """调用 weibo.com/ajax/statuses/mymblog 获取一页微博。

        该接口已用真实账号验证可调通，返回 data.list 内的微博对象。
        """
        url = f"https://weibo.com/ajax/statuses/mymblog?uid={uid}&page={page}&feature=0"
        data = await self.get_json(
            url,
            referer=f"https://weibo.com/u/{uid}",
            all_ret=True,
        )
        inner = data.get("data", {}) or {}
        http_code = inner.get("http_code", 200)
        if http_code == 400:
            raise WeiboAuthError("账号受限或需要登录，Cookie 可能失效")
        return inner

    def request_banned(self) -> bool:
        return self._stop_requested

    # -- Token 刷新 --------------------------------------------------------
    async def refresh_token(self) -> Optional[str]:
        if self._is_token_refreshing:
            return self._cookies.get("XSRF-TOKEN")
        self._is_token_refreshing = True
        try:
            self._cookies["_T_WM"] = int(time.time() / 3600) * 100001
            resp = await self._raw_get("https://m.weibo.cn/api/config")
            resp.raise_for_status()
            data = resp.json().get("data", {})
            if not data.get("login", False):
                raise WeiboAuthError("Cookie 无效或未登录")
            new_token = data.get("st")
            if new_token:
                self._cookies["XSRF-TOKEN"] = new_token
                self._save_cookies()
                logger.info("XSRF-TOKEN 刷新成功。")
            return new_token
        finally:
            self._is_token_refreshing = False

    async def _raw_get(self, url: str, referer: str = "") -> httpx.Response:
        await asyncio.sleep(random.uniform(DELAY_MIN, DELAY_MAX))
        return await self._client.get(url, headers=self._get_request_headers(referer))

    # -- 核心请求 (带重试与风控) ---------------------------------------------
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.TimeoutException, WeiboRateLimitError)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    async def _request(self, url: str, referer: str = "") -> httpx.Response:
        resp = await self._raw_get(url, referer)

        if resp.status_code in (418, 403, 429):
            raise WeiboRateLimitError(f"HTTP {resp.status_code}")

        try:
            payload = resp.json()
        except (ValueError, json.JSONDecodeError):
            return resp  # 非 JSON（如直接下载），原样返回

        code = payload.get("code")
        ok = payload.get("ok")

        if code == -100 or ok == -100:
            captcha_url = payload.get("url", "")
            logger.error("触发验证码 (-100): %s", captcha_url)
            if self.on_captcha:
                self.on_captcha(captcha_url)
            raise WeiboCaptchaError(url=captcha_url)

        msg = str(payload.get("msg", ""))
        if ok != 1 and "login" in msg.lower():
            logger.warning("Token 可能过期，尝试刷新。")
            await self.refresh_token()
            raise WeiboRateLimitError("Token expired, retrying")

        return resp

    async def get_json(self, url: str, referer: str = "", all_ret: bool = False) -> Dict[str, Any]:
        """发起请求并返回 JSON。默认只返回 data 字段。"""
        if self._stop_requested:
            raise RuntimeError("任务已停止")
        resp = await self._request(url, referer)
        data = resp.json()
        if all_ret:
            return data
        return data.get("data", {})

    async def download_file(self, url: str, save_path: Path, referer: str = "https://weibo.com/") -> bool:
        """异步流式下载文件。"""
        if save_path.exists() and save_path.stat().st_size > 0:
            return True
        save_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = save_path.with_suffix(save_path.suffix + ".part")
        try:
            async with self._client.stream(
                "GET", url, headers={"referer": referer}, timeout=60.0
            ) as resp:
                resp.raise_for_status()
                with open(tmp_path, "wb") as f:
                    async for chunk in resp.aiter_bytes(chunk_size=8192):
                        await asyncio.sleep(0)  # 让出事件循环
                        f.write(chunk)
            tmp_path.replace(save_path)
            return True
        except Exception as e:
            logger.error("下载失败 %s: %s", url, e)
            if tmp_path.exists():
                tmp_path.unlink()
            return False

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None


# ---------------------------------------------------------------------------
# 获取用户 UID 与 containerid
# ---------------------------------------------------------------------------
async def resolve_container_id(client: WeiboClient) -> tuple[int, str]:
    """通过 /api/config 获取 uid，再解析 profile 得到 containerid(CID)。"""
    data = await client.get_json(
        "https://m.weibo.cn/api/config", referer="https://m.weibo.cn/"
    )
    uid = int(data.get("uid"))
    profile = await client.get_json(
        f"https://m.weibo.cn/profile/info?uid={uid}",
        referer=f"https://m.weibo.cn/profile/{uid}",
    )
    profile = profile.get("user", profile) if "user" in profile else profile
    current_cid = profile.get("containerid")
    if not current_cid:
        # 从 more 字段解析
        more_url = profile.get("more", "") or ""
        current_cid = more_url.rstrip("/").split("/")[-1].split("?")[0]
    cid = str(current_cid).split("?")[0]
    return uid, cid