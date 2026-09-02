"""异步媒体下载器：图片/视频流式下载，特殊封装交给 ffmpeg 转封装。"""
from __future__ import annotations

import asyncio
import logging
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend import workspace
from backend.database import Media, User
from backend.scraper.client import WeiboClient
from backend.utils.logger import get_logger

logger = get_logger("weibo.media")


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


class MediaDownloader:
    def __init__(self, client: WeiboClient, session_factory: async_sessionmaker):
        self.client = client
        self.session_factory = session_factory
        self._semaphore = asyncio.Semaphore(5)
        self._stopped = False

    def stop(self) -> None:
        self._stopped = True

    async def _download_one(self, media: Media) -> None:
        """下载单个媒体，成功后回填 local_path。"""
        async with self._semaphore:
            if media.local_path and Path(media.local_path).exists():
                return
            try:
                target_dir = workspace.video_dir() if media.type in ("video", "livephoto") else workspace.pic_dir()
                target_dir.mkdir(parents=True, exist_ok=True)

                filename = f"{media.post_id}_{media.id}.{media.ext or 'jpg'}"
                target = target_dir / filename
                media.url = media.url
                ext = (media.ext or "").lower()

                if media.type == "pic" and ext in ("jpg", "jpeg", "png", "gif", "webp"):
                    ok = await self.client.download_file(media.url, target)
                elif media.type in ("video", "livephoto"):
                    if ext == "mp4":
                        ok = await self.client.download_file(media.url, target)
                    else:
                        # 特殊封装走 ffmpeg 转 mp4（先下载到本地再转，兼容无网络协议的 ffmpeg）
                        if not ffmpeg_available():
                            logger.warning("未检测到 ffmpeg，跳过特殊视频封装: %s", media.url)
                            return
                        src_tmp = target.with_suffix(target.suffix + ".src")
                        if await self.client.download_file(media.url, src_tmp):
                            ok = await self._ffmpeg_remux(src_tmp, target)
                            if src_tmp.exists():
                                src_tmp.unlink()
                        else:
                            ok = False
                else:
                    ok = await self.client.download_file(media.url, target)

                if ok and target.exists():
                    async with self.session_factory() as db:
                        obj = await db.get(Media, media.id)
                        if obj:
                            obj.local_path = str(target)
                            await db.commit()
                    logger.info("媒体已下载: %s", target.name)
            except Exception as e:
                logger.error("媒体下载失败 id=%s: %s", media.id, e)

    @staticmethod
    async def _ffmpeg_remux(src: Path, target: Path) -> bool:
        cmd = [
            "ffmpeg", "-y", "-i", str(src),
            "-c", "copy", "-bsf:a", "aac_adtstoasc", str(target),
        ]
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.wait_for(proc.wait(), timeout=300)
            return proc.returncode == 0 and target.exists()
        except Exception as e:
            logger.error("ffmpeg 转封装失败: %s", e)
            return False

    async def download_for_posts(self, post_ids: List[int]) -> None:
        """为指定微博的未下载媒体发起下载。"""
        async with self.session_factory() as db:
            result = await db.execute(
                select(Media).where(Media.post_id.in_(post_ids))
            )
            medias = list(result.scalars().all())
        jobs = [
            asyncio.create_task(self._download_one(m))
            for m in medias
            if not (m.local_path and Path(m.local_path).exists())
        ]
        if jobs:
            await asyncio.gather(*jobs, return_exceptions=True)

    async def download_all_missing(self) -> int:
        """下载所有尚未下载的媒体（含转发的原博图片）。返回本次新增下载数。"""
        async with self.session_factory() as db:
            result = await db.execute(
                select(Media).where(
                    (Media.local_path.is_(None)) | (Media.local_path == "")
                )
            )
            medias = list(result.scalars().all())
        for m in medias:
            await self._download_one(m)
        return len(medias)

    async def download_avatars(self, limit: int = 300) -> int:
        """下载所有未下载的用户头像，返回本次新增下载数。"""
        async with self.session_factory() as db:
            result = await db.execute(
                select(User).where(
                    User.profile_image_url.is_not(None),
                    User.profile_image_url != "",
                ).limit(limit)
            )
            users = list(result.scalars().all())

        avatar_dir = workspace.avatar_dir()
        avatar_dir.mkdir(parents=True, exist_ok=True)
        got = 0

        async def _one(user: User):
            nonlocal got
            if self._stopped:
                return
            target = avatar_dir / f"{user.id}.jpg"
            if user.avatar_local and Path(user.avatar_local).exists():
                return
            try:
                async with self._semaphore:
                    ok = await self.client.download_file(user.profile_image_url, target)
                if ok and target.exists():
                    async with self.session_factory() as db:
                        obj = await db.get(User, user.id)
                        if obj:
                            obj.avatar_local = str(target)
                            await db.commit()
                    got += 1
            except Exception as e:
                logger.warning("头像下载失败 uid=%s: %s", user.id, e)

        jobs = [asyncio.create_task(_one(u)) for u in users]
        if jobs:
            await asyncio.gather(*jobs, return_exceptions=True)
        return got