"""应用配置：数据类 + JSON 持久化（用户数据目录）"""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from typing import List

from app.core.models import RunMode
from app.utils import paths

CONFIG_FILE = "config.json"


@dataclass
class AppConfig:
    """全部可调参数。UI 修改后保存到用户数据目录的 config.json"""

    # ---- 运行模式 ----
    mode: str = RunMode.POST.value  # post / activate

    # ---- 路径 ----
    excel_path: str = ""        # 账号表（Autouer.xlsx），由用户选择
    img_dir: str = ""           # 图片库目录，空表示使用内置图片库

    # ---- 浏览器选择 ----
    browser: str = "edge"              # edge / chrome / firefox

    # ---- 功能开关 ----
    use_proxy: bool = False            # 默认不启用代理池
    use_virtual_location: bool = False # 默认不启用虚拟定位

    # ---- 目标站点 ----
    target_url: str = "https://www.beeline-ai.com/"
    account_prefix: str = "GUC"

    # ---- 密码策略 ----
    password_options: List[str] = field(default_factory=lambda: ["Aa000000", "CMTY0000", "A123456a"])
    reset_password: str = "A123456a"

    # ---- 代理池 ----
    priority_proxy_api_url: str = (
        "http://ip.quanminip.com/ip?secret=hnb8JZEU&num=200&port=1"
        "&type=json&cs=1&ys=1&sign=4a56443062b4f8c5ffbcb4a7c3dd58ae"
    )
    proxy_api_url: str = "https://proxy.scdn.io/api/get_proxy.php"
    proxy_api_format: str = "json"
    proxy_api_protocol: str = "http"
    proxy_api_count: int = 5
    proxy_api_country: str = "CN"
    proxy_list: List[str] = field(default_factory=list)

    # ---- 性能参数 ----
    wait_time: float = 0.3
    explicit_wait: int = 2
    debug_mode: bool = True

    # ---- 高德逆地理编码 Key（查询虚拟定位城市名）----
    amap_key: str = "8325164e247e15bc7c6d8cb32d7e88aa"

    # ---- AI 发帖配置 ----
    ai_enabled: bool = False                   # 是否启用 AI 生成内容
    ai_api_url: str = ""                       # OpenAI 兼容 API 地址
    ai_api_key: str = ""                       # API Key
    ai_model: str = ""                         # 模型名称
    ai_title_prompt: str = ""                  # 标题生成提示词
    ai_content_prompt: str = ""                # 内容生成提示词

    # ---------- 派生路径（不持久化）----------
    @property
    def run_mode(self) -> RunMode:
        return RunMode(self.mode)

    @property
    def effective_img_dir(self) -> str:
        """实际图片目录：用户未指定时使用内置图片库"""
        if self.img_dir and os.path.isdir(self.img_dir):
            return self.img_dir
        return paths.resource_path("assets", "img")

    @property
    def used_ips_file(self) -> str:
        return paths.user_data_path("used_ips.txt")

    @property
    def temp_upload_dir(self) -> str:
        return paths.user_data_path("temp_upload")

    # ---------- 持久化 ----------
    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "AppConfig":
        cfg = cls()
        for key, value in (data or {}).items():
            if hasattr(cfg, key) and not key.startswith("_"):
                setattr(cfg, key, value)
        return cfg


def config_file_path() -> str:
    return paths.user_data_path(CONFIG_FILE)


def load_config() -> AppConfig:
    """从用户数据目录加载配置，失败则返回默认配置"""
    path = config_file_path()
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return AppConfig.from_dict(json.load(f))
    except Exception:
        pass
    return AppConfig()


def save_config(config: AppConfig) -> None:
    """保存配置到用户数据目录"""
    path = config_file_path()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(config.to_dict(), f, ensure_ascii=False, indent=2)
