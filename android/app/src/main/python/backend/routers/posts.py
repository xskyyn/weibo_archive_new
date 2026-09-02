"""微博数据查询、搜索、分页与统计。"""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend import workspace
from backend.database import (
    Comment, Media, Post, User, fts_search, get_db, get_stats,
)
from backend.config import WORKSPACE_DIR
from backend.schemas import PostFilter

router = APIRouter(prefix="/api", tags=["Posts"])


def _media_to_dict(m: Media) -> dict:
    media_url = None
    if m.local_path:
        path = Path(m.local_path)
        try:
            media_url = "/media/" + path.relative_to(WORKSPACE_DIR).as_posix()
        except ValueError:
            media_url = f"/media/{path.name}"
    return {
        "id": m.id,
        "type": m.type,
        "url": m.url,
        "local_path": m.local_path,
        "media_url": media_url,
        "ext": m.ext,
        "width": m.width,
        "height": m.height,
    }


def _avatar_url(user) -> str:
    """优先返回本地头像地址，否则回退为在线 URL。"""
    if user is None:
        return ""
    if user.avatar_local:
        p = Path(user.avatar_local)
        try:
            return "/media/" + p.relative_to(WORKSPACE_DIR).as_posix()
        except ValueError:
            pass
    # 兜底：avatar_local 未写入但本地文件已存在时也使用本地地址
    if user.id:
        cand = workspace.avatar_dir() / f"{user.id}.jpg"
        if cand.exists():
            try:
                return "/media/" + cand.relative_to(WORKSPACE_DIR).as_posix()
            except ValueError:
                pass
    return user.profile_image_url or ""


def _post_to_dict(p: Post) -> dict:
    return {
        "id": p.id,
        "mid": p.mid,
        "text": p.text,
        "raw_html": p.raw_html,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "created_ts": int(p.created_at.timestamp()) if p.created_at else 0,
        "reposts_count": p.reposts_count,
        "comments_count": p.comments_count,
        "attitudes_count": p.attitudes_count,
        "region_name": p.region_name,
        "retweeted_status_id": p.retweeted_status_id,
        "user": {
            "id": p.user.id if p.user else None,
            "screen_name": p.user.screen_name if p.user else "",
            "profile_image_url": _avatar_url(p.user),
        },
        "media": [_media_to_dict(m) for m in p.media],
    }


def _comment_to_dict(c: Comment) -> dict:
    return {
        "id": c.id,
        "text": c.text,
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "like_count": c.like_count,
        "parent_id": c.parent_id,
        "user": {
            "id": c.user.id if c.user else None,
            "screen_name": c.user.screen_name if c.user else "",
            "profile_image_url": _avatar_url(c.user),
        },
    }


async def _load_posts(db: AsyncSession, stmt):
    stmt = stmt.options(
        selectinload(Post.media),
        selectinload(Post.user),
    )
    return list((await db.execute(stmt)).scalars().all())


async def _attach_retweet_media(db: AsyncSession, posts: List[Post]) -> None:
    """把"转发所指向原博"的媒体附加到转发卡片上，让被分享的图片也可见。"""
    retweet_ids = {p.retweeted_status_id for p in posts if p.retweeted_status_id}
    if not retweet_ids:
        return
    result = await db.execute(
        select(Post).where(Post.id.in_(retweet_ids)).options(selectinload(Post.media))
    )
    originals = {p.id: p for p in result.scalars().all()}
    for p in posts:
        orig = originals.get(p.retweeted_status_id)
        if not orig:
            continue
        existing = {m.id for m in p.media}
        for m in orig.media:
            if m.id not in existing:
                p.media.append(m)


@router.get("/stats")
async def stats(db: AsyncSession = Depends(get_db)):
    return await get_stats(db)


@router.get("/posts")
async def list_posts(
    year: int | None = Query(None),
    month: int | None = Query(None),
    has_media: bool | None = Query(None),
    has_video: bool | None = Query(None),
    on_this_day: bool | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """分页查询本人微博（is_own=True），支持年份、月份、媒体筛选、往年今日。"""
    filters = [Post.is_own == True]  # noqa: E712
    if on_this_day:
        # 往年今日：同月同日、且非今年的微博
        today = date.today()
        filters.append(func.strftime("%m-%d", Post.created_at) == today.strftime("%m-%d"))
        filters.append(func.strftime("%Y", Post.created_at) != str(today.year))
    else:
        if year:
            filters.append(func.strftime("%Y", Post.created_at) == str(year))
        if month:
            filters.append(func.strftime("%m", Post.created_at) == f"{month:02d}")

    base = select(Post).filter(*filters)
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar()

    stmt = base.order_by(Post.created_at.desc()).limit(page_size).offset((page - 1) * page_size)
    posts = await _load_posts(db, stmt)
    await _attach_retweet_media(db, posts)
    if has_media is not None:
        posts = [p for p in posts if bool(p.media) == has_media]
    if has_video is not None:
        posts = [p for p in posts if any(m.type == "video" for m in p.media) == has_video]

    return {"total": total or 0, "page": page, "page_size": page_size, "items": [_post_to_dict(p) for p in posts]}


@router.get("/posts/search")
async def search_posts(
    keyword: str = Query(""),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    submit: bool = True,
):
    """FTS5 全文搜索。"""
    posts, total = await fts_search(db, keyword, page, page_size)
    full = []
    for p in posts:
        fresh = (await db.execute(
            select(Post).where(Post.id == p.id).options(
                selectinload(Post.media), selectinload(Post.user)
            )
        )).scalar_one_or_none()
        if fresh:
            full.append(fresh)
    await _attach_retweet_media(db, full)
    items = [_post_to_dict(p) for p in full]
    if not submit:
        return full, total
    return {"total": total, "page": page, "items": items}


@router.get("/posts/{post_id}/comments")
async def get_comments(
    post_id: int,
    db: AsyncSession = Depends(get_db),
):
    """获取某条微博的一二级评论。"""
    result = await db.execute(
        select(Comment)
        .where(Comment.post_id == post_id)
        .options(selectinload(Comment.user))
        .order_by(Comment.created_at.desc())
        .limit(500)
    )
    comments = list(result.scalars().all())
    return {"items": [_comment_to_dict(c) for c in comments]}


@router.get("/media")
async def list_media(
    page: int = Query(1, ge=1),
    page_size: int = Query(60, ge=1, le=200),
    mtype: str | None = Query(None),
    order: str = Query("desc"),
    db: AsyncSession = Depends(get_db),
):
    """媒体时光轴数据（仅本人微博附带媒体），支持倒序/正序。"""
    stmt = select(Media).join(Post, Post.id == Media.post_id).where(Post.is_own == True).options(selectinload(Media.post))  # noqa: E712
    if mtype:
        stmt = stmt.where(Media.type == mtype)
    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar()
    order_col = Media.id.asc() if order == "asc" else Media.id.desc()
    result = await db.execute(
        stmt.order_by(order_col).limit(page_size).offset((page - 1) * page_size)
    )
    medias = list(result.scalars().all())
    items = []
    for m in medias:
        items.append({
            **_media_to_dict(m),
            "post_mid": m.post.mid if m.post else None,
            "post_text": (m.post.text or "")[:100] if m.post else "",
        })
    return {"total": total or 0, "page": page, "items": items}


@router.get("/posts/timeline")
async def timeline(db: AsyncSession = Depends(get_db)):
    """按星期-小时聚合本人发博数，生成热力图数据。"""
    days = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"]
    hours = [str(h) for h in range(24)]
    matrix = [[0] * 24 for _ in range(7)]
    result = await db.execute(
        select(
            ((func.strftime("%w", Post.created_at)).label("wd")),
            ((func.strftime("%H", Post.created_at)).label("hour")),
            func.count().label("cnt"),
        ).where(Post.is_own == True)  # noqa: E712
        .group_by("wd", "hour")
    )
    for row in result.fetchall():
        matrix[int(row.wd)][int(row.hour)] = row.cnt
    return {
        "days": days,
        "hours": hours,
        "matrix": matrix,
    }


@router.get("/years")
async def list_years(db: AsyncSession = Depends(get_db)):
    """可筛选的年份清单（仅本人微博）。"""
    result = await db.execute(
        select(func.strftime("%Y", Post.created_at)).where(Post.is_own == True)  # noqa: E712
        .distinct().order_by(
            func.strftime("%Y", Post.created_at).desc()
        )
    )
    return {"items": [r[0] for r in result.fetchall()]}