"""代理池服务：代理获取、连通性测试、"一号一IP" 记录

从原 main.py 的代理相关全局函数重构为 ProxyPool 类，
使用集合 + 文件持久化记录已使用 IP，避免重复。
"""
from __future__ import annotations

import json
import os
import random
import time
from typing import List, Optional

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def extract_ip_from_proxy(proxy: Optional[str]) -> Optional[str]:
    """从代理字符串中提取IP地址。

    支持: "ip:port" / "ip:port:user:pass" / "socks5://ip:port"
    """
    if not proxy:
        return None
    try:
        text = proxy.replace("socks5://", "")
        parts = text.split(":")
        if parts:
            return parts[0]
    except Exception:
        pass
    return None


def build_requests_proxies(proxy: Optional[str]) -> Optional[dict]:
    """构建 requests 库使用的代理字典（HTTP / SOCKS5）"""
    if not proxy:
        return None
    if proxy.startswith("socks5://"):
        return {"http": proxy, "https": proxy}
    parts = proxy.split(":")
    if len(parts) >= 4:
        ip, port, username, password = parts[:4]
        proxy_url = f"http://{username}:{password}@{ip}:{port}"
    elif len(parts) >= 2:
        proxy_url = f"http://{parts[0]}:{parts[1]}"
    else:
        return None
    return {"http": proxy_url, "https": proxy_url}


class ProxyPool:
    """代理池：负责获取、测试、记录已用 IP"""

    def __init__(self, config, log=lambda m, l="DEBUG": None):
        """
        Args:
            config: AppConfig
            log: 日志回调 (message, level)
        """
        self.config = config
        self.log = log
        self.used_ips: set = set()

    # ---------------- 已用 IP 持久化 ----------------
    def load_used_ips(self) -> None:
        path = self.config.used_ips_file
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self.used_ips = {line.strip() for line in f if line.strip()}
                self.log(f"已加载 {len(self.used_ips)} 个历史IP记录")
            except Exception as e:
                self.log(f"加载已使用IP文件失败: {str(e)}")
                self.used_ips = set()
        else:
            self.used_ips = set()

    def save_used_ips(self) -> None:
        try:
            with open(self.config.used_ips_file, "w", encoding="utf-8") as f:
                for ip in sorted(self.used_ips):
                    f.write(f"{ip}\n")
        except Exception as e:
            self.log(f"保存已使用IP文件失败: {str(e)}")

    def record_ip(self, ip: Optional[str]) -> None:
        if ip:
            self.used_ips.add(ip)
            self.save_used_ips()

    # ---------------- 代理测试 ----------------
    def test_proxy_connection(self, proxy: str, timeout: int = 10) -> bool:
        """测试代理连接是否可用（多备用URL）"""
        if not proxy:
            return False
        try:
            proxies_dict = build_requests_proxies(proxy)
            if not proxies_dict:
                return False
            test_urls = [
                "http://myip.ipip.net",
                "http://httpbin.org/ip",
                "http://api.ipify.org?format=json",
            ]
            for test_url in test_urls:
                try:
                    response = requests.get(test_url, proxies=proxies_dict, timeout=timeout)
                    if response.status_code == 200:
                        self.log(f"代理连接测试成功: {proxy} (通过 {test_url})")
                        return True
                except requests.exceptions.RequestException:
                    continue
            self.log(f"代理连接测试失败: {proxy} (所有测试URL都失败)")
            return False
        except Exception as e:
            self.log(f"测试代理连接时出错: {str(e)}")
            return False

    def test_proxy_target_website(self, proxy: str, target_url: str) -> bool:
        """测试代理是否能访问目标网站（SSL错误视为可用，浏览器会处理）"""
        if not proxy:
            return False
        try:
            proxies_dict = build_requests_proxies(proxy)
            if not proxies_dict:
                return False
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                              "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Connection": "keep-alive",
            }
            try:
                response = requests.get(
                    target_url, proxies=proxies_dict, headers=headers,
                    timeout=(5, 8), verify=False,
                )
                if response.status_code == 200:
                    self.log(f"代理可以访问目标网站: {proxy}")
                    return True
                self.log(f"代理访问目标网站返回非200状态码: {proxy} (状态码: {response.status_code})")
                return False
            except requests.exceptions.Timeout:
                self.log(f"代理访问目标网站超时: {proxy}")
                return False
            except Exception as e:
                error_str = str(e).lower()
                if "ssl" in error_str or "certificate" in error_str:
                    self.log(f"代理SSL验证失败，但可能仍可用（浏览器会处理）: {proxy}")
                    return True
                self.log(f"代理访问目标网站失败: {proxy} (错误: {str(e)})")
                return False
        except Exception as e:
            self.log(f"测试代理访问目标网站时出错: {str(e)}")
            return False

    # ---------------- 代理获取 ----------------
    def get_and_record_proxy(self, exclude_used_ips: bool = True) -> Optional[str]:
        """获取代理并记录IP到已使用列表（"一号一IP"）"""
        proxy = self.get_random_proxy(exclude_used_ips=exclude_used_ips)
        if proxy:
            proxy_ip = extract_ip_from_proxy(proxy)
            if proxy_ip:
                self.used_ips.add(proxy_ip)
                self.log(f"已记录代理IP: {proxy_ip} (当前已使用 {len(self.used_ips)} 个不同IP)")
                self.save_used_ips()
        return proxy

    def get_random_proxy(self, exclude_used_ips: bool = True) -> Optional[str]:
        """随机获取一个可用代理。

        优先级: 全民IP代理池 → 备用API → 手动列表 → None(本地连接)
        """
        proxy = self._fetch_from_priority_api(exclude_used_ips)
        if proxy:
            return proxy
        proxy = self._fetch_from_backup_api(exclude_used_ips)
        if proxy:
            return proxy
        proxy = self._fetch_from_manual_list(exclude_used_ips)
        if proxy:
            return proxy
        self.log("警告: 无法获取代理，将使用本地连接（本地IP）")
        return None

    def _split_unused(self, proxies: List[str], exclude_used_ips: bool) -> List[str]:
        """按"一号一IP"拆分：优先未使用IP；全部用过则允许重复"""
        if not (exclude_used_ips and self.used_ips):
            return list(proxies)
        unused = [p for p in proxies if (extract_ip_from_proxy(p) or "") not in self.used_ips]
        if unused:
            self.log(f"找到 {len(unused)} 个未使用的代理，{len(proxies) - len(unused)} 个已使用")
            return unused
        self.log(f"所有代理都已使用过（{len(proxies)}个），将允许重复使用")
        return list(proxies)

    def _fetch_from_priority_api(self, exclude_used_ips: bool) -> Optional[str]:
        """全民IP代理池（返回 ip:port 列表）"""
        api_url = self.config.priority_proxy_api_url
        if not api_url:
            return None
        max_retries = 2
        for attempt in range(1, max_retries + 1):
            try:
                self.log(f"从全民IP代理池获取代理 (尝试 {attempt}/{max_retries})")
                response = requests.get(api_url, timeout=5)
                response.raise_for_status()

                lines = [line.strip() for line in response.text.splitlines() if line.strip()]
                # 兼容 JSON 返回格式
                if not lines and response.text.strip().startswith("{"):
                    try:
                        data = response.json()
                        for key in ("data", "proxies", "list"):
                            if isinstance(data.get(key), list):
                                lines = [str(x).strip() for x in data[key] if str(x).strip()]
                                break
                    except Exception:
                        pass
                if not lines:
                    self.log(f"全民IP代理池返回为空 (尝试 {attempt}/{max_retries})")
                    continue

                self.log(f"从全民IP代理池获取到 {len(lines)} 个代理")
                proxies_to_try = self._split_unused(lines, exclude_used_ips)

                if len(proxies_to_try) == 1:
                    return proxies_to_try[0]

                random.shuffle(proxies_to_try)
                max_test_count = min(3, len(proxies_to_try))
                tested_count = 0
                failed_count = 0

                for proxy in proxies_to_try:
                    if tested_count >= max_test_count:
                        # 失败率过高则跳过测试直接使用
                        if failed_count >= max_test_count * 0.5 and proxies_to_try:
                            self.log("测试失败率较高，跳过测试直接使用代理")
                            return proxies_to_try[0]
                        break
                    tested_count += 1
                    if self.test_proxy_connection(proxy):
                        return proxy
                    failed_count += 1
                    self.log(f"代理 {proxy} 连接测试失败，尝试下一个 ({tested_count}/{max_test_count})")

                # 全部测试失败或只测了一部分：直接使用第一个
                if tested_count > 0 and failed_count == tested_count and proxies_to_try:
                    self.log("所有测试的代理都失败，但IP池可信，直接使用第一个代理")
                    return proxies_to_try[0]
                if tested_count > 0 and len(proxies_to_try) > tested_count:
                    return proxies_to_try[tested_count]

            except requests.exceptions.RequestException as e:
                self.log(f"从全民IP代理池获取失败（网络错误）: {str(e)} (尝试 {attempt}/{max_retries})")
            except Exception as e:
                self.log(f"从全民IP代理池获取失败: {str(e)} (尝试 {attempt}/{max_retries})")

            if attempt < max_retries:
                time.sleep(0.3 * attempt)
        self.log("全民IP代理池获取失败，尝试备用代理API")
        return None

    def _fetch_from_backup_api(self, exclude_used_ips: bool) -> Optional[str]:
        """备用代理池API（JSON格式）"""
        api_url = self.config.proxy_api_url
        if not api_url:
            return None
        max_retries = 2
        for attempt in range(1, max_retries + 1):
            try:
                params = {}
                if self.config.proxy_api_protocol and self.config.proxy_api_protocol.lower() != "all":
                    params["protocol"] = self.config.proxy_api_protocol.lower()
                if self.config.proxy_api_count and self.config.proxy_api_count > 0:
                    params["count"] = min(self.config.proxy_api_count, 20)
                if self.config.proxy_api_country and self.config.proxy_api_country.upper() != "ALL":
                    params["country_code"] = self.config.proxy_api_country.upper()

                self.log(f"从备用代理API获取代理 (尝试 {attempt}/{max_retries}): {params}")
                response = requests.get(api_url, params=params, timeout=10)
                response.raise_for_status()

                if self.config.proxy_api_format.lower() == "json":
                    data = response.json()
                    if data.get("code") == 200 and "data" in data:
                        proxies = data["data"].get("proxies", [])
                        if proxies:
                            proxies_to_try = self._split_unused(proxies, exclude_used_ips)
                            random.shuffle(proxies_to_try)
                            for proxy in proxies_to_try:
                                if self.test_proxy_connection(proxy):
                                    return proxy
                            self.log("备用API返回的代理都不可用，继续重试")
                    else:
                        self.log(f"备用API返回错误: code={data.get('code')}, message={data.get('message')}")
                else:
                    proxy = response.text.strip()
                    if proxy and self.test_proxy_connection(proxy):
                        return proxy
            except (requests.exceptions.RequestException, json.JSONDecodeError) as e:
                self.log(f"从备用代理API获取失败: {str(e)} (尝试 {attempt}/{max_retries})")
            except Exception as e:
                self.log(f"从备用代理API获取失败: {str(e)} (尝试 {attempt}/{max_retries})")

            if attempt < max_retries:
                time.sleep(0.5 * attempt)
        return None

    def _fetch_from_manual_list(self, exclude_used_ips: bool) -> Optional[str]:
        """手动配置代理列表"""
        proxy_list = list(self.config.proxy_list or [])
        if not proxy_list:
            return None
        proxies_to_try = self._split_unused(proxy_list, exclude_used_ips)
        random.shuffle(proxies_to_try)
        for proxy in proxies_to_try:
            if self.test_proxy_connection(proxy):
                return proxy
        self.log("所有手动代理连接测试失败")
        return None
