"""异步归档任务调度中心：状态机、断点续传、WebSocket 实时广播。"""
from __future__ import annotations

import asyncio
import logging
import time
from enum import Enum
from typing import Any, Dict, Optional, Set

from fastapi import WebSocket
from pydantic import BaseModel

from backend.config import CONCURRENCY, MAX_PAGES
from backend.database import (
    AsyncSessionLocal, Comment, Post, User, func, select, set_db_target,
)
from backend.scraper.client import (
    WeiboAuthError,
    WeiboCaptchaError,
    WeiboClient,
    WeiboRateLimitError,
    resolve_container_id,
)
from backend.scraper.media_downloader import MediaDownloader
from backend.scraper.parser import WeiboParser
from backend.utils.logger import get_logger, mask_cookie

logger = get_logger("weibo.task")


# ---------------------------------------------------------------------------
# 状态与消息
# ---------------------------------------------------------------------------
class TaskStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED_CAPTCHA = "paused_captcha"
    STOPPED = "stopped"
    COMPLETED = "completed"
    FAILED = "failed"


class WSMessageType(str, Enum):
    LOG = "log"
    PROGRESS = "progress"
    STATUS = "status"
    CAPTCHA = "captcha"
    ERROR = "error"


class WSMessage(BaseModel):
    type: WSMessageType
    data: Any
    timestamp: float = time.time()


# ---------------------------------------------------------------------------
# 任务管理器
# ---------------------------------------------------------------------------
class ArchiveTaskManager:
    def __init__(self):
        self.status: TaskStatus = TaskStatus.IDLE
        self.current_uid: Optional[int] = None

        self._task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()
        self._resume_event = asyncio.Event()
        self._resume_event.set()

        self.total_fetched = 0
        self.current_page = 0

        self.active_connections: Set[WebSocket] = set()
        self.client: Optional[WeiboClient] = None
        self._progress_lock = asyncio.Lock()

    # -- WebSocket ---------------------------------------------------------
    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.add(websocket)
        await self._send_ws(WSMessage(type=WSMessageType.STATUS, data=self.status))

    def disconnect(self, websocket: WebSocket) -> None:
        self.active_connections.discard(websocket)

    async def _send_ws(self, message: WSMessage) -> None:
        if not self.active_connections:
            return
        dead: Set[WebSocket] = set()
        for conn in list(self.active_connections):
            try:
                await conn.send_json(message.model_dump())
            except Exception:
                dead.add(conn)
        self.active_connections -= dead

    async def log(self, msg: str, level: str = "info") -> None:
        msg = mask_cookie(msg)
        if level == "error":
            logging.getLogger("weibo.task").error(msg)
            await self._send_ws(WSMessage(type=WSMessageType.ERROR, data=msg))
        else:
            logging.getLogger("weibo.task").info(msg)
            await self._send_ws(WSMessage(type=WSMessageType.LOG, data=msg))

    async def push_progress(self) -> None:
        async with self._progress_lock:
            await self._send_ws(
                WSMessage(
                    type=WSMessageType.PROGRESS,
                    data={"page": self.current_page, "total_fetched": self.total_fetched},
                )
            )

    # -- 生命周期控制 ------------------------------------------------------
    async def start(self, uid: Optional[int] = None) -> None:
        if self.status == TaskStatus.RUNNING:
            await self.log("任务已在运行中。", "error")
            return
        self._stop_event.clear()
        self._resume_event.set()
        self.total_fetched = 0
        self.current_page = 0
        self.client = WeiboClient()
        self.client.on_captcha = None  # captcha 由本管理器统一处理，见 _on_captcha
        self._task = asyncio.create_task(self._archive_loop(uid))
        self.status = TaskStatus.RUNNING
        await self._send_ws(WSMessage(type=WSMessageType.STATUS, data=self.status))
        await self.log("🚀 归档任务已启动。")

    async def stop(self) -> None:
        if self.status not in (TaskStatus.RUNNING, TaskStatus.PAUSED_CAPTCHA):
            return
        await self.log("🛑 正在安全停止任务…")
        self._stop_event.set()
        self._resume_event.set()
        if self._task:
            try:
                await asyncio.wait_for(asyncio.shield(self._task), timeout=15.0)
            except (asyncio.TimeoutError, Exception):
                self._task.cancel()
        self.status = TaskStatus.STOPPED
        await self._send_ws(WSMessage(type=WSMessageType.STATUS, data=self.status))

    async def pause_for_captcha(self, captcha_url: str) -> None:
        self.status = TaskStatus.PAUSED_CAPTCHA
        self._resume_event.clear()
        await self._send_ws(WSMessage(type=WSMessageType.STATUS, data=self.status))
        await self._send_ws(WSMessage(type=WSMessageType.CAPTCHA, data=captcha_url))
        await self.log(f"⚠️ 触发风控，请完成验证码后恢复。", "error")

    async def resume(self) -> None:
        if self.status != TaskStatus.PAUSED_CAPTCHA:
            return
        self.status = TaskStatus.RUNNING
        self._resume_event.set()
        await self._send_ws(WSMessage(type=WSMessageType.STATUS, data=self.status))
        await self.log("✅ 验证码已处理，恢复抓取…")

    # -- 评论补齐阶段 ------------------------------------------------------
    async def _fetch_comments_phase(self, parser: WeiboParser, semaphore: asyncio.Semaphore):
        """为所有评论未抓全的微博抓取一二级评论。幂等，可反复补齐。"""
        await self.log("💬 开始抓取评论…")
        pending: list[Post] = []
        async with AsyncSessionLocal() as db:
            rows = (await db.execute(
                select(Post).where(Post.comments_count > 0, Post.is_own == True)
            )).scalars().all()
            pending_posts = []
            for p in rows:
                got = await db.scalar(select(func.count()).select_from(Comment).where(Comment.post_id == p.id))
                if (got or 0) < p.comments_count:
                    pending_posts.append(p)
            if not pending_posts:
                await self.log("✅ 无需补抓评论（均已抓全）。")
                return
            pending = pending_posts

        async def _do(post: Post):
            if self._stop_event.is_set():
                return
            async with semaphore:
                async with AsyncSessionLocal() as db:
                    try:
                        n = await parser.fetch_comments(db, post)
                        await db.commit()
                        if n:
                            await self.log(f"    ✓ post {post.mid}: 新增评论 {n}")
                    except WeiboRateLimitError:
                        await self.log(f"⚠️ 评论限流于 {post.mid}，跳过本微博。", "error")
                    except Exception as e:
                        await self.log(f"⚠️ 评论失败 {post.mid}: {mask_cookie(str(e))}", "error")

        total = len(pending)
        done = 0
        chunk = 8
        for i in range(0, total, chunk):
            batch = pending[i:i + chunk]
            await asyncio.gather(*(_do(p) for p in batch))
            done += len(batch)
            await self.push_progress()
            await asyncio.sleep(1)
        await self.log(f"💬 评论补齐结束，覆盖 {total} 条微博。")

    # -- 抓取循环 ----------------------------------------------------------
    async def _archive_loop(self, uid: Optional[int]):
        if uid is None:
            try:
                resolved_uid, _ = await resolve_container_id(self.client)
                uid = resolved_uid
            except Exception:
                uid = 0
        parser = WeiboParser(self.client, uid=uid or None)
        downloader = MediaDownloader(self.client, AsyncSessionLocal)
        semaphore = asyncio.Semaphore(CONCURRENCY)

        try:
            if not self.client.has_cookie:
                raise RuntimeError("未导入 Cookie，请先登录导入。")
            if not uid:
                raise RuntimeError("无法解析登录 UID，请在启动接口传入 uid")
            self.current_uid = uid
            self._save_state()
            # 切换目标用户的工作区(独立 DB + 媒体目录)
            await set_db_target(uid)

            # 记录用户信息
            async with AsyncSessionLocal() as db:
                await parser.fetch_and_save_profile(db, self.current_uid)

            new_post_ids: list = []
            # 断点续抓：把已归档的本人微博 mid 载入 seen_ids，
            # 重跑时跳过已抓内容，继续向后翻页补抓缺失微博
            async with AsyncSessionLocal() as db:
                rows = await db.execute(select(Post.mid).where(Post.is_own.is_(True)))
                seen_ids = {str(mid) for mid in rows.scalars().all()}
            if seen_ids:
                await self.log(f"↩️ 检测到已有 {len(seen_ids)} 条归档，继续向后翻页补抓…")
            page = 0

            while not self._stop_event.is_set():
                await self._resume_event.wait()
                if self._stop_event.is_set():
                    break

                page += 1
                self.current_page = page

                try:
                    async with semaphore:
                        inner = await self.client.fetch_statuses(self.current_uid, page)
                except WeiboCaptchaError as e:
                    await self.pause_for_captcha(e.url)
                    continue
                except WeiboRateLimitError:
                    await self.log("⚠️ 频率受限，30 秒后重试…", "error")
                    await asyncio.sleep(30)
                    continue
                except WeiboAuthError as e:
                    await self.log(f"💥 {e}", "error")
                    raise

                statuses = inner.get("list", []) or []
                if not statuses:
                    await self.log("🎉 已抓取全部内容，归档完成。")
                    break

                page_new = 0
                for raw_post in statuses:
                    mid = raw_post.get("idstr") or raw_post.get("mid") or raw_post.get("id")
                    if not mid or str(mid) in seen_ids:
                        continue
                    seen_ids.add(str(mid))
                    async with AsyncSessionLocal() as db:
                        post = await parser.parse_post(db, raw_post)
                        await db.commit()
                        if post:
                            new_post_ids.append(post.id)
                            page_new += 1
                            self.total_fetched += 1

                await self.log(
                    f"📄 第 {page} 页完成，本页新增 {page_new} 条，累计 {self.total_fetched} 条。"
                )
                await self.push_progress()

                if MAX_PAGES and page >= MAX_PAGES:
                    break
                # 注意：不能以"本页无新增"作为终止条件。
                # 断点续抓时前几页都是已归档内容（新增 0 条），
                # 若在此 break 将永远到不了缺失的旧微博页。
                # 终止只依赖接口返回空列表（已抓取全部内容）。

            # 评论补齐阶段：为所有评论未抓全的微博抓取一二级评论
            if not self._stop_event.is_set():
                await self._fetch_comments_phase(parser, semaphore)

            # 头像下载：归档用户及所有互动用户的头像
            if not self._stop_event.is_set():
                await self.log("🖼️ 开始下载用户头像…")
                n_avatar = await downloader.download_avatars(limit=10000)
                await self.log(f"✅ 头像下载完成，新增 {n_avatar} 个。")

            # 媒体补齐：为历史微博补抓缺失媒体（如旧版未解析出的视频）
            if not self._stop_event.is_set():
                async with AsyncSessionLocal() as db:
                    n_backfill = await parser.backfill_missing_fields(db)
                    await db.commit()
                if n_backfill:
                    await self.log(f"🎬 媒体补齐完成，新增 {n_backfill} 个媒体记录。")

            # 后台补充：媒体下载（含转发的原博图片）
            if not self._stop_event.is_set():
                await self.log("📦 开始下载媒体文件…")
                n_media = await downloader.download_all_missing()
                await self.log(f"✅ 媒体下载完成，本次新增 {n_media} 个。")
                await self.push_progress()

            if self.status == TaskStatus.RUNNING:
                self.status = TaskStatus.COMPLETED
                await self.log("🏁 归档任务圆满完成！")

        except asyncio.CancelledError:
            await self.log("任务被取消。")
        except Exception as e:
            self.status = TaskStatus.FAILED
            await self.log(f"💥 任务失败: {mask_cookie(str(e))}", "error")
        finally:
            await self._send_ws(WSMessage(type=WSMessageType.STATUS, data=self.status))
            if self.client:
                await self.client.close()

    def _save_state(self) -> None:
        pass


# ---------------------------------------------------------------------------
# 全局单例
# ---------------------------------------------------------------------------
task_manager = ArchiveTaskManager()