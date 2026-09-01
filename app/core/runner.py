"""批量处理引擎：逐账号执行 登录 → (重置密码) → 导航 → 发帖/激活 → 回写Excel

从原 main.py（发帖模式）与 main_jihuo.py（激活模式）的 process_student/main 重构而来，
消除全局状态，支持 UI 回调与中途停止。重试策略与原脚本保持一致：
- 代理验证最多 3 次
- 首页访问最多 2 次
- 登录最多重试 1 次
- 发帖最多重试 1 次
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

from selenium.webdriver.support.ui import WebDriverWait

from app.core import auth, browser, excel_service, location_service, posting
from app.core.content import clean_temp_upload_dir
from app.core.excel_service import build_remark, update_remark
from app.core.models import (
    AccountOutcome,
    PipelineContext,
    RunMode,
    RunStats,
    StudentRecord,
)
from app.core.proxy_service import ProxyPool, extract_ip_from_proxy


class _StoppedByUser(Exception):
    """用户主动停止"""


@dataclass
class _SessionState:
    """单账号处理过程中的可变状态"""
    proxy: Optional[str] = None
    location: Optional[dict] = None
    driver: Optional[object] = None
    wait: Optional[object] = None
    login_ip: str = "未知"
    login_location: str = "未知"
    login_password: str = ""
    password_reset: bool = False


class BatchRunner:
    """批量账号处理器"""

    def __init__(self, ctx: PipelineContext):
        self.ctx = ctx
        self.config = ctx.config
        self.log = ctx.log
        if ctx.proxy_pool is None:
            ctx.proxy_pool = ProxyPool(self.config, log=self.log)
        self.pool: ProxyPool = ctx.proxy_pool

    # ============================
    # 对外接口
    # ============================
    def request_stop(self) -> None:
        """请求停止：设置停止标志并强制关闭当前浏览器（解除 Selenium 阻塞）"""
        self.ctx.stop_event.set()
        try:
            if self.ctx.current_driver:
                self.ctx.current_driver.quit()
        except Exception:
            pass

    def run(self) -> RunStats:
        """执行批量处理（在工作线程中调用）"""
        ctx = self.ctx
        config = self.config
        stats = RunStats()
        wb = None

        try:
            # 1. 打开账号表
            self.ctx.events.on_stage("正在读取账号表...")
            wb, ws, records, headers = excel_service.read_student_data(
                config.excel_path, log=lambda m: self.log(m)
            )
            stats.total = len(records)
            if not records:
                self.log("Excel文件中没有账号数据", "WARN")
                ctx.events.on_finished(stats)
                return stats
            remark_col = headers["备注"]

            # 2. 加载已用IP记录
            if config.use_proxy:
                self.pool.load_used_ips()
                self.log(f"已加载 {len(self.pool.used_ips)} 个历史IP记录，避免重复使用（一号一IP）")

            mode_text = "发帖模式" if config.run_mode == RunMode.POST else "激活模式"
            self.log(f"共 {len(records)} 个账号待处理，当前为【{mode_text}】")

            # 3. 逐账号处理
            for i, record in enumerate(records, 1):
                if ctx.stopped():
                    stats.stopped_by_user = True
                    self.log("用户停止，终止剩余账号处理", "WARN")
                    break

                self.log(f"\n{'=' * 40}\n处理进度: {i}/{len(records)}  学号: {record.student_id}\n{'=' * 40}")
                ctx.events.on_progress(i - 1, len(records), record.student_id)
                ctx.events.on_stage(f"正在处理 {record.student_id} ({i}/{len(records)})")

                try:
                    outcome = self._process_account(ws, record, remark_col)
                except _StoppedByUser:
                    stats.stopped_by_user = True
                    self.log("用户停止，当前账号未写回结果", "WARN")
                    break
                except Exception as e:
                    self.log(f"处理学号 {record.student_id} 时发生错误: {str(e)}", "ERROR")
                    outcome = AccountOutcome(success=False, status_code=5, error_message=str(e))

                # 保存 Excel（每个账号落盘一次）
                try:
                    wb.save(config.excel_path)
                except Exception as e:
                    self.log(f"保存Excel失败: {str(e)}", "ERROR")

                # 统计
                if outcome.success:
                    stats.success += 1
                else:
                    stats.failed += 1
                if outcome.password_reset:
                    stats.password_reset += 1
                else:
                    stats.no_password_reset += 1
                stats.status_counts[outcome.status_code] = stats.status_counts.get(outcome.status_code, 0) + 1

                remark_text = ws.cell(row=record.row, column=remark_col).value or ""
                ctx.events.on_account_done(record.student_id, outcome.status_code, str(remark_text))
                ctx.events.on_progress(i, len(records), record.student_id)

                if i % 3 == 0 and i < len(records):
                    self.log(f"已处理 {i} 个账号，休息2秒...")
                    time.sleep(2)

            self.log(f"\n处理完成！\n{stats.as_text()}")
            return stats

        except Exception as e:
            self.log(f"批量处理执行出错: {str(e)}", "ERROR")
            import traceback
            self.log(traceback.format_exc(), "DEBUG")
            return stats
        finally:
            if wb:
                try:
                    wb.save(self.config.excel_path)
                except Exception:
                    pass
            self.ctx.events.on_finished(stats)

    # ============================
    # 单账号处理主流程
    # ============================
    def _process_account(self, ws, record: StudentRecord, remark_col: int) -> AccountOutcome:
        ctx = self.ctx
        config = self.config
        mode = config.run_mode
        state = _SessionState()

        def write_result(outcome: AccountOutcome) -> AccountOutcome:
            remark = build_remark(
                mode, outcome.status_code,
                password_reset=outcome.password_reset,
                error_message=outcome.error_message,
                login_password=outcome.login_password,
                login_ip=outcome.login_ip,
                login_location=outcome.login_location,
                reset_password=config.reset_password,
            )
            update_remark(ws, record.row, remark_col, remark, log=lambda m: self.log(m))
            return outcome

        try:
            # ---- 1. 代理与定位 ----
            self._check_stopped()
            self._prepare_proxy_and_location(state)

            # ---- 2. 验证代理（最多3次，失败仍用最后一个）----
            if state.proxy:
                self._validate_proxy(state)

            # ---- 3. 创建浏览器 ----
            self._recreate_browser(state)

            # ---- 4. 访问首页（带换代理重试）----
            self._open_homepage(state)

            # ---- 5. IP 与归属地 ----
            self._check_stopped()
            self._resolve_ip_and_location(state)

            # ---- 6. 确保处于首页（会话有效）----
            self._ensure_on_homepage(state)

            # ---- 7. 登录（带重试）----
            self._check_stopped()
            login_ok, login_status, login_message = self._login_with_retries(state, record.student_id)

            if not login_ok:
                if mode == RunMode.POST:
                    if login_status == 1:
                        code, msg = 1, "密码错误"
                    elif login_status == 4:
                        code, msg = 4, "账号不存在"
                    elif login_status == 6:
                        code, msg = 6, f"登录状态检查失败: {login_message}"
                    else:
                        code, msg = 5, f"登录失败: {login_message}"
                else:
                    if login_status == 1:
                        code, msg = 2, "密码错误"
                    elif login_status == 4:
                        code, msg = 3, "账号不存在"
                    elif login_status == 6:
                        code, msg = 5, f"登录状态检查失败: {login_message}"
                    else:
                        code, msg = 5, login_message or "登录失败"
                outcome = AccountOutcome(
                    success=False, status_code=code, error_message=msg,
                    password_reset=state.password_reset, login_password=state.login_password,
                    login_ip=state.login_ip, login_location=state.login_location,
                )
                self._close_session(state, do_logout=True)
                return write_result(outcome)

            # ---- 8.（激活模式专属）登录成功后强制改密 ----
            if mode == RunMode.ACTIVATE:
                if state.login_password == config.reset_password:
                    self.log("使用重置密码登录成功，跳过强制修改密码步骤")
                else:
                    try:
                        auth.force_change_password_in_settings(
                            ctx, state.driver, current_password=state.login_password
                        )
                        state.password_reset = True
                        state.login_password = config.reset_password
                    except Exception as e:
                        self.log(f"强制修改密码时出错: {str(e)}，继续执行...")
                # 回首页
                try:
                    state.driver.get(config.target_url)
                    time.sleep(1)
                except Exception as e:
                    self.log(f"返回首页时出错: {str(e)}，继续执行...")

            # ---- 9. 导航到芯泉子/发帖页 ----
            self._check_stopped()
            nav_ok, nav_status, nav_error = posting.navigate_to_post_page(ctx, state.driver, state.wait)
            if not nav_ok:
                if nav_status == 7:
                    code, msg = 7, f"无法找到发帖页面: {nav_error}"
                elif nav_status == 8:
                    code, msg = 8, f"无法点击'开始对话': {nav_error}"
                elif nav_status == 9:
                    code, msg = 9, f"无法点击'芯泉子': {nav_error}"
                else:
                    code, msg = 5, f"导航失败: {nav_error}"
                outcome = AccountOutcome(
                    success=False, status_code=code, error_message=msg,
                    password_reset=state.password_reset, login_password=state.login_password,
                    login_ip=state.login_ip, login_location=state.login_location,
                )
                self._close_session(state, do_logout=True)
                return write_result(outcome)

            # ---- 10. 模式分支：激活成功 / 发帖 ----
            self._check_stopped()
            if mode == RunMode.ACTIVATE:
                outcome = AccountOutcome(
                    success=True, status_code=1,
                    password_reset=state.password_reset, login_password=state.login_password,
                    login_ip=state.login_ip, login_location=state.login_location,
                )
                self._close_session(state, do_logout=True)
                return write_result(outcome)

            # 发帖（带重试与网络超时重登录）
            post_ok, post_error = self._post_with_retries(state, record.student_id)
            if post_ok:
                outcome = AccountOutcome(
                    success=True, status_code=2,
                    password_reset=state.password_reset, login_password=state.login_password,
                    login_ip=state.login_ip, login_location=state.login_location,
                )
            else:
                outcome = AccountOutcome(
                    success=False, status_code=3, error_message=f"发帖失败: {post_error}",
                    password_reset=state.password_reset, login_password=state.login_password,
                    login_ip=state.login_ip, login_location=state.login_location,
                )
            self._close_session(state, do_logout=True)
            return write_result(outcome)

        except _StoppedByUser:
            self._close_session(state, do_logout=False)
            raise
        except Exception as e:
            self.log(f"处理过程中出现异常: {str(e)}", "ERROR")
            if state.login_location == "未知" and state.login_ip != "未知":
                try:
                    state.login_location = location_service.format_location(
                        state.login_ip, log=self.log
                    )
                except Exception:
                    pass
            outcome = AccountOutcome(
                success=False, status_code=5, error_message=f"处理过程中出现异常: {str(e)}",
                password_reset=state.password_reset, login_password=state.login_password,
                login_ip=state.login_ip, login_location=state.login_location,
            )
            self._close_session(state, do_logout=True)
            return write_result(outcome)

    # ============================
    # 流程阶段
    # ============================
    def _check_stopped(self) -> None:
        if self.ctx.stopped():
            raise _StoppedByUser()

    def _prepare_proxy_and_location(self, state: _SessionState) -> None:
        """按配置获取代理与虚拟定位"""
        config = self.config
        ctx = self.ctx

        if config.use_proxy:
            self.ctx.events.on_stage("正在获取代理IP...")
            state.proxy = self.pool.get_and_record_proxy(exclude_used_ips=True)
        else:
            state.proxy = None
        ctx.current_proxy = state.proxy

        if state.proxy:
            self.log(f"已获取代理: {state.proxy} (IP: {extract_ip_from_proxy(state.proxy) or '无法提取'})")
        else:
            self.log("未使用代理，将使用本地连接" if not config.use_proxy else "未获取到代理，将使用本地连接")

        if config.use_virtual_location:
            state.location = location_service.get_random_location(log=self.log)
            self.log(
                f"已获取虚拟定位: 纬度={state.location['latitude']:.4f}, "
                f"经度={state.location['longitude']:.4f}"
            )
        else:
            state.location = None
            self.log("未启用虚拟定位，将使用真实地理位置")

    def _validate_proxy(self, state: _SessionState) -> None:
        """验证代理连通性与目标网站可达性（最多3次，全部失败仍保留最后一个代理）"""
        max_retries = 3
        retry = 0
        original_proxy = state.proxy

        while retry < max_retries:
            if retry > 0:
                self.log(f"尝试获取新代理（重试 {retry}/{max_retries}）...")
                state.proxy = self.pool.get_and_record_proxy(exclude_used_ips=True)
                self.ctx.current_proxy = state.proxy
                if not state.proxy:
                    retry += 1
                    continue

            if not self.pool.test_proxy_connection(state.proxy):
                self.log(f"警告: 代理连接验证失败: {state.proxy}")
                retry += 1
                continue

            if self.pool.test_proxy_target_website(state.proxy, self.config.target_url):
                self.log(f"代理验证成功: {state.proxy}")
                return
            self.log(f"警告: 代理无法访问目标网站: {state.proxy}")
            retry += 1

        self.log(f"已尝试 {max_retries} 个代理均验证失败，将继续使用最后一个代理（浏览器可能可处理SSL问题）")
        if not state.proxy:
            state.proxy = original_proxy
            self.ctx.current_proxy = state.proxy

    def _recreate_browser(self, state: _SessionState) -> None:
        """关闭旧浏览器并创建新实例"""
        browser.quit_driver_quietly(state.driver)
        state.driver = browser.setup_driver(self.ctx, proxy=state.proxy, location=state.location)
        state.wait = WebDriverWait(state.driver, self.config.explicit_wait)
        self.ctx.current_driver = state.driver
        self.log("已创建新的浏览器实例，IP和定位已随机化")
        time.sleep(1)

    def _open_homepage(self, state: _SessionState) -> None:
        """访问首页：超时/访问失败时更换代理重建浏览器（最多2次）"""
        max_retry = 2
        retry = 0

        while retry < max_retry:
            try:
                try:
                    self.log(f"正在访问首页: {self.config.target_url} "
                             f"(使用代理: {state.proxy if state.proxy else '本地连接'})")
                    state.driver.get(self.config.target_url)
                    time.sleep(1)
                except Exception as page_error:
                    error_msg = str(page_error).lower()
                    if "timeout" in error_msg or "timed out" in error_msg:
                        self.log(f"页面加载超时: {str(page_error)}")
                        if state.proxy and retry + 1 < max_retry:
                            retry += 1
                            self._swap_proxy_and_browser(state)
                            continue
                        # 非代理或重试用尽：超时也继续后续流程
                    else:
                        raise

                # 会话检查
                if not browser.check_driver_session(state.driver):
                    self.log("浏览器会话在访问首页后断开，重新创建浏览器实例...")
                    self._recreate_browser(state)
                    state.driver.get(self.config.target_url)
                    time.sleep(2)

                if browser.check_page_access_success(state.driver):
                    self.log("页面访问成功")
                    return

                # 访问失败：检查 IP 连接是否稳定
                self.log("页面访问失败，检查IP连接是否稳定...")
                test_ip = browser.get_current_ip(self.ctx)
                if test_ip and test_ip != "未知":
                    self.log(f"IP连接稳定（IP: {test_ip}），但页面访问失败，可能是代理被网站封禁")
                    retry += 1
                    if retry < max_retry:
                        self._swap_proxy_and_browser(state)
                        continue
                    self.log("已达到最大重试次数，继续使用当前连接")
                    return
                else:
                    self.log("IP连接也不稳定，代理可能完全不可用")
                    if state.proxy and retry < max_retry - 1:
                        retry += 1
                        self._swap_proxy_and_browser(state)
                        continue
                    self.log("无法获取稳定IP，继续使用当前连接")
                    return

            except Exception as e:
                self.log(f"访问首页时出错: {str(e)}")
                retry += 1
                if retry < max_retry:
                    time.sleep(2)
                else:
                    return

    def _swap_proxy_and_browser(self, state: _SessionState) -> None:
        """更换代理并重建浏览器"""
        self.log("尝试更换代理...")
        if self.config.use_proxy:
            state.proxy = self.pool.get_and_record_proxy(exclude_used_ips=True)
            self.ctx.current_proxy = state.proxy
            if state.proxy:
                self.log(f"已获取新代理: {state.proxy} (IP: {extract_ip_from_proxy(state.proxy)})")
                if not self.pool.test_proxy_connection(state.proxy):
                    self.log("警告: 新代理连接验证失败，将使用本地连接")
                    state.proxy = None
                    self.ctx.current_proxy = None
            else:
                self.log("未获取到可用代理，将使用本地连接")
        self._recreate_browser(state)

    def _resolve_ip_and_location(self, state: _SessionState) -> None:
        """获取出口IP、校验浏览器实际IP、确定登录地区"""
        config = self.config
        state.login_ip = browser.get_current_ip(self.ctx)
        self.log(f"当前登录IP: {state.login_ip}")

        # 校验浏览器实际使用的IP（无头浏览器同代理检测）
        if state.proxy:
            browser_actual_ip = browser.get_browser_actual_ip(self.ctx)
            if browser_actual_ip:
                self.log(f"浏览器实际使用的IP: {browser_actual_ip}")
                if browser_actual_ip != state.login_ip:
                    self.log(f"警告: 浏览器实际IP ({browser_actual_ip}) 与代理IP ({state.login_ip}) 不一致！", "WARN")
                    state.login_ip = browser_actual_ip
                else:
                    self.log(f"验证通过: 浏览器实际IP与代理IP一致 ({state.login_ip})")
            else:
                self.log("警告: 无法获取浏览器实际IP，可能代理认证失败", "WARN")

        # 本地连接也记录IP，避免多账号同IP
        if not state.proxy and state.login_ip and state.login_ip != "未知":
            if state.login_ip not in self.pool.used_ips:
                self.pool.record_ip(state.login_ip)
                self.log(f"已记录本地IP: {state.login_ip}")
            else:
                self.log(f"警告: 本地IP {state.login_ip} 已被使用，多个账号可能使用相同IP", "WARN")

        # 登录地区
        if config.use_virtual_location and state.location:
            if state.location.get("city_name"):
                state.login_location = state.location["city_name"]
            else:
                state.login_location = location_service.get_city_name_from_coordinates(
                    state.location["latitude"], state.location["longitude"],
                    config.amap_key, log=self.log,
                )
                if state.login_location == "未知":
                    state.login_location = location_service.format_location(state.login_ip, log=self.log)
            self.log(f"登录地区（虚拟定位）: {state.login_location}")
        else:
            state.login_location = location_service.format_location(state.login_ip, log=self.log)
            self.log(f"登录地区（IP位置）: {state.login_location}")

    def _ensure_on_homepage(self, state: _SessionState) -> None:
        """确保浏览器会话有效且位于首页"""
        if not browser.check_driver_session(state.driver):
            self.log("浏览器会话断开，重新创建浏览器实例...")
            self._recreate_browser(state)
            state.driver.get(self.config.target_url)
            time.sleep(1)
            return
        try:
            current_url = state.driver.current_url
            if "beeline-ai.com" not in current_url:
                state.driver.get(self.config.target_url)
                time.sleep(1)
        except Exception:
            self._recreate_browser(state)
            state.driver.get(self.config.target_url)
            time.sleep(1)

    def _login_with_retries(self, state: _SessionState, student_id: str):
        """登录（最多重试1次；代理断开时换代理重建浏览器重试）。

        返回 (成功, 状态码或None, 消息)
        """
        max_retries = 1
        retry = 0

        while retry <= max_retries:
            self._check_stopped()
            try:
                result, status, password_reset, message, login_password = auth.login_with_student(
                    self.ctx, state.driver, state.wait, student_id
                )
                if password_reset:
                    state.password_reset = True
                if login_password:
                    state.login_password = login_password

                if result:
                    return True, None, message

                if retry < max_retries and browser.check_proxy_disconnected(self.ctx, state.driver):
                    self.log("检测到代理断开，重新获取代理并重试登录...", "WARN")
                    retry += 1
                    self._swap_proxy_and_browser(state)
                    state.driver.get(self.config.target_url)
                    time.sleep(1)
                    continue

                self.log(f"登录失败: {message}，不再重试")
                return False, status, message

            except _StoppedByUser:
                raise
            except Exception as e:
                error_msg = str(e).lower()
                is_timeout = "timeout" in error_msg or "timed out" in error_msg
                is_session_error = "session" in error_msg or "disconnected" in error_msg
                if (is_timeout or is_session_error) and retry < max_retries:
                    retry += 1
                    if browser.check_proxy_disconnected(self.ctx, state.driver):
                        self.log("检测到代理断开，重新获取代理并重试登录...", "WARN")
                        self._swap_proxy_and_browser(state)
                        state.driver.get(self.config.target_url)
                        time.sleep(1)
                    else:
                        time.sleep(2)
                    continue
                self.log(f"登录时发生错误: {str(e)}", "ERROR")
                return False, 5, str(e)

        return False, 5, "登录重试次数用尽"

    def _post_with_retries(self, state: _SessionState, student_id: str):
        """发帖（最多重试1次；网络超时→重登录；代理断开→换代理重建）。

        返回 (成功, 错误消息)
        """
        max_retries = 1
        retry = 0

        while retry <= max_retries:
            self._check_stopped()
            try:
                post_success, post_error = posting.create_post(
                    self.ctx, state.driver, state.wait, student_id
                )
                if post_success:
                    return True, ""

                # 网络超时：退出登录 → 重新登录 → 重新导航 → 重发（不计重试次数）
                if post_error == "网络超时":
                    self.log("检测到网络超时，退出登录并重新登录...", "WARN")
                    if not self._relogin_and_renavigate(state, student_id):
                        return False, "重新登录或重新导航失败"
                    continue

                if retry < max_retries and browser.check_proxy_disconnected(self.ctx, state.driver):
                    self.log("检测到代理断开，换代理重建浏览器并重试发帖...", "WARN")
                    retry += 1
                    self._swap_proxy_and_browser(state)
                    state.driver.get(self.config.target_url)
                    time.sleep(1)
                    if not self._relogin_and_renavigate(state, student_id):
                        return False, "重新登录或重新导航失败"
                    continue

                self.log(f"发帖失败: {post_error}，不再重试")
                return False, post_error

            except _StoppedByUser:
                raise
            except Exception as e:
                error_msg = str(e).lower()
                is_timeout = "timeout" in error_msg or "timed out" in error_msg
                is_session_error = "session" in error_msg or "disconnected" in error_msg
                if (is_timeout or is_session_error) and retry < max_retries:
                    retry += 1
                    if browser.check_proxy_disconnected(self.ctx, state.driver):
                        self.log("检测到代理断开，换代理重建浏览器并重试发帖...", "WARN")
                        self._swap_proxy_and_browser(state)
                        state.driver.get(self.config.target_url)
                        time.sleep(1)
                        if not self._relogin_and_renavigate(state, student_id):
                            return False, f"重新登录或重新导航失败: {str(e)}"
                    else:
                        time.sleep(2)
                    continue
                return False, str(e)

        return False, "发帖重试次数用尽"

    def _relogin_and_renavigate(self, state: _SessionState, student_id: str) -> bool:
        """退出登录 → 重新登录 → 重新导航到发帖页"""
        try:
            auth.logout(self.ctx, state.driver, state.wait)
        except Exception:
            pass
        time.sleep(1)

        result, status, password_reset, message, login_password = auth.login_with_student(
            self.ctx, state.driver, state.wait, student_id
        )
        if not result:
            self.log(f"重新登录失败: {message}")
            return False
        if password_reset:
            state.password_reset = True
        if login_password:
            state.login_password = login_password

        nav_ok, nav_status, nav_error = posting.navigate_to_post_page(
            self.ctx, state.driver, state.wait
        )
        if not nav_ok:
            self.log(f"重新导航到发帖页面失败: {nav_error}")
            return False
        self.log("已重新登录并导航到发帖页面")
        return True

    def _close_session(self, state: _SessionState, do_logout: bool) -> None:
        """收尾：退出登录（可选）、清理临时目录、关闭浏览器"""
        try:
            if state.driver and do_logout:
                auth.logout(self.ctx, state.driver, state.wait)
        except Exception:
            pass
        clean_temp_upload_dir(self.config.temp_upload_dir, log=lambda m: self.log(m))
        browser.quit_driver_quietly(state.driver)
        if self.ctx.current_driver is state.driver:
            self.ctx.current_driver = None
        state.driver = None
        state.wait = None
