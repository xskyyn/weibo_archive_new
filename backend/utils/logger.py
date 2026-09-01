"""日志工具：统一 logging 配置 + Cookie 脱敏。"""
from __future__ import annotations

import logging
import re
from logging.handlers import RotatingFileHandler
from pathlib import Path

_FORMAT = "[%(asctime)s] %(levelname)s [%(name)s] %(message)s"
_DATE_FMT = "%H:%M:%S"


def get_logger(name: str = "weibo") -> logging.Logger:
    return logging.getLogger(name)


class MaskFormatter(logging.Formatter):
    """在输出前对日志行做 Cookie 脱敏的 Formatter。"""

    def format(self, record: logging.LogRecord) -> str:
        return mask_cookie(super().format(record))


def setup_logging(level: int = logging.INFO, log_dir: str | Path | None = None) -> None:
    """配置根日志：控制台 + 落地文件（均带 Cookie 脱敏）。

    :param log_dir: 日志目录。传 None 则仅控制台；GUI 版(console=False)必须传目录。
    """
    handlers: list[logging.Handler] = []
    console = logging.StreamHandler()
    console.setFormatter(MaskFormatter(_FORMAT, _DATE_FMT))
    handlers.append(console)

    if log_dir is not None:
        log_path = Path(log_dir) / "weibo_archive.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        fh = RotatingFileHandler(
            log_path, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
        )
        fh.setFormatter(MaskFormatter(_FORMAT, _DATE_FMT))
        handlers.append(fh)

    logging.basicConfig(level=level, handlers=handlers)


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