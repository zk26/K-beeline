"""路径解析工具：同时兼容开发环境与 PyInstaller 打包环境。

打包后：
- 只读资源（图片、模板、兜底驱动）位于 exe 同级/_internal 的 assets 目录
- 可写数据（配置、日志、驱动缓存、临时文件）位于 %LOCALAPPDATA%\\KBeeline
"""
import os
import sys

APP_NAME = "KBeeline"


def is_frozen() -> bool:
    """是否为 PyInstaller 打包环境"""
    return getattr(sys, "frozen", False)


def resource_root() -> str:
    """只读资源根目录（开发时为项目根目录，打包后为 _internal 目录）"""
    if is_frozen():
        return sys._MEIPASS  # type: ignore[attr-defined]
    # 开发环境：本文件位于 app/utils/paths.py，向上三级为项目根
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def resource_path(*parts: str) -> str:
    """拼接只读资源路径"""
    return os.path.join(resource_root(), *parts)


def user_data_dir() -> str:
    """用户可写数据目录（%LOCALAPPDATA%\\KBeeline），不存在则创建"""
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    path = os.path.join(base, APP_NAME)
    os.makedirs(path, exist_ok=True)
    return path


def user_data_path(*parts: str) -> str:
    """拼接用户数据目录下的路径（不创建文件，仅确保父目录存在）"""
    path = os.path.join(user_data_dir(), *parts)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    return path
