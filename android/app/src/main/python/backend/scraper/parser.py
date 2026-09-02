"""微博脏数据解析与入库：用户、微博、长文、媒体、评论树。"""
from __future__ import annotations

import ast
import hashlib
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.database import Comment, Media, Post, User, clean_and_tokenize
from backend.scraper.client import WeiboClient, WeiboRateLimitError
from backend.utils.logger import get_logger

logger = get_logger("weibo.parser")

# 每条微博最多抓取的评论页数（每页20条）。防止爆款博(几十万评论)拉飞。
COMMENT_MAX_PAGES = 20


def _ext_from_url(url: str) -> str:
    if not url:
        return ""
    path = urlparse(url).path
    if "." not in path:
        return ""
    return path.rsplit(".", 1)[-1].lower()


def parse_weibo_time(time_str: Optional[str]) -> datetime:
    """解析微博各种时间格式。"""
    now = datetime.now()
    if not time_str:
        return now
    time_str = time_str.strip()
    try:
        if "刚刚" in time_str:
            return now
        if "分钟前" in time_str:
            return now - timedelta(minutes=int(time_str.split("分钟前")[0]))
        if "小时前" in time_str:
            return now - timedelta(hours=int(time_str.split("小时前")[0]))
        if "今天" in time_str:
            t = time_str.replace("今天", "").strip()
            return datetime.strptime(f"{now:%Y-%m-%d} {t}", "%Y-%m-%d %H:%M")
        if "昨天" in time_str:
            t = time_str.replace("昨天", "").strip()
            yesterday = now - timedelta(days=1)
            return datetime.strptime(f"{yesterday:%Y-%m-%d} {t}", "%Y-%m-%d %H:%M")
        # "MM-DD" 补全当前年份
        if "-" in time_str and len(time_str) <= 5:
            return datetime.strptime(f"{now.year}-{time_str}", "%Y-%m-%d")
        for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d", "%a %b %d %H:%M:%S %z %Y"):
            try:
                return datetime.strptime(time_str, fmt)
            except ValueError:
                continue
    except Exception as e:
        logger.warning("时间解析失败 %r: %s", time_str, e)
    return now


def _parse_raw_json(raw_json: str) -> Optional[Dict[str, Any]]:
    """解析库中 raw_json（可能是 JSON 或 Python repr 两种历史格式）。"""
    if not raw_json:
        return None
    try:
        return json.loads(raw_json)
    except (ValueError, TypeError):
        pass
    try:
        value = ast.literal_eval(raw_json)
        return value if isinstance(value, dict) else None
    except (ValueError, SyntaxError):
        return None


def _pick_video_url(data: Dict[str, Any]) -> str:
    """从视频 data 中挑选最高清晰度可用的 mp4 地址（playback_list 优先）。"""
    media_info = data.get("media_info") or {}
    playback = media_info.get("playback_list") or data.get("playback_list") or []
    for item in playback:
        info = item.get("play_info") or {}
        url = info.get("url") or ""
        mime = (info.get("mime") or "").lower()
        if url and ("mp4" in mime or "video" in mime):
            return url
    return (
        media_info.get("mp4_720p_mp4")
        or media_info.get("mp4_hd_url")
        or media_info.get("mp4_sd_url")
        or media_info.get("stream_url")
        or media_info.get("stream_url_hd")
        or ""
    )


def build_media_urls(raw_post: Dict[str, Any]) -> List[Dict[str, Any]]:
    """从原始微博 JSON 中提取媒体 URL 列表。返回 [{type, url, ext}]。"""
    medias: List[Dict[str, Any]] = []
    pics = raw_post.get("pics", []) or []
    for pic in pics:
        url = (pic.get("large", {}) or {}).get("url") or pic.get("url") or ""
        if not url:
            continue
        medias.append({"type": "pic", "url": url, "ext": _ext_from_url(url)})
        # livephoto 视频源
        if pic.get("type") == "livephoto" and pic.get("videoSrc"):
            medias.append({"type": "livephoto", "url": pic["videoSrc"], "ext": "mov"})

    # weibo.com 网页版：pics 为空，使用 pic_ids 拼图
    pic_ids = raw_post.get("pic_ids", []) or []
    for pid in pic_ids:
        url = f"https://wx1.sinaimg.cn/orj1080/{pid}.jpg"
        medias.append({"type": "pic", "url": url, "ext": "jpg"})

    page_info = raw_post.get("page_info", {}) or {}
    if page_info.get("type") == "video":
        urls = page_info.get("urls") or {}
        media_info = page_info.get("media_info") or {}
        video_url = (
            urls.get("mp4_720p_mp4")
            or urls.get("mp4_hd_url")
            or urls.get("mp4_ld_mp4")
            or media_info.get("stream_url")
            or media_info.get("h264_mp4")
            or ""
        )
        if video_url:
            medias.append({"type": "video", "url": video_url, "ext": "mp4"})

    # 新版混合媒体：mix_media_info.items（视频 / livephoto）
    mix_items = (raw_post.get("mix_media_info") or {}).get("items") or []
    for item in mix_items:
        data = item.get("data") or {}
        if item.get("type") == "video":
            video_url = _pick_video_url(data)
            if video_url:
                medias.append({"type": "video", "url": video_url, "ext": "mp4"})
        elif item.get("type") == "pic" and data.get("type") == "livephoto":
            live_url = data.get("video") or ""
            if live_url:
                medias.append({"type": "livephoto", "url": live_url, "ext": "mov"})

    # 按 URL 去重，避免同一媒体被多段逻辑重复提取
    seen: set[str] = set()
    unique: List[Dict[str, Any]] = []
    for m in medias:
        if m["url"] in seen:
            continue
        seen.add(m["url"])
        unique.append(m)
    return unique


class WeiboParser:
    def __init__(self, client: WeiboClient, uid: Optional[int] = None):
        self.client = client
        self.uid = uid

    # -- 用户 -------------------------------------------------------------
    async def parse_and_save_user(self, db: AsyncSession, user_data: Dict[str, Any]) -> Optional[User]:
        if not user_data or "id" not in user_data:
            return None
        uid = int(user_data["id"])
        result = await db.execute(select(User).where(User.id == uid))
        user = result.scalar_one_or_none()
        if user:
            user.screen_name = user_data.get("screen_name", user.screen_name)
            user.profile_image_url = user_data.get("profile_image_url", user.profile_image_url)
            user.description = user_data.get("description", user.description)
        else:
            user = User(
                id=uid,
                screen_name=user_data.get("screen_name"),
                profile_image_url=user_data.get("profile_image_url"),
                description=user_data.get("description"),
            )
            db.add(user)
        return user

    async def fetch_and_save_profile(self, db: AsyncSession, uid: int) -> Optional[User]:
        """拉取用户主页信息。"""
        try:
            data = await self.client.get_json(
                f"https://weibo.com/ajax/profile/info?uid={uid}",
                referer=f"https://weibo.com/u/{uid}",
            )
            user_data = data.get("user", data)
            if not user_data.get("id"):
                user_data = {"id": uid}
            user_data["id"] = uid
            return await self.parse_and_save_user(db, user_data)
        except Exception as e:
            logger.warning("拉取用户信息失败 uid=%s: %s", uid, e)
            return None

    # -- 微博正文 ----------------------------------------------------------
    async def fetch_long_text(self, mid: str) -> str:
        try:
            data = await self.client.get_json(
                f"https://weibo.com/ajax/statuses/longtext?id={mid}",
                referer=f"https://weibo.com/u/{mid}",
            )
            return data.get("longTextContent", "") or ""
        except Exception as e:
            logger.warning("获取长文失败 %s: %s", mid, e)
            return ""

    # -- 单条微博解析 ------------------------------------------------------
    async def parse_post(self, db: AsyncSession, raw_post: Dict[str, Any], check_existing: bool = True, is_own_post: bool = True) -> Optional[Post]:
        mid = str(raw_post.get("mid") or raw_post.get("id") or "").strip()
        if not mid:
            logger.warning("跳过无 mid 的微博。")
            return None

        result = await db.execute(select(Post).where(Post.mid == mid))
        existing = result.scalar_one_or_none()
        if existing:
            # check_existing=True 时对已存在微博返回 None，表示"非新增"，
            # 供任务循环用于增量判断；递归解析转发时传 False 保留关联。
            return None if check_existing else existing

        user = await self.parse_and_save_user(db, raw_post.get("user") or {})

        text_content = raw_post.get("text", "") or ""
        if raw_post.get("isLongText"):
            long_text = await self.fetch_long_text(mid)
            if long_text:
                text_content = long_text

        retweeted_id = None
        retweeted_raw = raw_post.get("retweeted_status")
        if retweeted_raw:
            # 被转发的原博：标记 is_own=False（他人的内容，不入个人统计/评论）
            retweeted_post = await self.parse_post(
                db, retweeted_raw, check_existing=False, is_own_post=False
            )
            retweeted_id = retweeted_post.id if retweeted_post else None

        post = Post(
            id=int(mid) if mid.isdigit() else hash(mid) % (2 ** 63 - 1),
            mid=mid,
            user_id=user.id if user else 0,
            is_own=is_own_post,
            created_at=parse_weibo_time(raw_post.get("created_at")),
            text=text_content,
            raw_html=raw_post.get("text") or "",
            region_name=raw_post.get("region_name") or None,
            reposts_count=raw_post.get("reposts_count", 0),
            comments_count=raw_post.get("comments_count", 0),
            attitudes_count=raw_post.get("attitudes_count", 0),
            retweeted_status_id=retweeted_id,
            search_text=clean_and_tokenize(text_content),
            raw_json=str(raw_post),
        )

        for m in build_media_urls(raw_post):
            post.media.append(Media(type=m["type"], url=m["url"], ext=m["ext"]))

        db.add(post)
        logger.info("解析成功 %s", mid)
        return post

    async def backfill_missing_fields(self, db: AsyncSession) -> int:
        """为已入库微博补齐缺失数据（旧版未解析出的视频等媒体 + 发布位置）。返回新增媒体数。"""
        posts = (
            await db.execute(select(Post).options(selectinload(Post.media)))
        ).scalars().all()
        added = 0
        for post in posts:
            if not post.raw_json:
                continue
            raw = _parse_raw_json(post.raw_json)
            if not raw:
                continue
            # 补齐发布位置
            if not post.region_name:
                region = raw.get("region_name") or None
                if region:
                    post.region_name = region
            # 补齐缺失媒体
            existing_urls = {m.url for m in post.media}
            for m in build_media_urls(raw):
                if m["url"] in existing_urls:
                    continue
                db.add(Media(post_id=post.id, type=m["type"], url=m["url"], ext=m["ext"]))
                existing_urls.add(m["url"])
                added += 1
        if added:
            logger.info("媒体补齐：新增 %d 条记录", added)
        return added

    # -- 评论树 (weibo.com buildComments) --------------------------------
    async def _save_comment(
        self, db: AsyncSession, post_id: int, raw: Dict[str, Any], parent_id: Optional[int]
    ) -> Optional[Comment]:
        cid = raw.get("id")
        if cid is None:
            return None
        cid = int(cid)
        # 已存在则跳过（幂等）
        exists = await db.get(Comment, cid)
        if exists:
            return None
        user = await self.parse_and_save_user(db, raw.get("user") or {})
        comment = Comment(
            id=cid,
            mid=str(raw.get("mid", cid)),
            post_id=post_id,
            user_id=user.id if user else 0,
            text=raw.get("text_raw") or raw.get("text") or "",
            created_at=parse_weibo_time(raw.get("created_at")),
            parent_id=parent_id,
            like_count=raw.get("like_counts") or raw.get("like_count") or 0,
        )
        db.add(comment)
        return comment

    async def fetch_comments(self, db: AsyncSession, post: Post) -> int:
        """抓取一级(分页) + 二级(预载+分页尝试)评论，返回新增评论数。"""
        if post.comments_count <= 0:
            return 0
        mid = post.mid
        uid = self.uid or post.user_id
        if not uid:
            return 0
        count = 0
        top_max_id = 0
        page_count = 0

        while True:
            page_count += 1
            if page_count > COMMENT_MAX_PAGES:
                logger.info("评论已达页数上限(%d)，停止 %s", COMMENT_MAX_PAGES, mid)
                break
            url = (
                f"https://weibo.com/ajax/statuses/buildComments?flow=0&is_reload=1"
                f"&id={mid}&is_show_bulletin=2&is_mix=0&count=20&uid={uid}"
            )
            if top_max_id:
                url += f"&max_id={top_max_id}&max_id_type=0"
            try:
                data = await self.client.get_json(
                    url, referer=f"https://weibo.com/status/{mid}", all_ret=True
                )
            except WeiboRateLimitError:
                logger.warning("评论接口限流 %s，稍后重试", mid)
                break
            except Exception as e:
                logger.warning("评论抓取中断 %s: %s", mid, e)
                break

            comments = data.get("data") or []
            if not comments:
                break
            for c_raw in comments:
                if await self._save_comment(db, post.id, c_raw, None):
                    count += 1
                # 二级评论（预载）
                children = c_raw.get("comments") or []
                for child_raw in children:
                    if await self._save_comment(db, post.id, child_raw, int(c_raw["id"])):
                        count += 1
                # 二级评论分页补全
                total_child = c_raw.get("total_number") or len(children)
                child_max = c_raw.get("max_id") or 0
                fetched_children = len(children)
                while total_child > fetched_children and child_max:
                    c_url = (
                        f"https://weibo.com/ajax/statuses/buildComments?is_reload=1"
                        f"&id={mid}&is_show_bulletin=2&is_mix=0&count=20&uid={uid}"
                        f"&cid={c_raw['id']}&max_id={child_max}&max_id_type=2"
                    )
                    try:
                        c_data = await self.client.get_json(
                            c_url, referer=f"https://weibo.com/status/{mid}", all_ret=True
                        )
                    except Exception as e:
                        logger.warning("二级评论分页中断: %s", e)
                        break
                    child_list = c_data.get("data") or []
                    if not child_list:
                        break
                    for child_raw in child_list:
                        if await self._save_comment(db, post.id, child_raw, int(c_raw["id"])):
                            count += 1
                            fetched_children += 1
                    child_max = c_data.get("max_id") or 0

            top_max_id = data.get("max_id") or 0
            if not top_max_id:
                break
            await db.flush()  # 放行并发调度
        return count