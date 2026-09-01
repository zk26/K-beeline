"""多浏览器驱动自动管理服务（Edge / Chrome / Firefox）。

工作原理（启动时执行）：
1. 读取本机已安装的浏览器版本（注册表 → 安装目录扫描 两级兜底）
2. 检查驱动缓存是否匹配
3. 不匹配则从官方 CDN 查询匹配版本并自动下载（带进度回调），解压校验后缓存
4. 下载失败 → 返回 None，交给 Selenium Manager 自动解析
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import winreg
import zipfile
from typing import Callable, Optional

import requests

from app.utils import paths

ProgressCallback = Callable[[str], None]


def _noop(_: str) -> None:
    pass


class DriverManager:
    """多浏览器驱动版本检测、下载与缓存管理"""

    def __init__(self, browser: str = "edge", log: ProgressCallback = _noop):
        self.browser = browser.lower()
        self.log = log

    # ==================== 版本检测 ====================

    def get_installed_version(self) -> Optional[str]:
        """读取本机浏览器版本"""
        if self.browser == "edge":
            return self._get_edge_version()
        elif self.browser == "chrome":
            return self._get_chrome_version()
        elif self.browser == "firefox":
            return self._get_firefox_version()
        return None

    def _get_edge_version(self) -> Optional[str]:
        for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY, 0):
                try:
                    key = winreg.OpenKey(
                        root, r"SOFTWARE\Microsoft\Edge\BLBeacon", 0, winreg.KEY_READ | view
                    )
                    version, _ = winreg.QueryValueEx(key, "version")
                    winreg.CloseKey(key)
                    if version:
                        self.log(f"从注册表检测到 Edge 版本: {version}")
                        return version
                except OSError:
                    continue
        for base in (os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles")):
            if not base:
                continue
            app_dir = os.path.join(base, "Microsoft", "Edge", "Application")
            if os.path.isdir(app_dir):
                candidates = [d for d in os.listdir(app_dir) if re.fullmatch(r"\d+\.\d+\.\d+\.\d+", d)]
                if candidates:
                    candidates.sort(key=lambda v: [int(x) for x in v.split(".")], reverse=True)
                    version = candidates[0]
                    self.log(f"从安装目录检测到 Edge 版本: {version}")
                    return version
        self.log("未检测到 Edge 浏览器安装", "WARN")
        return None

    def _get_chrome_version(self) -> Optional[str]:
        for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY, 0):
                for subkey in (r"SOFTWARE\Google\Chrome\BLBeacon", r"SOFTWARE\Google\Chrome"):
                    try:
                        key = winreg.OpenKey(root, subkey, 0, winreg.KEY_READ | view)
                        version, _ = winreg.QueryValueEx(key, "version")
                        winreg.CloseKey(key)
                        if version:
                            self.log(f"从注册表检测到 Chrome 版本: {version}")
                            return version
                    except OSError:
                        continue
        for base in (os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles")):
            if not base:
                continue
            app_dir = os.path.join(base, "Google", "Chrome", "Application")
            if os.path.isdir(app_dir):
                candidates = [d for d in os.listdir(app_dir) if re.fullmatch(r"\d+\.\d+\.\d+\.\d+", d)]
                if candidates:
                    candidates.sort(key=lambda v: [int(x) for x in v.split(".")], reverse=True)
                    version = candidates[0]
                    self.log(f"从安装目录检测到 Chrome 版本: {version}")
                    return version
        self.log("未检测到 Chrome 浏览器安装", "WARN")
        return None

    def _get_firefox_version(self) -> Optional[str]:
        for root in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY, 0):
                try:
                    key = winreg.OpenKey(
                        root, r"SOFTWARE\Mozilla\Mozilla Firefox", 0, winreg.KEY_READ | view
                    )
                    version, _ = winreg.QueryValueEx(key, "CurrentVersion")
                    winreg.CloseKey(key)
                    if version:
                        self.log(f"从注册表检测到 Firefox 版本: {version}")
                        return version
                except OSError:
                    continue
        for base in (os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)")):
            if not base:
                continue
            exe_path = os.path.join(base, "Mozilla Firefox", "firefox.exe")
            if os.path.exists(exe_path):
                try:
                    result = subprocess.run(
                        [exe_path, "--version"], capture_output=True, text=True, timeout=5,
                        creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
                    )
                    match = re.search(r"(\d+\.\d+(?:\.\d+)?)", (result.stdout or "") + (result.stderr or ""))
                    if match:
                        version = match.group(1)
                        self.log(f"从可执行文件检测到 Firefox 版本: {version}")
                        return version
                except Exception:
                    pass
        self.log("未检测到 Firefox 浏览器安装", "WARN")
        return None

    # ==================== 驱动版本检测 ====================

    @staticmethod
    def get_driver_version(driver_path: str) -> Optional[str]:
        if not os.path.exists(driver_path):
            return None
        try:
            result = subprocess.run(
                [driver_path, "--version"],
                capture_output=True, text=True, timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
            )
            output = (result.stdout or "") + (result.stderr or "")
            match = re.search(r"(\d+\.\d+\.\d+\.\d+)", output)
            if match:
                return match.group(1)
        except Exception:
            pass
        return None

    # ==================== 缓存路径 ====================

    def _cached_driver_path(self, major: str) -> str:
        exe_name = {"edge": "msedgedriver.exe", "chrome": "chromedriver.exe", "firefox": "geckodriver.exe"}
        return paths.user_data_path("drivers", self.browser, major, exe_name[self.browser])

    # ==================== 在线查询与下载 ====================

    def _query_matching_version(self, major: str) -> Optional[str]:
        if self.browser == "edge":
            return self._query_edge_driver(major)
        elif self.browser == "chrome":
            return self._query_chrome_driver(major)
        elif self.browser == "firefox":
            return self._query_firefox_driver(major)
        return None

    def _query_edge_driver(self, major: str) -> Optional[str]:
        try:
            url = f"https://msedgedriver.microsoft.com/LATEST_RELEASE_{major}_WINDOWS"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                text = None
                for encoding in ("utf-16", "utf-8-sig", "utf-8"):
                    try:
                        text = response.content.decode(encoding).strip()
                        break
                    except (UnicodeDecodeError, ValueError):
                        continue
                if text:
                    match = re.search(r"(\d+\.\d+\.\d+\.\d+)", text)
                    if match:
                        return match.group(1)
        except Exception as e:
            self.log(f"查询 Edge 驱动版本失败: {str(e)}", "WARN")
        return None

    def _query_chrome_driver(self, major: str) -> Optional[str]:
        try:
            url = f"https://googlechromelabs.github.io/chrome-for-testing/LATEST_RELEASE_{major}"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                text = response.text.strip()
                match = re.search(r"(\d+\.\d+\.\d+\.\d+)", text)
                if match:
                    return match.group(1)
        except Exception as e:
            self.log(f"查询 Chrome 驱动版本失败: {str(e)}", "WARN")
        return None

    def _query_firefox_driver(self, major: str) -> Optional[str]:
        """从 GitHub API 获取最新 geckodriver 版本"""
        try:
            url = "https://api.github.com/repos/mozilla/geckodriver/releases/latest"
            response = requests.get(url, timeout=10, headers={"Accept": "application/vnd.github.v3+json"})
            if response.status_code == 200:
                data = response.json()
                tag = data.get("tag_name", "")
                match = re.search(r"v?(\d+\.\d+\.\d+)", tag)
                if match:
                    return match.group(1)
        except Exception as e:
            self.log(f"查询 Firefox 驱动版本失败: {str(e)}", "WARN")
        return None

    def _download_driver(self, version: str, dest_dir: str,
                         progress: Optional[Callable[[int], None]] = None) -> str:
        os.makedirs(dest_dir, exist_ok=True)

        if self.browser == "edge":
            return self._download_edge_driver(version, dest_dir, progress)
        elif self.browser == "chrome":
            return self._download_chrome_driver(version, dest_dir, progress)
        elif self.browser == "firefox":
            return self._download_firefox_driver(version, dest_dir, progress)
        raise RuntimeError(f"不支持的浏览器: {self.browser}")

    def _download_edge_driver(self, version, dest_dir, progress):
        url = f"https://msedgedriver.microsoft.com/{version}/edgedriver_win64.zip"
        zip_path = os.path.join(dest_dir, "edgedriver_win64.zip")
        exe_path = os.path.join(dest_dir, "msedgedriver.exe")
        self.log(f"正在下载 Edge 驱动 v{version} ...")
        self._download_and_extract(url, zip_path, exe_path, "msedgedriver.exe", progress)
        return exe_path

    def _download_chrome_driver(self, version, dest_dir, progress):
        url = f"https://storage.googleapis.com/chrome-for-testing-public/{version}/win64/chromedriver-win64.zip"
        zip_path = os.path.join(dest_dir, "chromedriver-win64.zip")
        exe_path = os.path.join(dest_dir, "chromedriver.exe")
        self.log(f"正在下载 Chrome 驱动 v{version} ...")
        self._download_and_extract(url, zip_path, exe_path, "chromedriver.exe", progress, strip_prefix="chromedriver-win64/")
        return exe_path

    def _download_firefox_driver(self, version, dest_dir, progress):
        url = f"https://github.com/mozilla/geckodriver/releases/download/v{version}/geckodriver-v{version}-win64.zip"
        zip_path = os.path.join(dest_dir, "geckodriver-win64.zip")
        exe_path = os.path.join(dest_dir, "geckodriver.exe")
        self.log(f"正在下载 Firefox 驱动 v{version} ...")
        self._download_and_extract(url, zip_path, exe_path, "geckodriver.exe", progress)
        return exe_path

    def _download_and_extract(self, url, zip_path, exe_path, target_name, progress, strip_prefix=""):
        with requests.get(url, stream=True, timeout=(10, 120)) as response:
            response.raise_for_status()
            total = int(response.headers.get("Content-Length", 0))
            downloaded = 0
            with open(zip_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=256 * 1024):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if progress and total > 0:
                            progress(min(99, int(downloaded * 100 / total)))

        with zipfile.ZipFile(zip_path, "r") as zf:
            found = None
            for name in zf.namelist():
                if name.lower().endswith(target_name.lower()):
                    found = name
                    break
            if not found:
                raise RuntimeError(f"驱动压缩包中未找到 {target_name}")
            with zf.open(found) as src, open(exe_path, "wb") as dst:
                shutil.copyfileobj(src, dst)

        try:
            os.remove(zip_path)
        except OSError:
            pass
        if progress:
            progress(100)

    # ==================== 主入口 ====================

    def ensure_driver(self, progress: Optional[Callable[[int], None]] = None) -> Optional[str]:
        browser_name = {"edge": "Edge", "chrome": "Chrome", "firefox": "Firefox"}[self.browser]
        version = self.get_installed_version()
        if not version:
            self.log(f"未安装 {browser_name} 浏览器，无法自动匹配驱动", "ERROR")
            return None
        major = version.split(".")[0]
        self.log(f"当前 {browser_name} 大版本: {major} (完整版本 {version})")

        cached = self._cached_driver_path(major)
        cached_version = self.get_driver_version(cached)
        if cached_version and cached_version.split(".")[0] == major:
            self.log(f"驱动缓存命中: v{cached_version}，无需更新")
            if progress:
                progress(100)
            return cached

        if cached_version:
            self.log(f"缓存驱动 v{cached_version} 与浏览器 v{version} 不匹配，需要更新")

        self.log("正在查询与浏览器匹配的驱动版本...")
        driver_version = self._query_matching_version(major)
        if driver_version:
            try:
                dest_dir = os.path.dirname(cached)
                driver_path = self._download_driver(driver_version, dest_dir, progress=progress)
                verified = self.get_driver_version(driver_path)
                if verified:
                    self.log(f"驱动更新完成: v{verified}（已缓存，下次启动直接使用）")
                    return driver_path
                self.log("下载的驱动校验失败", "WARN")
            except Exception as e:
                self.log(f"驱动下载失败: {str(e)}", "WARN")
        else:
            self.log("无法在线查询驱动版本（可能网络受限）", "WARN")

        return None
