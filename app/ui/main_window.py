"""主窗口：任务配置、驱动状态、进度与结果展示、运行日志"""
from __future__ import annotations

import os
import shutil

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QIcon, QTextCursor
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.core import excel_service
from app.core.config import AppConfig, load_config, save_config
from app.core.models import RunMode
from app.ui.settings_dialog import SettingsDialog
from app.ui.worker import DriverCheckThread, TaskWorker
from app.utils import paths

APP_TITLE = "K-Beeline 自动化助手"
APP_VERSION = "1.0.0"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_TITLE} v{APP_VERSION}")
        self.setWindowIcon(QIcon(paths.resource_path("assets", "icons", "logo.png")))
        self.resize(980, 780)

        self.config: AppConfig = load_config()
        self.driver_path: str | None = None
        self.edge_version: str | None = None
        self._driver_ready = False
        self._pending_start = False

        self._driver_thread: DriverCheckThread | None = None
        self._worker: TaskWorker | None = None

        self._success_count = 0
        self._fail_count = 0

        self._build_ui()
        self._load_config_to_ui()

        # 启动后自动检测浏览器驱动
        QTimer.singleShot(300, self.check_driver)

    # ================= UI 构建 =================
    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        # ---- 任务设置 ----
        task_group = QGroupBox("任务设置")
        task_form = QFormLayout(task_group)

        browser_row = QHBoxLayout()
        self.browser_combo = QComboBox()
        self.browser_combo.addItems(["Edge", "Chrome", "Firefox"])
        self.browser_combo.currentIndexChanged.connect(self._on_browser_changed)
        browser_row.addWidget(self.browser_combo)
        browser_row.addStretch(1)
        task_form.addRow("浏览器:", browser_row)

        mode_row = QHBoxLayout()
        self.post_radio = QRadioButton("发帖模式（登录→发帖→回写结果）")
        self.activate_radio = QRadioButton("激活模式（登录→重置密码→进入芯泉子）")
        self.post_radio.setChecked(True)
        self.post_radio.toggled.connect(self._on_mode_changed)
        mode_row.addWidget(self.post_radio)
        mode_row.addWidget(self.activate_radio)
        mode_row.addStretch(1)
        task_form.addRow("运行模式:", mode_row)

        excel_row = QHBoxLayout()
        self.excel_edit = QLineEdit()
        self.excel_edit.setPlaceholderText("选择账号表（Autouer.xlsx，需包含 学号/备注 两列）")
        self.excel_browse_btn = QPushButton("浏览...")
        self.excel_browse_btn.clicked.connect(self._browse_excel)
        self.excel_template_btn = QPushButton("下载模板")
        self.excel_template_btn.clicked.connect(self._export_template)
        excel_row.addWidget(self.excel_edit, 1)
        excel_row.addWidget(self.excel_browse_btn)
        excel_row.addWidget(self.excel_template_btn)
        task_form.addRow("账号表:", excel_row)

        img_row = QHBoxLayout()
        self.img_edit = QLineEdit()
        self.img_edit.setPlaceholderText("留空使用内置图片库（35张）")
        self.img_browse_btn = QPushButton("浏览...")
        self.img_browse_btn.clicked.connect(self._browse_img_dir)
        img_row.addWidget(self.img_edit, 1)
        img_row.addWidget(self.img_browse_btn)
        task_form.addRow("图片库:", img_row)

        option_row = QHBoxLayout()
        self.proxy_check = QCheckBox("使用代理IP池（一号一IP）")
        self.location_check = QCheckBox("使用虚拟定位")
        self.ai_check = QCheckBox("AI 自动生成内容")
        option_row.addWidget(self.proxy_check)
        option_row.addWidget(self.location_check)
        option_row.addWidget(self.ai_check)
        option_row.addStretch(1)
        task_form.addRow("功能开关:", option_row)

        root.addWidget(task_group)

        # ---- 浏览器驱动 ----
        driver_group = QGroupBox("浏览器驱动（自动更新，无需手动维护）")
        driver_layout = QVBoxLayout(driver_group)
        driver_row = QHBoxLayout()
        self.driver_status_label = QLabel("正在检测...")
        self.driver_check_btn = QPushButton("检查/更新驱动")
        self.driver_check_btn.clicked.connect(self.check_driver)
        driver_row.addWidget(self.driver_status_label, 1)
        driver_row.addWidget(self.driver_check_btn)
        driver_layout.addLayout(driver_row)
        self.driver_completion_label = QLabel("")
        self.driver_completion_label.setStyleSheet("color: #0969da; font-size: 12px;")
        driver_layout.addWidget(self.driver_completion_label)
        root.addWidget(driver_group)

        # ---- 控制按钮 ----
        btn_row = QHBoxLayout()
        self.start_btn = QPushButton("开始任务")
        self.start_btn.setMinimumHeight(36)
        self.start_btn.clicked.connect(self.start_task)
        self.stop_btn = QPushButton("停止")
        self.stop_btn.setMinimumHeight(36)
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_task)
        self.settings_btn = QPushButton("高级设置")
        self.settings_btn.setMinimumHeight(36)
        self.settings_btn.clicked.connect(self.open_settings)
        btn_row.addWidget(self.start_btn, 2)
        btn_row.addWidget(self.stop_btn, 1)
        btn_row.addWidget(self.settings_btn, 1)
        root.addLayout(btn_row)

        # ---- 进度 ----
        progress_row = QHBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.current_label = QLabel("空闲")
        self.stats_label = QLabel("成功: 0    失败: 0")
        progress_row.addWidget(self.progress_bar, 1)
        progress_row.addWidget(self.current_label)
        progress_row.addWidget(self.stats_label)
        root.addLayout(progress_row)

        # ---- 结果与日志（上下分栏）----
        self.result_table = QTableWidget(0, 3)
        self.result_table.setHorizontalHeaderLabels(["学号", "状态码", "备注"])
        self.result_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.result_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.result_table.setMaximumHeight(170)
        result_group = QGroupBox("处理结果")
        result_layout = QVBoxLayout(result_group)
        result_layout.addWidget(self.result_table)
        root.addWidget(result_group)

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.document().setMaximumBlockCount(5000)
        log_group = QGroupBox("运行日志")
        log_layout = QVBoxLayout(log_group)
        log_layout.addWidget(self.log_view)
        root.addWidget(log_group, 1)

        # ---- 底部状态栏与署名 ----
        bottom_row = QHBoxLayout()
        self.status_label = QLabel("就绪")
        self.status_label.setStyleSheet("color: #656d76; font-size: 12px;")
        signature = QLabel("Powered by 小可  |  www.ikee002.top")
        signature.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        signature.setStyleSheet("color: #8b949e; font-size: 11px;")
        bottom_row.addWidget(self.status_label)
        bottom_row.addStretch(1)
        bottom_row.addWidget(signature)
        root.addLayout(bottom_row)

    # ================= 配置 <-> UI =================
    def _load_config_to_ui(self) -> None:
        c = self.config
        # 浏览器
        browser_map = {"edge": 0, "chrome": 1, "firefox": 2}
        self.browser_combo.setCurrentIndex(browser_map.get(c.browser, 0))
        if c.mode == RunMode.ACTIVATE.value:
            self.activate_radio.setChecked(True)
        else:
            self.post_radio.setChecked(True)
        self.excel_edit.setText(c.excel_path or "")
        self.img_edit.setText(c.img_dir or "")
        self.proxy_check.setChecked(c.use_proxy)
        self.location_check.setChecked(c.use_virtual_location)
        self.ai_check.setChecked(c.ai_enabled)

    def _save_ui_to_config(self) -> None:
        c = self.config
        c.browser = ["edge", "chrome", "firefox"][self.browser_combo.currentIndex()]
        c.mode = RunMode.POST.value if self.post_radio.isChecked() else RunMode.ACTIVATE.value
        c.excel_path = self.excel_edit.text().strip()
        c.img_dir = self.img_edit.text().strip()
        c.use_proxy = self.proxy_check.isChecked()
        c.use_virtual_location = self.location_check.isChecked()
        c.ai_enabled = self.ai_check.isChecked()
        save_config(c)

    def _on_mode_changed(self) -> None:
        """切换模式时默认不勾选功能开关"""
        self.proxy_check.setChecked(False)
        self.location_check.setChecked(False)
        self.ai_check.setChecked(False)

    def _on_browser_changed(self) -> None:
        """切换浏览器时重置驱动状态，重新检测"""
        self._driver_ready = False
        self.driver_path = None
        self.edge_version = None
        self.driver_status_label.setText("浏览器已切换，请重新检测驱动")
        QTimer.singleShot(300, self.check_driver)

    # ================= 文件选择 =================
    def _browse_excel(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "选择账号表", "", "Excel 文件 (*.xlsx)"
        )
        if path:
            self.excel_edit.setText(path)

    def _browse_img_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "选择图片库目录")
        if path:
            self.img_edit.setText(path)

    def _export_template(self) -> None:
        src = paths.resource_path("assets", "templates", "Autouer_模板.xlsx")
        if not os.path.exists(src):
            QMessageBox.warning(self, "模板缺失", "未找到内置模板文件。")
            return
        dst, _ = QFileDialog.getSaveFileName(
            self, "保存账号表模板", "Autouer.xlsx", "Excel 文件 (*.xlsx)"
        )
        if dst:
            try:
                shutil.copy2(src, dst)
                self.excel_edit.setText(dst)
                QMessageBox.information(self, "模板已导出", f"模板已保存到:\n{dst}\n\n请在'学号'列填入账号后使用。")
            except Exception as e:
                QMessageBox.warning(self, "导出失败", str(e))

    # ================= 驱动检测 =================
    def check_driver(self) -> None:
        if self._driver_thread and self._driver_thread.isRunning():
            return
        browser = ["edge", "chrome", "firefox"][self.browser_combo.currentIndex()]
        self.driver_status_label.setText("正在检测浏览器驱动...")
        self.driver_completion_label.setText("")
        self.driver_check_btn.setEnabled(False)

        self._driver_thread = DriverCheckThread(browser=browser, parent=self)
        self._driver_thread.log.connect(self.append_log)
        self._driver_thread.progress.connect(self._on_driver_progress)
        self._driver_thread.done.connect(self._on_driver_done)
        self._driver_thread.failed.connect(self._on_driver_failed)
        self._driver_thread.finished.connect(lambda: self.driver_check_btn.setEnabled(True))
        self._driver_thread.start()

    def _on_driver_progress(self, value: int) -> None:
        self.driver_completion_label.setText(f"完成度: {value}%")

    def _on_driver_done(self, browser_version: str, driver_path) -> None:
        self.edge_version = browser_version
        self.driver_path = driver_path
        self._driver_ready = True
        self.driver_completion_label.setText("")
        browser_name = ["Edge", "Chrome", "Firefox"][self.browser_combo.currentIndex()]
        if driver_path:
            self.driver_status_label.setText(f"{browser_name} {browser_version} ｜ 驱动已就绪 ✓")
            self.append_log(f"浏览器驱动已就绪 ({browser_name} {browser_version})", "INFO")
        else:
            self.driver_status_label.setText(f"{browser_name} {browser_version} ｜ 驱动将在运行时自动解析")
            self.append_log("本地驱动未命中，将在运行时由 Selenium Manager 自动解析", "WARN")
        if self._pending_start:
            self._pending_start = False
            self.start_task()

    def _on_driver_failed(self, message: str) -> None:
        self._driver_ready = False
        self.driver_status_label.setText("检测失败")
        self.driver_completion_label.setText("")
        QMessageBox.critical(self, "驱动检测失败", message)
        self._pending_start = False

    # ================= 任务控制 =================
    def start_task(self) -> None:
        if self._worker and self._worker.isRunning():
            return

        # 1. 校验 AI 配置
        self._save_ui_to_config()
        if self.config.ai_enabled:
            missing = []
            if not self.config.ai_api_url:
                missing.append("API 地址")
            if not self.config.ai_api_key:
                missing.append("API Key")
            if not self.config.ai_model:
                missing.append("模型名称")
            if missing:
                QMessageBox.warning(
                    self, "AI 配置不完整",
                    f"已启用 AI 自动生成内容，但缺少以下配置：\n\n"
                    f"  - {'、'.join(missing)}\n\n"
                    f"请在【高级设置 → AI 发帖配置】中补全。"
                )
                return

        # 2. 校验账号表
        excel_path = self.excel_edit.text().strip()
        if not excel_path:
            QMessageBox.information(self, "缺少账号表", "请先选择账号表（或点击'下载模板'获取模板）。")
            return
        if not os.path.exists(excel_path):
            QMessageBox.warning(self, "账号表不存在", f"文件不存在:\n{excel_path}")
            return

        # 2. 检查文件占用（UI线程中处理，给用户选择）
        is_locked, locked_by = excel_service.check_file_locked(excel_path)
        if is_locked:
            names = "\n".join(f"  - {p['name']} (PID: {p['pid']})" for p in (locked_by or [])) or "  未知程序"
            ret = QMessageBox.question(
                self, "账号表被占用",
                f"账号表正被以下程序占用：\n{names}\n\n是否强制关闭这些程序？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            )
            if ret != QMessageBox.Yes:
                return
            closed = excel_service.force_close_excel_processes(excel_path, log=lambda m: self.append_log(m, "WARN"))
            self.append_log(f"已强制关闭 {closed} 个占用进程", "WARN")
            still_locked, _ = excel_service.check_file_locked(excel_path)
            if still_locked:
                QMessageBox.warning(self, "仍被占用", "文件仍被占用，请手动关闭 Excel/WPS 后重试。")
                return

        # 3. 驱动未就绪 → 先检测驱动，完成后自动开始
        if not self._driver_ready:
            self.append_log("驱动尚未就绪，先执行驱动检测...", "INFO")
            self._pending_start = True
            self.check_driver()
            return

        # 4. 保存配置并启动
        self._save_ui_to_config()
        self._success_count = 0
        self._fail_count = 0
        self._update_stats_label()
        self.result_table.setRowCount(0)
        self.progress_bar.setValue(0)

        self._worker = TaskWorker(self.config, self.driver_path, self)
        self._worker.log.connect(self.append_log)
        self._worker.progress.connect(self._on_progress)
        self._worker.stage.connect(lambda text: self.status_label.setText(text))
        self._worker.account_done.connect(self._on_account_done)
        self._worker.finished_stats.connect(self._on_finished)
        self._worker.fatal_error.connect(self._on_fatal_error)

        self._set_running_state(True)
        self.append_log("=" * 50, "INFO")
        self.append_log("任务开始", "INFO")
        self._worker.start()

    def stop_task(self) -> None:
        if not (self._worker and self._worker.isRunning()):
            return
        ret = QMessageBox.question(
            self, "停止任务", "确定要停止吗？当前账号的处理将被中断。",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if ret == QMessageBox.Yes:
            self.status_label.setText("正在停止...")
            self.stop_btn.setEnabled(False)
            self._worker.stop()

    def _set_running_state(self, running: bool) -> None:
        self.start_btn.setEnabled(not running)
        self.stop_btn.setEnabled(running)
        self.settings_btn.setEnabled(not running)
        self.browser_combo.setEnabled(not running)
        self.post_radio.setEnabled(not running)
        self.activate_radio.setEnabled(not running)
        self.excel_browse_btn.setEnabled(not running)
        self.excel_template_btn.setEnabled(not running)
        self.img_browse_btn.setEnabled(not running)
        self.proxy_check.setEnabled(not running)
        self.location_check.setEnabled(not running)
        self.ai_check.setEnabled(not running)

    # ================= 任务信号 =================
    def _on_progress(self, current: int, total: int, student_id: str) -> None:
        if total > 0:
            self.progress_bar.setValue(int(current * 100 / total))
        self.current_label.setText(f"{current}/{total}  {student_id}")

    def _on_account_done(self, student_id: str, status_code: int, remark: str) -> None:
        mode = self.config.run_mode
        success_code = 2 if mode == RunMode.POST else 1
        if status_code == success_code:
            self._success_count += 1
        else:
            self._fail_count += 1
        self._update_stats_label()

        self.result_table.insertRow(0)
        for col, text in enumerate((student_id, str(status_code), remark)):
            item = QTableWidgetItem(text)
            if col == 1:
                item.setForeground(QColor("#1a7f37") if status_code == success_code else QColor("#cf222e"))
            self.result_table.setItem(0, col, item)

    def _update_stats_label(self) -> None:
        self.stats_label.setText(f"成功: {self._success_count}    失败: {self._fail_count}")

    def _on_finished(self, stats) -> None:
        self._set_running_state(False)
        self.status_label.setText("任务结束")
        self.current_label.setText("空闲")
        title = "任务完成" if not stats.stopped_by_user else "任务已停止"
        self.append_log(f"{title}\n{stats.as_text()}", "INFO")
        QMessageBox.information(self, title, stats.as_text())

    def _on_fatal_error(self, message: str) -> None:
        self._set_running_state(False)
        self.status_label.setText("任务出错")
        QMessageBox.critical(self, "任务出错", message)

    # ================= 日志 =================
    def append_log(self, message: str, level: str = "DEBUG") -> None:
        color = {
            "ERROR": "#cf222e",
            "WARN": "#bf8700",
            "INFO": "#0969da",
        }.get(level, "#656d76")
        if level == "DEBUG" and not self.config.debug_mode:
            return
        for line in str(message).splitlines() or [""]:
            self.log_view.append(f'<span style="color:{color}">{line}</span>')
        self.log_view.moveCursor(QTextCursor.End)

    # ================= 其他 =================
    def open_settings(self) -> None:
        dialog = SettingsDialog(self.config, self)
        if dialog.exec():
            save_config(self.config)
            self.append_log("高级设置已保存", "INFO")

    def closeEvent(self, event) -> None:
        if self._worker and self._worker.isRunning():
            ret = QMessageBox.question(
                self, "任务进行中", "任务正在运行，确定要停止并退出吗？",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
            )
            if ret != QMessageBox.Yes:
                event.ignore()
                return
            self._worker.stop()
            self._worker.wait(8000)
        self._save_ui_to_config()
        event.accept()
