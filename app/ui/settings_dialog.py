"""高级设置对话框：代理池、密码策略、站点、性能参数、AI 发帖"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QLineEdit,
    QPlainTextEdit,
    QScrollArea,
    QSpinBox,
    QDoubleSpinBox,
    QVBoxLayout,
    QWidget,
)


class SettingsDialog(QDialog):
    """编辑 AppConfig 中的高级参数"""

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.setWindowTitle("高级设置")
        self.setMinimumWidth(600)
        self.setMinimumHeight(500)
        self.config = config
        self._build_ui()
        self._load_values()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(10)

        # ---- 账号与站点（只读）----
        site_group = QGroupBox("站点与账号（只读）")
        site_form = QFormLayout(site_group)
        self.target_url_edit = QLineEdit()
        self.target_url_edit.setReadOnly(True)
        self.target_url_edit.setStyleSheet("background-color: #f0f0f0; color: #888;")
        self.account_prefix_edit = QLineEdit()
        self.account_prefix_edit.setReadOnly(True)
        self.account_prefix_edit.setStyleSheet("background-color: #f0f0f0; color: #888;")
        site_form.addRow("目标站点:", self.target_url_edit)
        site_form.addRow("账号前缀:", self.account_prefix_edit)
        layout.addWidget(site_group)

        # ---- 密码策略 ----
        pwd_group = QGroupBox("密码策略")
        pwd_form = QFormLayout(pwd_group)
        self.password_options_edit = QLineEdit()
        self.password_options_edit.setPlaceholderText("多个密码用英文逗号分隔，按顺序尝试")
        self.reset_password_edit = QLineEdit()
        pwd_form.addRow("尝试密码列表:", self.password_options_edit)
        pwd_form.addRow("重置密码:", self.reset_password_edit)
        layout.addWidget(pwd_group)

        # ---- 代理池 ----
        proxy_group = QGroupBox("代理池")
        proxy_form = QFormLayout(proxy_group)
        self.priority_proxy_edit = QLineEdit()
        self.backup_proxy_edit = QLineEdit()
        self.proxy_count_spin = QSpinBox()
        self.proxy_count_spin.setRange(1, 20)
        self.proxy_country_edit = QLineEdit()
        self.manual_proxy_edit = QPlainTextEdit()
        self.manual_proxy_edit.setPlaceholderText("每行一个，格式 ip:port 或 ip:port:用户名:密码（可留空）")
        self.manual_proxy_edit.setMaximumHeight(70)
        proxy_form.addRow("主代理池API:", self.priority_proxy_edit)
        proxy_form.addRow("备用代理API:", self.backup_proxy_edit)
        proxy_form.addRow("备用API获取数量:", self.proxy_count_spin)
        proxy_form.addRow("备用API国家代码:", self.proxy_country_edit)
        proxy_form.addRow("手动代理列表:", self.manual_proxy_edit)
        layout.addWidget(proxy_group)

        # ---- AI 发帖配置 ----
        ai_group = QGroupBox("AI 发帖配置（自动生成标题与内容）")
        ai_form = QFormLayout(ai_group)
        self.ai_api_url_edit = QLineEdit()
        self.ai_api_url_edit.setPlaceholderText("如 https://api.openai.com/v1 或其他兼容接口")
        self.ai_api_key_edit = QLineEdit()
        self.ai_api_key_edit.setEchoMode(QLineEdit.Password)
        self.ai_api_key_edit.setPlaceholderText("输入 API Key")
        self.ai_model_edit = QLineEdit()
        self.ai_model_edit.setPlaceholderText("如 gpt-4o-mini、deepseek-chat 等")
        self.ai_title_prompt_edit = QPlainTextEdit()
        self.ai_title_prompt_edit.setPlaceholderText("给 AI 的提示词，用于生成帖子标题。可用 {student_id} 插入学号")
        self.ai_title_prompt_edit.setMaximumHeight(80)
        self.ai_content_prompt_edit = QPlainTextEdit()
        self.ai_content_prompt_edit.setPlaceholderText("给 AI 的提示词，用于生成帖子正文内容。可用 {student_id} 插入学号")
        self.ai_content_prompt_edit.setMaximumHeight(80)
        ai_form.addRow("API 地址:", self.ai_api_url_edit)
        ai_form.addRow("API Key:", self.ai_api_key_edit)
        ai_form.addRow("模型名称:", self.ai_model_edit)
        ai_form.addRow("标题提示词:", self.ai_title_prompt_edit)
        ai_form.addRow("内容提示词:", self.ai_content_prompt_edit)
        layout.addWidget(ai_group)

        # ---- 其他 ----
        misc_group = QGroupBox("其他")
        misc_form = QFormLayout(misc_group)
        self.wait_time_spin = QDoubleSpinBox()
        self.wait_time_spin.setRange(0.1, 5.0)
        self.wait_time_spin.setSingleStep(0.1)
        self.explicit_wait_spin = QSpinBox()
        self.explicit_wait_spin.setRange(1, 30)
        self.amap_key_edit = QLineEdit()
        misc_form.addRow("基础等待(秒):", self.wait_time_spin)
        misc_form.addRow("显式等待(秒):", self.explicit_wait_spin)
        misc_form.addRow("高德API Key:", self.amap_key_edit)
        layout.addWidget(misc_group)

        layout.addStretch()
        scroll.setWidget(container)
        outer.addWidget(scroll)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)

    def _load_values(self) -> None:
        c = self.config
        self.target_url_edit.setText(c.target_url)
        self.account_prefix_edit.setText(c.account_prefix)
        self.password_options_edit.setText(",".join(c.password_options))
        self.reset_password_edit.setText(c.reset_password)
        self.priority_proxy_edit.setText(c.priority_proxy_api_url)
        self.backup_proxy_edit.setText(c.proxy_api_url)
        self.proxy_count_spin.setValue(c.proxy_api_count)
        self.proxy_country_edit.setText(c.proxy_api_country)
        self.manual_proxy_edit.setPlainText("\n".join(c.proxy_list or []))
        self.wait_time_spin.setValue(c.wait_time)
        self.explicit_wait_spin.setValue(c.explicit_wait)
        self.amap_key_edit.setText(c.amap_key)
        # AI（不含开关，开关在主界面）
        self.ai_api_url_edit.setText(c.ai_api_url)
        self.ai_api_key_edit.setText(c.ai_api_key)
        self.ai_model_edit.setText(c.ai_model)
        self.ai_title_prompt_edit.setPlainText(c.ai_title_prompt)
        self.ai_content_prompt_edit.setPlainText(c.ai_content_prompt)

    def accept(self) -> None:
        c = self.config
        # 站点字段只读，不写回
        passwords = [p.strip() for p in self.password_options_edit.text().split(",") if p.strip()]
        if passwords:
            c.password_options = passwords
        c.reset_password = self.reset_password_edit.text().strip() or c.reset_password
        c.priority_proxy_api_url = self.priority_proxy_edit.text().strip()
        c.proxy_api_url = self.backup_proxy_edit.text().strip()
        c.proxy_api_count = self.proxy_count_spin.value()
        c.proxy_api_country = self.proxy_country_edit.text().strip() or "CN"
        c.proxy_list = [
            line.strip() for line in self.manual_proxy_edit.toPlainText().splitlines() if line.strip()
        ]
        c.wait_time = self.wait_time_spin.value()
        c.explicit_wait = self.explicit_wait_spin.value()
        c.amap_key = self.amap_key_edit.text().strip()
        # AI（不含开关）
        c.ai_api_url = self.ai_api_url_edit.text().strip()
        c.ai_api_key = self.ai_api_key_edit.text().strip()
        c.ai_model = self.ai_model_edit.text().strip()
        c.ai_title_prompt = self.ai_title_prompt_edit.toPlainText().strip()
        c.ai_content_prompt = self.ai_content_prompt_edit.toPlainText().strip()
        super().accept()
