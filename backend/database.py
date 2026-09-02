"""数据库层：SQLAlchemy 2.0 异步模型 + SQLite FTS5 全文搜索 + jieba 中文分词。"""
from __future__ import annotations

import re
from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text, event, func, select, text,
)
from sqlalchemy.ext.asyncio import (
    AsyncSession, async_sessionmaker, create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from backend import workspace

# ---------------------------------------------------------------------------
# 引擎与 Session（动态按当前工作区重建）
# ---------------------------------------------------------------------------
_engine = None


def _make_engine(url: str):
    return create_async_engine(url, echo=False, connect_args={"check_same_thread": False})


def init_engine() -> None:
    """按当前工作区的目标 UID 创建数据库引擎。"""
    global _engine
    _engine = _make_engine(workspace.db_url())


def AsyncSessionLocal():
    """当前工作区对应的异步会话工厂（每次返回新 Session，绑定当前引擎）。

    用法与 async_sessionmaker 一致：`async with AsyncSessionLocal() as db:`。
    """
    if _engine is None:
        raise RuntimeError("数据库引擎未初始化，请先调用 set_db_target/init_engine")
    maker = async_sessionmaker(bind=_engine, class_=AsyncSession, expire_on_commit=False)
    return maker()


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# 模型定义
# ---------------------------------------------------------------------------
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    screen_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    profile_image_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    avatar_local: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    posts: Mapped[List["Post"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    comments: Mapped[List["Comment"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    mid: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    raw_html: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    reposts_count: Mapped[int] = mapped_column(Integer, default=0)
    comments_count: Mapped[int] = mapped_column(Integer, default=0)
    attitudes_count: Mapped[int] = mapped_column(Integer, default=0)

    retweeted_status_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    # 是否属于本人发布（False 表示被递归保存的"转发他人内容"原博）
    is_own: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    # 发布位置（如"发布于 北京"）
    region_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # 专为 FTS5 预处理后的分词结果
    search_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    raw_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    user: Mapped["User"] = relationship(back_populates="posts")
    media: Mapped[List["Media"]] = relationship(back_populates="post", cascade="all, delete-orphan")
    comments: Mapped[List["Comment"]] = relationship(back_populates="post", cascade="all, delete-orphan")


class Media(Base):
    __tablename__ = "media"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    post_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type: Mapped[str] = mapped_column(String(20), nullable=False)  # pic / video / livephoto
    url: Mapped[str] = mapped_column(String(1000), nullable=False)
    local_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    ext: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    width: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    height: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    post: Mapped["Post"] = relationship(back_populates="media")


class Comment(Base):
    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    mid: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    post_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    parent_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, index=True)
    like_count: Mapped[int] = mapped_column(Integer, default=0)

    post: Mapped["Post"] = relationship(back_populates="comments")
    user: Mapped["User"] = relationship(back_populates="comments")


# ---------------------------------------------------------------------------
# FTS5 全文搜索 (与 posts 表通过内容行绑定 + 触发器同步)
# ---------------------------------------------------------------------------
FTS5_SETUP_SQL = """
CREATE VIRTUAL TABLE IF NOT EXISTS posts_fts USING fts5(
    search_text,
    content="posts",
    content_rowid="id",
    tokenize="unicode61"
);

CREATE TRIGGER IF NOT EXISTS posts_ai AFTER INSERT ON posts BEGIN
    INSERT INTO posts_fts(rowid, search_text) VALUES (new.id, new.search_text);
END;

CREATE TRIGGER IF NOT EXISTS posts_ad AFTER DELETE ON posts BEGIN
    INSERT INTO posts_fts(posts_fts, rowid, search_text) VALUES('delete', old.id, old.search_text);
END;

CREATE TRIGGER IF NOT EXISTS posts_au AFTER UPDATE ON posts BEGIN
    INSERT INTO posts_fts(posts_fts, rowid, search_text) VALUES('delete', old.id, old.search_text);
    INSERT INTO posts_fts(rowid, search_text) VALUES (new.id, new.search_text);
END;
"""


def _split_statements(sql: str) -> List[str]:
    """按分号切分 SQL，同时正确处理触发器 BEGIN...END 内的分号。"""
    stmts = []
    current: List[str] = []
    for part in sql.split(";"):
        current.append(part)
        joined = ";".join(current)
        if joined.count("BEGIN") == joined.count("END") and joined.strip():
            stmts.append(joined + ";")
            current = []
    if current:
        leftover = ";".join(current).strip()
        if leftover:
            stmts.append(leftover + ";")
    return stmts


@event.listens_for(Base.metadata, "after_create")
def _create_fts5_triggers(target, connection, **kw):  # pragma: no cover
    for stmt in _split_statements(FTS5_SETUP_SQL):
        connection.execute(text(stmt))


# ---------------------------------------------------------------------------
# 中文分词工具
# ---------------------------------------------------------------------------
_stop_words = set()
try:
    import jieba.analyse
    _jieba_ready = True
except Exception:  # pragma: no cover
    _jieba_ready = False


def clean_and_tokenize(html_text: str) -> str:
    """清洗 HTML 并用 jieba 分词，返回空格分隔的关键词字符串（供 FTS5 使用）。"""
    if not html_text:
        return ""
    clean_text = re.sub(r"<[^>]+>", "", html_text)
    clean_text = re.sub(r"\s+", " ", clean_text).strip()
    if _jieba_ready:
        words = jieba.lcut(clean_text, cut_all=False)
    else:
        words = clean_text.split()
    return " ".join(w for w in words if w.strip())


# ---------------------------------------------------------------------------
# 初始化与依赖注入
# ---------------------------------------------------------------------------
async def init_db() -> None:
    """创建所有表并配置 FTS5 全文索引与同步触发器。"""
    if _engine is None:
        init_engine()
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # 轻量迁移：为已存在的库补充新增列（create_all 不会改已有表）
        cols = {r[1] for r in (await conn.execute(text("PRAGMA table_info(posts)"))).fetchall()}
        if "region_name" not in cols:
            await conn.execute(text("ALTER TABLE posts ADD COLUMN region_name VARCHAR(100)"))
        # 显式执行 FTS5 虚拟表与触发器（保证在已存在的库上也能生效）
        for stmt in _split_statements(FTS5_SETUP_SQL):
            await conn.execute(text(stmt))


async def set_db_target(uid: int | None) -> None:
    """切换到目标用户的工作区（对应独立 DB 与媒体目录），并完成建表。"""
    global _engine
    if _engine is not None:
        await _engine.dispose()
    workspace.set_current_uid(uid)
    workspace.ensure_dirs()
    init_engine()
    await init_db()


async def get_db():
    """FastAPI 依赖注入项，提供 Session。"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_stats(db: AsyncSession) -> dict:
    """汇总统计信息（仪表盘用）。每个计数用独立子查询，避免笛卡尔积放大。

    只统计本人(is_own=True)的微博/媒体/评论；转发的他人原博不计入。
    """
    own = Post.is_own == True  # noqa: E712
    users = (await db.scalar(select(func.count(User.id)))) or 0
    posts = (await db.scalar(select(func.count(Post.id)).where(own))) or 0
    comments = (await db.scalar(
        select(func.count(Comment.id)).join(Post, Post.id == Comment.post_id).where(own)
    )) or 0
    media = (await db.scalar(
        select(func.count(Media.id)).join(Post, Post.id == Media.post_id).where(own)
    )) or 0
    videos = (await db.scalar(
        select(func.count(Media.id)).join(Post, Post.id == Media.post_id)
        .where(own, Media.type == "video")
    )) or 0
    return {
        "users": users,
        "posts": posts,
        "comments": comments,
        "media": media,
        "videos": videos,
    }


async def fts_search(db: AsyncSession, keyword: str, page: int = 1, page_size: int = 20) -> tuple:
    """使用 FTS5 全文检索，返回 (posts, total)。"""
    offset = (page - 1) * page_size
    if not keyword:
        total = await db.scalar(select(func.count(Post.id)).where(Post.is_own == True))  # noqa: E712
        result = await db.execute(
            select(Post).where(Post.is_own == True)  # noqa: E712
            .order_by(Post.created_at.desc()).limit(page_size).offset(offset)
        )
        return list(result.scalars().all()), total or 0

    results = await db.execute(
        text(
            """
            SELECT p.id FROM posts p
            JOIN posts_fts ON p.id = posts_fts.rowid
            WHERE posts_fts MATCH :keyword AND p.is_own = 1
            ORDER BY p.created_at DESC
            LIMIT :limit OFFSET :offset
            """
        ),
        {"keyword": keyword, "limit": page_size, "offset": offset},
    )
    ids = [r[0] for r in results.fetchall()]
    if not ids:
        return [], 0

    stmt = select(Post).where(Post.id.in_(ids)).order_by(Post.created_at.desc())
    posts = list((await db.execute(stmt)).scalars().all())
    return posts, len(posts)