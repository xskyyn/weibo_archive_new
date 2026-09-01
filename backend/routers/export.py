"""数据导出：Markdown 与 HTML 离线包(ZIP)。"""
from __future__ import annotations

import io
import re
import zipfile
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.config import EXPORT_DIR, PIC_DIR, RESOURCE_DIR, VIDEO_DIR
from backend.database import Comment, Media, Post, User, get_db

router = APIRouter(prefix="/api/export", tags=["Export"])

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"
_env = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    autoescape=select_autoescape(["html"]),
)


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text or "").strip()


async def _load_posts(db: AsyncSession, post_id: int | None = None, limit: int | None = None):
    stmt = (
        select(Post)
        .options(
            selectinload(Post.user),
            selectinload(Post.media),
        )
        .order_by(Post.created_at.desc())
    )
    if post_id:
        stmt = stmt.where(Post.id == post_id)
    if limit:
        stmt = stmt.limit(limit)
    return list((await db.execute(stmt)).scalars().all())


@router.get("/markdown/{post_id}")
async def export_markdown(post_id: int, db: AsyncSession = Depends(get_db)):
    """将单条微博导出为 Markdown。"""
    posts = await _load_posts(db, post_id=post_id)
    if not posts:
        raise HTTPException(404, "微博不存在")
    p = posts[0]
    lines = [
        f"# {p.user.screen_name if p.user else ''} 的微博",
        "",
        f"> 时间：{p.created_at:%Y-%m-%d %H:%M}",
        f"> 转发 {p.reposts_count} / 评论 {p.comments_count} / 赞 {p.attitudes_count}",
        "",
        _strip_html(p.text),
        "",
    ]
    if p.media:
        lines.append("## 媒体")
        lines.append("")
        for i, m in enumerate(p.media, 1):
            if m.local_path:
                lines.append(f"![媒体{i}]({Path(m.local_path).name if m.type=='pic' else m.url})")
        lines.append("")

    # 评论
    result = await db.execute(
        select(Comment).where(Comment.post_id == p.id).options(selectinload(Comment.user)).limit(200)
    )
    comments = list(result.scalars().all())
    if comments:
        lines.append("## 评论")
        lines.append("")
        for c in comments:
            name = c.user.screen_name if c.user else "?"
            indent = "  > " if c.parent_id else ""
            lines.append(f"{indent}- **{name}**：{_strip_html(c.text)}")
        lines.append("")

    filename = f"weibo_{p.mid}.md"
    return StreamingResponse(
        io.BytesIO(("\n".join(lines)).encode("utf-8")),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/html")
async def export_html(db: AsyncSession = Depends(get_db)):
    """导出 HTML 离线包 + 媒体到 ZIP。"""
    posts = await _load_posts(db, limit=1000)

    # 收集带本地的媒体，用于打包
    media_map = {}
    for p in posts:
        for m in p.media:
            if m.local_path and Path(m.local_path).exists():
                media_map[m.local_path] = True

    # 用相对路径展示媒体
    records = []
    for p in posts:
        p_copy = {
            "id": p.id,
            "mid": p.mid,
            "text": _strip_html(p.text),
            "created_at": f"{p.created_at:%Y-%m-%d %H:%M}" if p.created_at else "",
            "reposts_count": p.reposts_count,
            "comments_count": p.comments_count,
            "attitudes_count": p.attitudes_count,
            "user": {"screen_name": p.user.screen_name if p.user else ""},
            "media": [],
            "comments": [],
        }
        for m in p.media:
            rel = Path(m.local_path).name if m.local_path else ""
            p_copy["media"].append({
                "type": m.type,
                "local_path": f"media/{rel}" if rel else m.url,
            })
        records.append(p_copy)

    template = _env.get_template("archive.html")
    html = template.render(
        title="微博归档",
        generated=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        posts=records,
    )

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("index.html", html)
        for path in media_map.keys():
            p = Path(path)
            if p.exists():
                zf.write(p, f"media/{p.name}")

    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    out = EXPORT_DIR / f"weibo_archive_{datetime.now():%Y%m%d_%H%M%S}.zip"
    out.write_bytes(buf.getvalue())

    return {"ok": True, "path": str(out), "posts": len(records), "media": len(media_map)}