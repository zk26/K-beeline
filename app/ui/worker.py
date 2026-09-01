"""后台工作线程：驱动检测线程 + 批量任务线程（Qt 信号与 UI 解耦）"""
from __future__ import annotations

import threading

from PySide6.QtCore import QThread, Signal

from app.core.models import PipelineContext, RunnerEvents
from app.core.runner import BatchRunner
from app.services.driver_manager import DriverManager


class DriverCheckThread(QThread):
    """启动时/手动触发的驱动检测线程"""

    log = Signal(str, str)          # message, level
    progress = Signal(int)          # 0-100
    done = Signal(str, object)      # browser_version, driver_path(None 表示交给 Selenium Manager)
    failed = Signal(str)            # 错误消息

    def __init__(self, browser: str = "edge", parent=None):
        super().__init__(parent)
        self._browser = browser
        self._manager = DriverManager(
            browser=browser,
            log=lambda m, l="DEBUG": self.log.emit(m, l),
        )

    def run(self) -> None:
        try:
            browser_name = {"edge": "Edge", "chrome": "Chrome", "firefox": "Firefox"}.get(self._browser, self._browser)
            version = self._manager.get_installed_version()
            if not version:
                self.failed.emit(
                    f"未检测到 {browser_name} 浏览器。\n\n"
                    f"本软件需要 {browser_name} 才能工作，请先安装后重试。"
                )
                return
            driver_path = self._manager.ensure_driver(progress=self.progress.emit)
            self.done.emit(version, driver_path)
        except Exception as e:
            self.failed.emit(f"驱动检测失败: {str(e)}")


class TaskWorker(QThread):
    """批量任务线程"""

    log = Signal(str, str)                 # message, level
    progress = Signal(int, int, str)       # current, total, student_id
    stage = Signal(str)                    # 阶段描述
    account_done = Signal(str, int, str)   # student_id, status_code, remark
    finished_stats = Signal(object)        # RunStats
    fatal_error = Signal(str)              # 无法启动的致命错误

    def __init__(self, config, driver_path, parent=None):
        super().__init__(parent)
        self.config = config
        self.driver_path = driver_path
        self._runner: BatchRunner | None = None
        self._stop_event = threading.Event()

    def stop(self) -> None:
        """请求停止（线程安全）"""
        self._stop_event.set()
        if self._runner:
            self._runner.request_stop()

    def run(self) -> None:
        try:
            events = RunnerEvents(
                on_log=lambda msg, level: self.log.emit(msg, level),
                on_progress=lambda cur, total, sid: self.progress.emit(cur, total, sid),
                on_stage=lambda text: self.stage.emit(text),
                on_account_done=lambda sid, code, remark: self.account_done.emit(sid, code, remark),
                on_finished=lambda stats: self.finished_stats.emit(stats),
            )
            ctx = PipelineContext(
                config=self.config,
                events=events,
                stop_event=self._stop_event,
                driver_path=self.driver_path,
            )
            self._runner = BatchRunner(ctx)
            self._runner.run()
        except Exception as e:
            self.fatal_error.emit(f"任务执行出错: {str(e)}")
