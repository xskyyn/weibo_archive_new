"""Pydantic 数据校验模型。"""
from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


# -- 认证 -----------------------------------------------------------
class CookieImport(BaseModel):
    """兼容两种：直接传 cookie 字典，或含 weibo.cn 键的结构。"""
    cookie: Optional[Dict[str, str]] = None
    weibo_cn: Optional[Dict[str, str]] = None
    name: Optional[str] = ""
    uid: Optional[int] = None

    def merged(self) -> Dict[str, str]:
        if self.weibo_cn is not None:
            return dict(self.weibo_cn)
        if self.cookie is not None:
            return dict(self.cookie)
        return {}


class SwitchAccountReq(BaseModel):
    id: str


class SetTargetReq(BaseModel):
    uid: int


# -- 任务控制 -----------------------------------------------------------
class StartTaskReq(BaseModel):
    uid: Optional[int] = None


class StartArchiveReq(BaseModel):
    uid: Optional[int] = None
    max_pages: Optional[int] = None


# -- 查询 -----------------------------------------------------------
class PostFilter(BaseModel):
    keyword: Optional[str] = ""
    year: Optional[int] = None
    month: Optional[int] = None
    has_media: Optional[bool] = None
    has_video: Optional[bool] = None
    page: int = 1
    page_size: int = Field(default=20, le=100)