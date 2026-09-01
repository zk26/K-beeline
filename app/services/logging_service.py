"""日志服务：文件日志（用户数据目录 logs/）+ 内存回调（供 UI 实时显示）"""
from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Callable, Optional

from app.utils import paths

_logger: Optional[logging.Logger] = None
_ui_callback: Optional[Callable[[str, str], None]] = None


class _CallbackHandler(logging.Handler):
    """把日志记录转发给 UI 回调"""

    def emit(self, record: logging.LogRecord) -> None:
        if _ui_callback:
            try:
                _ui_callback(record.getMessage(), record.levelname)
            except Exception:
                pass


def setup_logging() -> logging.Logger:
    """初始化全局日志器（幂等）"""
    global _logger
    if _logger:
        return _logger

    logger = logging.getLogger("kbeeline")
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    log_dir = os.path.join(paths.user_data_dir(), "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f"kbeeline_{datetime.now():%Y%m%d}.log")

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(
        "[%(asctime)s] [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    ))
    logger.addHandler(file_handler)

    callback_handler = _CallbackHandler()
    callback_handler.setLevel(logging.DEBUG)
    logger.addHandler(callback_handler)

    _logger = logger
    return logger


def set_ui_callback(callback: Optional[Callable[[str, str], None]]) -> None:
    """设置 UI 日志回调 (message, level)"""
    global _ui_callback
    _ui_callback = callback


def get_logger() -> logging.Logger:
    return setup_logging()
