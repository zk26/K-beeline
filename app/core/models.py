"""核心数据模型"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional


class RunMode(str, Enum):
    """运行模式"""
    POST = "post"          # 发帖模式：登录 → 发帖 → 回写结果
    ACTIVATE = "activate"  # 激活模式：登录（重置密码）→ 进入芯泉子即成功


@dataclass
class StudentRecord:
    """一条账号记录"""
    row: int            # Excel 行号
    student_id: str     # 学号
    remark: str = ""    # 原备注


@dataclass
class AccountOutcome:
    """单个账号的处理结果"""
    success: bool
    status_code: int
    error_message: str = ""
    password_reset: bool = False
    login_password: str = ""
    login_ip: str = "未知"
    login_location: str = "未知"


@dataclass
class RunStats:
    """一次批量运行的统计"""
    total: int = 0
    success: int = 0
    failed: int = 0
    password_reset: int = 0
    no_password_reset: int = 0
    stopped_by_user: bool = False
    status_counts: dict = field(default_factory=dict)

    def as_text(self) -> str:
        lines = [
            f"总计: {self.total}",
            f"成功: {self.success}",
            f"失败: {self.failed}",
            f"重置密码: {self.password_reset}",
            f"未重置密码: {self.no_password_reset}",
        ]
        for code, count in sorted(self.status_counts.items()):
            if count:
                lines.append(f"  状态{code}: {count} 个")
        return "\n".join(lines)


@dataclass
class RunnerEvents:
    """Runner → UI 的回调集合（全部可选，默认空操作）"""
    on_log: Callable[[str, str], None] = lambda msg, level: None
    on_progress: Callable[[int, int, str], None] = lambda cur, total, sid: None
    on_account_done: Callable[[str, int, str], None] = lambda sid, code, remark: None
    on_stage: Callable[[str], None] = lambda text: None
    on_finished: Callable[[RunStats], None] = lambda stats: None


@dataclass
class PipelineContext:
    """贯穿一次批量运行的上下文（替代原脚本中的全局变量）"""
    config: object                      # AppConfig（避免循环导入，运行期实际为 AppConfig）
    events: RunnerEvents
    stop_event: threading.Event = field(default_factory=threading.Event)
    current_proxy: Optional[str] = None   # 当前统一代理（requests 与 selenium 共用）
    driver_path: Optional[str] = None     # msedgedriver.exe 路径，None 表示交给 Selenium Manager
    proxy_pool: Optional[object] = None   # ProxyPool
    current_driver: Optional[object] = None  # 当前浏览器实例（用于停止时强制关闭）

    def log(self, message: str, level: str = "DEBUG") -> None:
        self.events.on_log(message, level)

    def stopped(self) -> bool:
        return self.stop_event.is_set()
