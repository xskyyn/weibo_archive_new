"""日志工具：统一 logging 配置 + Cookie 脱敏。"""
from __future__ import annotations

import logging
import re

_FORMAT = "[%(asctime)s] %(levelname)s [%(name)s] %(message)s"
_DATE_FMT = "%H:%M:%S"


def get_logger(name: str = "weibo") -> logging.Logger:
    return logging.getLogger(name)


def setup_logging(level: int = logging.INFO) -> None:
    logging.basicConfig(
        level=level,
        format=_FORMAT,
        datefmt=_DATE_FMT,
    )


# ---------------------------------------------------------------------------
# Cookie 脱敏
# ---------------------------------------------------------------------------
_COOKIE_VALUE_RE = re.compile(r"(Cookie:?\s*)([^;\n]+)", re.IGNORECASE)
_SENSITIVE_RE = re.compile(
    r"(SUB|SUBP|SUHB|SSOLOGIN|ALF|XSRF-TOKEN)\s*=\s*([A-Za-z0-9_\-%]{8,})",
    re.IGNORECASE,
)


def mask_cookie(text: str) -> str:
    """对日志文本中的 Cookie 敏感值进行脱敏。"""
    if not text:
        return text

    def _mask_sensitive(m):
        key = m.group(1)
        raw = m.group(2)
        return f"{key}={raw[:4]}***{raw[-2:]}"

    return _SENSITIVE_RE.sub(_mask_sensitive, text)


class MaskingLogger(logging.LoggerAdapter):
    """自动脱敏的日志适配器。"""

    def process(self, msg, kwargs):
        return mask_cookie(str(msg)), kwargs