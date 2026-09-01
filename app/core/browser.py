"""浏览器服务：多浏览器驱动构建（反检测/WebRTC封死/CDP虚拟定位）、会话与网络状态检查"""
from __future__ import annotations

import json
import time
from typing import Optional

import requests
from selenium import webdriver
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.firefox.service import Service as FirefoxService

from app.core.proxy_service import build_requests_proxies, extract_ip_from_proxy


def _create_driver(ctx, options, browser: str = "edge"):
    """按上下文创建 WebDriver。"""
    if browser == "edge":
        if ctx.driver_path:
            return webdriver.Edge(service=EdgeService(ctx.driver_path), options=options)
        return webdriver.Edge(options=options)
    elif browser == "chrome":
        if ctx.driver_path:
            return webdriver.Chrome(service=ChromeService(ctx.driver_path), options=options)
        return webdriver.Chrome(options=options)
    elif browser == "firefox":
        if ctx.driver_path:
            return webdriver.Firefox(service=FirefoxService(ctx.driver_path), options=options)
        return webdriver.Firefox(options=options)
    raise ValueError(f"不支持的浏览器: {browser}")


def setup_driver(ctx, proxy: Optional[str] = None, location: Optional[dict] = None):
    """设置并返回浏览器驱动（统一代理 / WebRTC封死 / 虚拟定位）"""
    browser = getattr(ctx.config, "browser", "edge")
    browser_name = {"edge": "Edge", "chrome": "Chrome", "firefox": "Firefox"}.get(browser, browser)
    ctx.log(f"正在启动{browser_name}浏览器（统一代理/WebRTC封死）...")

    if browser == "firefox":
        driver = _setup_firefox(ctx, proxy, location)
    else:
        driver = _setup_chromium(ctx, proxy, location, browser)

    driver.set_page_load_timeout(30)
    driver.implicitly_wait(3)

    # ---------- 虚拟定位（CDP，仅 Chromium 内核）----------
    if location and browser != "firefox":
        try:
            driver.execute_cdp_cmd("Emulation.setGeolocationOverride", {
                "latitude": location["latitude"],
                "longitude": location["longitude"],
                "accuracy": location.get("accuracy", 100),
            })
            ctx.log(f"已设置虚拟地理位置覆盖: 纬度={location['latitude']:.4f}, 经度={location['longitude']:.4f}")
            try:
                driver.execute_cdp_cmd("Emulation.setTimezoneOverride", {"timezoneId": "Asia/Shanghai"})
            except Exception:
                pass
            try:
                driver.execute_cdp_cmd("Emulation.setLocaleOverride", {"locale": "zh-CN"})
            except Exception:
                pass
        except Exception as e:
            ctx.log(f"设置虚拟地理位置失败: {str(e)}")

    # ---------- 隐藏 webdriver 特征 ----------
    if browser != "firefox":
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        })

    # ---------- 完全覆盖 geolocation API ----------
    if location:
        _inject_geolocation_override(ctx, driver, location, browser)

    driver.maximize_window()
    ctx.log("浏览器启动成功")
    return driver


def _setup_chromium(ctx, proxy, location, browser: str):
    """Edge / Chrome 共用的 Chromium 内核配置"""
    options = EdgeOptions() if browser == "edge" else ChromeOptions()

    # 反自动化
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    # WebRTC 封死
    options.add_argument("--disable-webrtc")
    options.add_argument("--force-webrtc-ip-handling-policy=disable_non_proxied_udp")
    options.add_argument("--disable-features=WebRtcHideLocalIpsWithMdns")
    options.add_experimental_option("prefs", {
        "webrtc.ip_handling_policy": "disable_non_proxied_udp",
        "webrtc.multiple_routes_enabled": False,
        "webrtc.nonproxied_udp_enabled": False,
        "profile.managed_default_content_settings.images": 2,
        "profile.default_content_setting_values.notifications": 2,
        "profile.default_content_settings.popups": 0,
    })

    # 稳定选项
    options.add_argument("--disable-features=IsolateOrigins,site-per-process")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    # 错误抑制
    options.add_argument("--disable-logging")
    options.add_argument("--log-level=3")
    options.add_argument("--disable-gpu-logging")
    options.add_argument("--disable-breakpad")
    options.add_argument("--disable-crash-reporter")
    options.add_argument("--disable-component-update")
    options.add_argument("--disable-client-side-phishing-detection")
    options.add_argument("--disable-domain-reliability")
    options.add_argument("--disable-default-apps")

    # 性能优化
    options.add_argument("--blink-settings=imagesEnabled=false")
    options.add_argument("--disable-images")
    options.add_argument("--disable-plugins")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-background-networking")
    options.add_argument("--disable-sync")
    options.add_argument("--disable-translate")
    options.add_argument("--disable-ipc-flooding-protection")
    options.add_argument("--aggressive-cache-discard")
    options.add_argument("--memory-pressure-off")

    # 代理
    _apply_proxy(options, ctx, proxy)

    driver = _create_driver(ctx, options, browser)
    return driver


def _setup_firefox(ctx, proxy, location):
    """Firefox / GeckoDriver 配置"""
    options = FirefoxOptions()

    # 反自动化
    options.set_preference("dom.webdriver.enabled", False)
    options.set_preference("useAutomationExtension", False)

    # WebRTC 封死
    options.set_preference("media.peerconnection.enabled", False)
    options.set_preference("media.peerconnection.ice.default_address_only", True)

    # 性能优化：禁用图片
    options.set_preference("permissions.default.image", 2)
    options.set_preference("dom.push.enabled", False)

    # 代理
    if proxy:
        if proxy.startswith("socks5://"):
            host_port = proxy.replace("socks5://", "").split(":")
            options.set_preference("network.proxy.type", 1)
            options.set_preference("network.proxy.socks", host_port[0])
            options.set_preference("network.proxy.socks_port", int(host_port[1]))
            options.set_preference("network.proxy.socks_version", 5)
            ctx.log(f"设置 Firefox SOCKS5 代理: {proxy}")
        else:
            parts = proxy.split(":")
            options.set_preference("network.proxy.type", 1)
            options.set_preference("network.proxy.http", parts[0])
            options.set_preference("network.proxy.http_port", int(parts[1]))
            options.set_preference("network.proxy.ssl", parts[0])
            options.set_preference("network.proxy.ssl_port", int(parts[1]))
            ctx.log(f"设置 Firefox HTTP 代理: {parts[0]}:{parts[1]}")

    driver = _create_driver(ctx, options, "firefox")
    return driver


def _apply_proxy(options, ctx, proxy):
    """为 Chromium 内核设置代理"""
    if not proxy:
        return
    if proxy.startswith("socks5://"):
        options.add_argument(f"--proxy-server={proxy}")
        ctx.log(f"设置 SOCKS5 代理: {proxy}")
    else:
        parts = proxy.split(":")
        if len(parts) >= 2:
            proxy_string = f"{parts[0]}:{parts[1]}"
            options.add_argument(f"--proxy-server={proxy_string}")
            ctx.log(f"设置代理: {proxy_string}")


def _inject_geolocation_override(ctx, driver, location, browser: str):
    """注入 geolocation API 覆盖脚本"""
    js_code = f"""
    (function() {{
        const fakeCoords = {{
            latitude: {location['latitude']},
            longitude: {location['longitude']},
            accuracy: {location.get('accuracy', 100)},
            altitude: null, altitudeAccuracy: null, heading: null, speed: null
        }};
        navigator.geolocation.getCurrentPosition = function(success) {{
            if (success) success({{ coords: fakeCoords, timestamp: Date.now() }});
        }};
        navigator.geolocation.watchPosition = function(success) {{
            if (success) success({{ coords: fakeCoords, timestamp: Date.now() }});
            return 1;
        }};
    }})();
    """
    if browser == "firefox":
        try:
            driver.execute_script(js_code)
            ctx.log("已覆盖 geolocation API (Firefox)")
        except Exception as e:
            ctx.log(f"覆盖 geolocation API 失败: {str(e)}")
    else:
        try:
            driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": js_code})
            ctx.log("已完全覆盖 geolocation API")
        except Exception as e:
            ctx.log(f"覆盖 geolocation API 失败: {str(e)}")


# ==================== 通用工具函数 ====================

def check_driver_session(driver) -> bool:
    try:
        if driver is None:
            return False
        driver.current_window_handle
        return True
    except Exception:
        return False


def quit_driver_quietly(driver) -> None:
    try:
        if driver:
            driver.quit()
    except Exception:
        pass


def check_page_access_success(driver, expected_url_pattern: str = "beeline-ai.com") -> bool:
    try:
        if driver is None:
            return False
        current_url = driver.current_url
        if expected_url_pattern.lower() in current_url.lower():
            try:
                if driver.title:
                    return True
            except Exception:
                pass
        return False
    except Exception:
        return False


def check_proxy_disconnected(ctx, driver=None) -> bool:
    try:
        if not ctx.current_proxy:
            return False
        if driver:
            try:
                driver.current_url
            except Exception as e:
                error_msg = str(e).lower()
                if "timeout" in error_msg or "timed out" in error_msg or "disconnected" in error_msg:
                    ctx.log(f"检测到浏览器会话断开，可能是代理断开: {str(e)}")
                    return True
        try:
            proxies_dict = build_requests_proxies(ctx.current_proxy)
            if proxies_dict:
                response = requests.get("http://httpbin.org/ip", proxies=proxies_dict, timeout=5)
                if response.status_code == 200:
                    return False
                return True
        except requests.exceptions.Timeout:
            ctx.log("代理连接超时，可能已断开")
            return True
        except requests.exceptions.ConnectionError:
            ctx.log("代理连接错误，可能已断开")
            return True
        except Exception:
            return False
        return False
    except Exception:
        return False


def get_current_ip(ctx) -> str:
    try:
        proxies_dict = build_requests_proxies(ctx.current_proxy)
        ip_apis = [
            {"url": "https://api.xinyew.cn/api/ip", "type": "json", "key": "ip", "ret_key": "ret", "ret_success": 0},
            {"url": "http://httpbin.org/ip", "type": "json", "key": "origin"},
            {"url": "http://api.ipify.org?format=json", "type": "json", "key": "ip"},
            {"url": "http://icanhazip.com", "type": "text"},
            {"url": "http://ident.me", "type": "text"},
            {"url": "http://ifconfig.me/ip", "type": "text"},
            {"url": "https://httpbin.org/ip", "type": "json", "key": "origin"},
            {"url": "https://api64.ipify.org?format=json", "type": "json", "key": "ip"},
            {"url": "https://api.ipify.org?format=json", "type": "json", "key": "ip"},
            {"url": "https://ipapi.co/json/", "type": "json", "key": "ip"},
            {"url": "https://ip-api.com/json/", "type": "json", "key": "query"},
            {"url": "https://api.ip.sb/ip", "type": "text"},
            {"url": "https://ifconfig.me/ip", "type": "text"},
            {"url": "https://icanhazip.com", "type": "text"},
            {"url": "https://ident.me", "type": "text"},
            {"url": "https://checkip.amazonaws.com", "type": "text"},
        ]
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }

        def _valid_ipv4(ip: str) -> bool:
            parts = ip.split(".")
            return len(parts) == 4 and all(p.isdigit() and 0 <= int(p) <= 255 for p in parts)

        for api_info in ip_apis:
            for retry in range(2):
                try:
                    if retry > 0:
                        time.sleep(0.5)
                    response = requests.get(api_info["url"], headers=headers, proxies=proxies_dict, timeout=(5, 8))
                    if response.status_code == 200:
                        if api_info["type"] == "json":
                            data = response.json()
                            ret_key = api_info.get("ret_key")
                            ret_success = api_info.get("ret_success")
                            if ret_key and ret_success is not None and data.get(ret_key) != ret_success:
                                continue
                            ip = str(data.get(api_info["key"], "")).strip()
                        else:
                            ip = response.text.strip()
                        if ip and _valid_ipv4(ip):
                            return ip
                except Exception:
                    continue

        if ctx.current_proxy and proxies_dict:
            proxy_ip = extract_ip_from_proxy(ctx.current_proxy)
            if proxy_ip:
                ctx.log(f"所有IP查询API都失败，从代理字符串提取IP: {proxy_ip}")
                return proxy_ip

        if not ctx.current_proxy:
            fallback_apis = [
                {"url": "https://api.xinyew.cn/api/ip", "type": "json", "key": "ip", "ret_key": "ret", "ret_success": 0},
                {"url": "http://httpbin.org/ip", "type": "json", "key": "origin"},
                {"url": "https://httpbin.org/ip", "type": "json", "key": "origin"},
                {"url": "http://api.ipify.org?format=json", "type": "json", "key": "ip"},
            ]
            for api_info in fallback_apis:
                try:
                    response = requests.get(api_info["url"], headers=headers, proxies=None, timeout=(5, 8))
                    if response.status_code == 200:
                        if api_info["type"] == "json":
                            data = response.json()
                            ret_key = api_info.get("ret_key")
                            ret_success = api_info.get("ret_success")
                            if ret_key and ret_success is not None and data.get(ret_key) != ret_success:
                                continue
                            ip = str(data.get(api_info["key"], "")).strip()
                        else:
                            ip = response.text.strip()
                        if ip and _valid_ipv4(ip):
                            return ip
                except Exception:
                    continue

        return "未知"
    except Exception as e:
        ctx.log(f"获取IP地址失败: {str(e)}")
        return "未知"


def get_browser_actual_ip(ctx) -> Optional[str]:
    browser = getattr(ctx.config, "browser", "edge")
    try:
        if browser == "firefox":
            options = FirefoxOptions()
            options.add_argument("--headless")
            if ctx.current_proxy:
                parts = ctx.current_proxy.replace("socks5://", "").replace("http://", "").split(":")
                options.set_preference("network.proxy.type", 1)
                options.set_preference("network.proxy.socks", parts[0])
                options.set_preference("network.proxy.socks_port", int(parts[1]))
            temp_driver = webdriver.Firefox(
                service=FirefoxService(ctx.driver_path) if ctx.driver_path else None,
                options=options
            )
        else:
            OptionsClass = EdgeOptions if browser == "edge" else ChromeOptions
            options = OptionsClass()
            options.add_argument("--headless")
            options.add_argument("--disable-gpu")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-logging")
            options.add_argument("--log-level=3")
            if ctx.current_proxy:
                if ctx.current_proxy.startswith("socks5://"):
                    options.add_argument(f"--proxy-server={ctx.current_proxy}")
                else:
                    parts = ctx.current_proxy.split(":")
                    if len(parts) >= 2:
                        options.add_argument(f"--proxy-server={parts[0]}:{parts[1]}")
            temp_driver = _create_driver(ctx, options, browser)

        temp_driver.set_page_load_timeout(10)
        try:
            for url in ["http://httpbin.org/ip", "http://api.ipify.org?format=json", "http://icanhazip.com"]:
                try:
                    temp_driver.get(url)
                    time.sleep(0.3)
                    page_source = temp_driver.page_source
                    if "json" in url or "httpbin" in url:
                        json_start = page_source.find("{")
                        json_end = page_source.rfind("}") + 1
                        if json_start >= 0 and json_end > json_start:
                            data = json.loads(page_source[json_start:json_end])
                            ip = data.get("origin", "").split(",")[0].strip() or str(data.get("ip", "")).strip()
                            parts = ip.split(".")
                            if len(parts) == 4 and all(p.isdigit() and 0 <= int(p) <= 255 for p in parts):
                                return ip
                    else:
                        import re
                        matches = re.findall(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", page_source)
                        if matches:
                            return matches[0]
                except Exception:
                    continue
        finally:
            quit_driver_quietly(temp_driver)
        return None
    except Exception as e:
        ctx.log(f"通过浏览器获取实际IP时出错: {str(e)}")
        return None
