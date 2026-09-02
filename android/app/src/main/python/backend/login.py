"""原生 CDP 扫码登录：外部启动 Edge + websocket CDP，无需 DrissionPage。

背景：新浪已收紧匿名 SSO 接口，纯 httpx 无法取到二维码；而 DrissionPage 4.1 与本机
Edge 152 存在兼容缺陷（初始化会对同一 /devtools/browser/<id> 建第二条 ws 被 404 拒绝）。
经实测，原生 CDP websocket 连接稳定，故本模块直接用 websocket-client 实现 CDP 控制：

  1. start()   外部启动 Edge(指定调试端口+专属 profile)，导航到微博扫码登录页，
                用 Runtime.evaluate 提取二维码 <img>（data:image 或 URL）生成 PNG 回传前端
  2. status()  轮询 document.cookie 是否出现 SUB（登录成功）
  3. confirm() 登录成功后用 Network.getAllCookies 导出 Cookie，交账号管理保存并关停浏览器

本模块接口与 QrLoginManager 保持：start/status/confirm/drop_session，端侧代码无需改动。
"""
from __future__ import annotations

import asyncio
import base64
import json
import os
import shutil
import socket
import subprocess
import threading
import time
import urllib.request
import uuid
from concurrent.futures import Future
from pathlib import Path
from typing import Any, Dict, Optional

from backend.config import WORKSPACE_DIR, is_android
from backend.utils.logger import get_logger

logger = get_logger("weibo.login")

# 全局开关：测试用 headless（生产/桌面默认有头，供用户扫码）
_HEADLESS = False

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36 Edg/152.0.0.0"
    ),
    "Referer": "https://m.weibo.cn/",
    "Accept": "application/json, text/plain, */*",
}

# 微博移动端扫码登录页
LOGIN_URL = (
    "https://passport.weibo.cn/signin/login?entry=mweibo&res=wel&wm=3349"
    "&r=https%3A%2F%2Fm.weibo.cn"
)
QR_CACHE_DIR = WORKSPACE_DIR / "qr_cache"
# 浏览器用户数据目录（内含登录 Cookie），放在非静态服务目录之外，避免被 /media 路由暴露
BROWSER_DATA_DIR = WORKSPACE_DIR.parent / ".weibo_browser_profiles"

TTL = 180  # 会话有效期（秒）
_LOGIN_COOKIES = ("SUB", "SUBSCRIBE", "gsid")

# 提取二维码图片 src 的 JS：尝试多种容器/特征
_QR_EXTRACT_JS = r"""(() => {
  const imgs = Array.from(document.querySelectorAll('img'));
  const hit = imgs.find(im => {
    const s = (im.src || '');
    const alt = (im.alt || '');
    const cls = (im.className || '') + ' ' + (im.id || '');
    return /qrcode|qr_code|qrimg|qrcodeimg/i.test(alt + ' ' + cls)
      || (s.startsWith('data:image') && s.length > 500)
      || /qrcode|qrlogin|qr\/|qrcoderemind|\/qr\//i.test(s);
  });
  return hit ? { src: hit.src } : { src: '' };
})()
"""

# 扫码弹窗自定义隐私与安全提示（替换浏览器窗口中的占位文本）
# 微博 passport 页面占位文本为小写且分两行，匹配忽略大小写、用特征短语（避免误伤真实内容）
_PLACEHOLDER_MARKERS = (
    "this space intentionally",
    "in official builds this space",
)
_PRIVACY_HTML = (
    '<div style="font-family:\'Microsoft YaHei\',sans-serif;max-width:360px;'
    "margin:0 auto;padding:16px;background:#ffffff;border:1px solid #e5e7eb;"
    "border-radius:8px;color:#111827;font-size:13px;line-height:1.7\">"
    '<div style="font-weight:700;font-size:14px;margin-bottom:8px">🔒 隐私与安全说明</div>'
    "<ul style=\"margin:0;padding-left:18px\">"
    "<li><b>数据仅存本地</b>：您的微博账号信息（Cookie、UID、昵称等）仅保存在您的本地设备中，不会上传至任何第三方服务器。</li>"
    "<li><b>安全可靠</b>：本工具通过浏览器原生协议（CDP）完成登录流程，不经过任何中间服务器，与您在浏览器中正常登录微博无异。</li>"
    "<li><b>自主可控</b>：您可随时在「账号管理」中退出登录，一键清除所有登录态数据。</li>"
    "</ul>"
    '<div style="margin-top:8px">扫码即表示您已了解并同意上述说明。</div>'
    "</div>"
)
# 注入 JS（幂等 + 多 frame 递归）：遍历各文档文本节点，将占位文本替换为自定义提示；
# 占位文本可能位于 iframe（passport.weibo.com 登录框），且大小写不定，匹配忽略大小写
_INJECT_PRIVACY_JS = r"""(() => {
  const markers = (window.__WBAR_MARKERS__ || []).map(m => m.toLowerCase());
  let replaced = 0;
  function processRoot(doc) {
    if (!doc || !doc.body || doc.getElementById('wbar-privacy-panel')) return;
    const nodes = [];
    const walker = doc.createTreeWalker(doc.body, NodeFilter.SHOW_TEXT);
    let n;
    while ((n = walker.nextNode())) {
      const v = (n.nodeValue || '').toLowerCase();
      if (markers.some(m => v.indexOf(m) !== -1)) nodes.push(n);
    }
    nodes.forEach((tn) => {
      replaced++;
      if (tn.parentNode) {
        if (replaced === 1) {
          const el = doc.createElement('div');
          el.id = 'wbar-privacy-panel';
          el.innerHTML = window.__WBAR_PRIVACY__ || '';
          tn.parentNode.replaceChild(el, tn);
        } else {
          tn.nodeValue = '';
        }
      }
    });
    Array.from(doc.querySelectorAll('iframe')).forEach(f => {
      try { if (f.contentDocument) processRoot(f.contentDocument); } catch (e) {}
    });
  }
  processRoot(document);
  return { injected: replaced > 0, replaced };
})()
"""


class QrLoginError(Exception):
    pass


# ---------------------------------------------------------------------------
# 极简 CDP 会话：JSON-RPC over websocket（同步请求 + 后台接收线程）
# ---------------------------------------------------------------------------
class CdpSession:
    def __init__(self, ws_url: str):
        import websocket

        self._ws = websocket.create_connection(
            ws_url, timeout=30, enable_multithread=True, suppress_origin=True
        )
        self._seq = 0
        self._lock = threading.Lock()
        self._pending: Dict[int, Future] = {}
        self._reader = threading.Thread(target=self._recv_loop, daemon=True)
        self._reader.start()

    def _recv_loop(self) -> None:
        while True:
            try:
                msg = json.loads(self._ws.recv())
            except Exception:
                break
            if isinstance(msg, dict) and "id" in msg:
                fut = self._pending.pop(msg["id"], None)
                if fut and not fut.done():
                    fut.set_result(msg)

    def call(self, method: str, params: Optional[dict] = None, timeout: int = 30) -> dict:
        with self._lock:
            self._seq += 1
            mid = self._seq
            fut: Future = Future()
            self._pending[mid] = fut
            self._ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
        res = fut.result(timeout)
        if "error" in res:
            raise QrLoginError(f"CDP {method} 失败: {res['error']}")
        return res.get("result", {})

    def eval(self, expression: str, timeout: int = 30) -> Any:
        res = self.call(
            "Runtime.evaluate",
            {"expression": expression, "returnByValue": True, "awaitPromise": True},
            timeout=timeout,
        )
        exc = res.get("exceptionDetails")
        if exc:
            raise QrLoginError(f"JS 执行失败: {exc.get('text', '')} {exc.get('exception')}")
        value = res.get("result", {}).get("value")
        return json.loads(value) if isinstance(value, str) and _is_json(value) else value

    def close(self) -> None:
        try:
            self._ws.close()
        except Exception:
            pass


def _is_json(s: str) -> bool:
    try:
        json.loads(s)
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# 浏览器启动
# ---------------------------------------------------------------------------
def _find_browser() -> str:
    """探测本机可用浏览器（Chrome/Edge 常见路径），找不到返回空串。"""
    candidates = [
        "google-chrome", "chromium", "chromium-browser", "microsoft-edge", "msedge",
    ]
    for c in candidates:
        p = shutil.which(c)
        if p:
            return p
    for c in [
        "/usr/bin/google-chrome", "/usr/bin/chromium", "/usr/bin/chromium-browser",
        "/usr/bin/microsoft-edge", "/opt/google/chrome/chrome",
        "C:/Program Files/Google/Chrome/Application/chrome.exe",
        "C:/Program Files (x86)/Google/Chrome/Application/chrome.exe",
        "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
        "C:/Program Files/Microsoft/Edge/Application/msedge.exe",
    ]:
        if Path(c).exists():
            return c
    return ""


def _is_root() -> bool:
    """判断是否以 root 身份运行（POSIX）。Windows 恒为 False。"""
    try:
        return os.geteuid() == 0
    except Exception:
        return False


def _terminate_browser(proc) -> None:
    import signal

    try:
        proc.send_signal(signal.SIGTERM)
        proc.wait(timeout=5)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


def _start_browser() -> tuple:
    """外部启动 Edge/Chrome，返回 (CdpSession, proc, port, profile)。"""
    browser = _find_browser()
    if not browser:
        raise QrLoginError("未探测到 Chrome/Edge，无法进行扫码登录。")

    profile = BROWSER_DATA_DIR / uuid.uuid4().hex[:16]
    profile.mkdir(parents=True, exist_ok=True)

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]

    cmd = [
        browser,
        f"--remote-debugging-port={port}",
        f"--user-data-dir={profile}",
        "--disable-gpu",
        "--disable-dev-shm-usage",
        # 抑制 “不受支持的命令行标志” 等信息条
        "--disable-infobars",
        # 用全新 profile 启动时抑制 Edge/Chrome 自带的首启·附加条款·欢迎页，
        # 避免弹出 "This space intentionally blank" 占位框与登录页并存
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-background-networking",
        "--disable-sync",
        "--disable-features=msEdgeFirstRunExperience,msEdgeFirstRunExperienceOptIn",
    ]
    # 仅在以 root 运行时需要 --no-sandbox；普通用户桌面相加会触发
    # “不受支持的命令行标志:--no-sandbox” 警告条，故只在 root 下追加
    if _is_root():
        cmd.append("--no-sandbox")
    if _HEADLESS:
        cmd.append("--headless=new")
    cmd.append("about:blank")
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            start_new_session=True)

    # 等待产生一个 page 标签并拿到其 ws 地址
    page_ws = None
    for _ in range(40):
        try:
            tabs = json.loads(urllib.request.urlopen(
                f"http://127.0.0.1:{port}/json", timeout=1).read())
            for t in tabs:
                if t.get("type") == "page" and t.get("webSocketDebuggerUrl"):
                    page_ws = t["webSocketDebuggerUrl"]
                    break
        except Exception:
            pass
        if page_ws:
            break
        time.sleep(0.5)
    if not page_ws:
        _terminate_browser(proc)
        raise QrLoginError("浏览器启动超时，无法建立调试连接。")

    try:
        page = CdpSession(page_ws)
    except Exception as e:
        _terminate_browser(proc)
        raise QrLoginError(f"连接浏览器失败：{e}")

    # 关闭其它多余的 page 标签（如首启/附加条款页），只保留即将导航的登录页
    try:
        tabs = json.loads(urllib.request.urlopen(
            f"http://127.0.0.1:{port}/json", timeout=1).read())
        for t in tabs:
            if t.get("type") == "page" and t.get("webSocketDebuggerUrl") != page_ws:
                tid = t.get("id")
                if tid:
                    try:
                        urllib.request.urlopen(
                            f"http://127.0.0.1:{port}/json/close/{tid}", timeout=1).read()
                    except Exception:
                        pass
    except Exception:
        pass

    page._launcher_proc = proc
    page._launcher_port = port
    page._launcher_profile = profile
    return page, proc, port, profile


def _set_headless(flag: bool = True) -> None:
    """测试用：设置是否以 headless 方式启动浏览器。"""
    global _HEADLESS
    _HEADLESS = flag


# ---------------------------------------------------------------------------
# 扫码页操作
# ---------------------------------------------------------------------------
def _navigate(page: CdpSession, url: str) -> None:
    page.call("Page.navigate", {"url": url}, timeout=30)
    try:
        page.call("Page.bringToFront")
    except Exception:
        pass
    # 等待页面基本加载
    for _ in range(40):
        try:
            val = page.eval("document.readyState || ''")
            if val == "complete":
                break
        except Exception:
            pass
        time.sleep(0.5)


def _inject_privacy(page: CdpSession) -> bool:
    """在浏览器登录页注入自定义隐私/安全提示，替换占位文本。返回是否执行成功。"""
    try:
        page.eval("window.__WBAR_MARKERS__ = " + json.dumps(list(_PLACEHOLDER_MARKERS)))
        page.eval("window.__WBAR_PRIVACY__ = " + json.dumps(_PRIVACY_HTML))
        res = page.eval(_INJECT_PRIVACY_JS, timeout=5)
        return bool(res and res.get("injected"))
    except Exception as e:
        logger.warning("隐私提示注入失败（不影响扫码）：%s", e)
        return False


def _capture_qr(page: CdpSession, qr_png: Path) -> Optional[str]:
    """提取二维码图片写入 qr_png，返回 /media/ 相对地址；失败返回 None。"""
    qr_png.parent.mkdir(parents=True, exist_ok=True)
    # 等待二维码出现（登录页二维码常需 1~3s 渲染）
    src = None
    for _ in range(15):
        try:
            src = page.eval(_QR_EXTRACT_JS, timeout=5)
            if src and src.get("src"):
                break
        except Exception:
            pass
        time.sleep(0.5)
    if src and src.get("src"):
        img_src = src["src"]
        try:
            if img_src.startswith("data:"):
                b64 = img_src.split(",", 1)[1]
                qr_png.write_bytes(base64.b64decode(b64))
            else:
                # 非 data URL 则原样下载
                url = img_src if img_src.startswith("http") else f"https:{img_src}"
                req = urllib.request.Request(url, headers=_HEADERS)
                qr_png.write_bytes(urllib.request.urlopen(req, timeout=15).read())
            if qr_png.exists() and qr_png.stat().st_size > 200:
                return "/media/" + qr_png.relative_to(WORKSPACE_DIR).as_posix()
        except Exception as e:
            logger.warning("二维码图片获取失败：%s", e)
    # 兜底：整页截图
    try:
        res = page.call("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": True})
        if res.get("data"):
            qr_png.write_bytes(base64.b64decode(res["data"]))
            if qr_png.exists() and qr_png.stat().st_size > 200:
                return "/media/" + qr_png.relative_to(WORKSPACE_DIR).as_posix()
    except Exception as e:
        logger.warning("整页截图失败：%s", e)
    return None


def _all_cookies(page: CdpSession) -> Dict[str, str]:
    """优先用 Network.getAllCookies 读取（含 HttpOnly 凭证），失败回退 document.cookie。"""
    try:
        page.call("Network.enable")
    except Exception:
        pass
    try:
        res = page.call("Network.getAllCookies")
        cookies = {
            c["name"]: c.get("value", "")
            for c in res.get("cookies", [])
            if c.get("name")
        }
        if "SUB" in cookies or "gsid" in cookies or "SUBSCRIBE" in cookies:
            return cookies
    except Exception:
        pass
    # 兜底：当前页面 document.cookie
    cookies = {}
    try:
        for item in (page.eval("document.cookie || ''") or "").split(";"):
            if "=" in item:
                k, _, v = item.strip().partition("=")
                cookies[k.strip()] = v.strip()
    except Exception:
        pass
    return cookies


def _has_auth_cookie(cookies: Dict[str, str]) -> bool:
    return any(k in cookies for k in _LOGIN_COOKIES)


def _browser_logged_in(page: CdpSession) -> bool:
    try:
        if _has_auth_cookie(_all_cookies(page)):
            return True
    except Exception:
        pass
    try:
        url = page.eval("location.href || ''", timeout=5) or ""
        if url and "passport.weibo" not in url and "passport.sina" not in url:
            # 已离开登录页视为登录成功（凭证可能为 HttpOnly，无法以 document.cookie 读取）
            return True
    except Exception:
        pass
    return False


def _extract_cookies(page: CdpSession) -> Dict[str, str]:
    cookies = _all_cookies(page)
    cookies.setdefault("MLOGIN", "1")
    if not _has_auth_cookie(cookies):
        raise QrLoginError("未读取到有效微博登录 Cookie（缺少 SUB/gsid 凭证），请重试扫码")
    return cookies


# ---------------------------------------------------------------------------
# 会话管理
# ---------------------------------------------------------------------------
class QrLoginManager:
    def __init__(self, ttl: int = TTL):
        self._sessions: Dict[str, dict] = {}
        self._ttl = ttl

    def _cleanup(self) -> None:
        now = time.time()
        expired = [k for k, v in self._sessions.items() if now - v["created"] >= self._ttl]
        for sid in expired:
            self.drop(sid)

    def drop(self, sid: str) -> None:
        sess = self._sessions.pop(sid, None)
        if not sess or sess.get("page") is None:
            return
        page = sess["page"]
        try:
            page.close()
        except Exception:
            pass
        proc = getattr(page, "_launcher_proc", None)
        if proc is not None:
            _terminate_browser(proc)

    # -- 内部阻塞实现（线程中执行） --------------------------------------
    def _start_sync(self, sid: str, qr_png: Path) -> dict:
        if is_android():
            # Android：无桌面浏览器，由原生 WebView 登录页完成扫码/账号登录，
            # 登录成功后由 native 端调用 complete() 回填 Cookie
            self._sessions[sid] = {
                "sid": sid, "page": None, "qr_url": None,
                "qr_in_browser": True, "state": "wait", "created": time.time(),
                "android_webview": True,
            }
            return {
                "sid": sid,
                "qr_in_browser": True,
                "android_webview": True,
                "qr_url": "",
                "expires_in": self._ttl,
                "msg": "正在打开登录页面，请完成扫码或账号密码登录…",
            }
        page, _proc, _port, _profile = _start_browser()
        try:
            _navigate(page, LOGIN_URL)
            _inject_privacy(page)
        except Exception as e:
            self.drop(sid)
            raise QrLoginError(f"打开登录页失败：{e}")
        qr_url = _capture_qr(page, qr_png)
        # 重定向/风控页渲染后可能晚出占位文本，幂等再注入一次
        try:
            _inject_privacy(page)
        except Exception:
            pass
        self._sessions[sid] = {
            "sid": sid, "page": page, "qr_url": qr_url,
            "qr_in_browser": qr_url is None, "state": "wait", "created": time.time(),
        }
        return {
            "sid": sid,
            "qr_in_browser": qr_url is None,
            "qr_url": qr_url or "",
            "expires_in": self._ttl,
            "msg": (
                "已打开浏览器登录窗口；若前端未显示二维码，请直接在浏览器窗口中完成扫码。"
                if qr_url is None
                else "请用手机微博 App 扫码并确认，然后回到应用内等待登录完成。"
            ),
        }

    def _status_sync(self, sess: dict) -> dict:
        if sess.get("android_webview"):
            # Android：状态由 native 端通过 complete() 更新
            if sess.get("state") == "confirmed":
                return {"state": "confirmed", "msg": "已登录，正在获取 Cookie…"}
            return {"state": "wait", "msg": "等待登录…"}
        page = sess.get("page")
        if page is None:
            return {"state": "expired", "msg": "浏览器已关闭，请重新发起扫码"}
        if _browser_logged_in(page):
            sess["state"] = "confirmed"
            return {"state": "confirmed", "msg": "已登录，正在获取 Cookie…"}
        return {"state": "wait", "msg": "等待扫码并确认…"}

    def _confirm_sync(self, sess: dict) -> dict:
        if sess.get("android_webview"):
            cookies = sess.get("cookies")
            if not cookies:
                raise QrLoginError("尚未检测到登录成功，请先在登录页面完成登录")
            return {"ok": True, "cookies": cookies}
        page = sess.get("page")
        if page is None:
            raise QrLoginError("浏览器已关闭，请重新发起扫码")
        if not _browser_logged_in(page):
            raise QrLoginError(
                "尚未在浏览器中检测到登录成功，请确认手机微博 App 已扫码并在手机上"
                "点击「确认登录」，等浏览器跳转后再试"
            )
        cookies = _extract_cookies(page)
        return {"ok": True, "cookies": cookies}

    # -- 对外 async 接口 ------------------------------------------------
    async def start(self) -> dict:
        self._cleanup()
        sid = uuid.uuid4().hex[:16]
        qr_png = QR_CACHE_DIR / f"{sid}.png"
        res = await asyncio.to_thread(self._start_sync, sid, qr_png)
        res["sid"] = sid
        return res

    async def status(self, sid: str) -> dict:
        sess = self._sessions.get(sid)
        if sess is None:
            return {"state": "expired", "msg": "会话已失效，请重新发起扫码"}
        return await asyncio.to_thread(self._status_sync, sess)

    async def confirm(self, sid: str) -> dict:
        sess = self._sessions.get(sid)
        if sess is None:
            raise QrLoginError("会话不存在或已过期，请重新发起扫码")
        res = await asyncio.to_thread(self._confirm_sync, sess)
        self.drop(sid)
        return res

    def drop_session(self, sid: str) -> None:
        self.drop(sid)

    def complete(self, sid: str, cookies: Dict[str, str]) -> bool:
        """Android native 端登录成功后回填 Cookie 并标记为已确认。"""
        sess = self._sessions.get(sid)
        if sess is None:
            return False
        sess["cookies"] = dict(cookies)
        sess["state"] = "confirmed"
        return True


qr_login = QrLoginManager()


# 兼容：模块级开关，供测试设置 headless
def _enable_headless() -> None:
    _set_headless(True)