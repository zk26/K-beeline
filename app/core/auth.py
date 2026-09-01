"""登录认证服务：登录、协议勾选、密码重置、登录结果检测、退出"""
from __future__ import annotations

import time

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from app.core.browser import check_driver_session


def click_login_button(ctx, driver, wait) -> bool:
    """点击首页的登录按钮"""
    try:
        if not check_driver_session(driver):
            ctx.log("浏览器会话无效，无法点击登录按钮")
            return False
        login_btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, ".login-btn.flex-center")))
        driver.execute_script("arguments[0].click();", login_btn)
        ctx.log("点击首页登录按钮成功")
        time.sleep(0.5)
        return True
    except Exception as e:
        ctx.log(f"点击首页登录按钮失败: {str(e)}")
        return False


def check_agreement(ctx, driver, wait) -> bool:
    """勾选同意协议"""
    try:
        time.sleep(0.2)
        try:
            agreement_container = WebDriverWait(driver, 2).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".agreement-content.flex-center"))
            )
            checkboxes = agreement_container.find_elements(By.CSS_SELECTOR, "input[type='checkbox']")
            if checkboxes:
                checkbox = checkboxes[0]
                if not checkbox.is_selected():
                    try:
                        driver.execute_script("arguments[0].click();", checkbox)
                        time.sleep(0.1)
                        return True
                    except Exception:
                        checkbox.click()
                        time.sleep(0.1)
                        return True
                return True
            else:
                try:
                    driver.execute_script("arguments[0].click();", agreement_container)
                    time.sleep(0.1)
                    return True
                except Exception:
                    agreement_container.click()
                    time.sleep(0.1)
                    return True
        except Exception as e:
            ctx.log(f"查找协议容器失败: {str(e)}")
            return False
    except Exception as e:
        ctx.log(f"勾选同意协议时发生错误: {str(e)}")
        return False


def wait_login_button_enabled(ctx, driver, wait) -> bool:
    """等待登录按钮变为可用状态"""
    try:
        short_wait = WebDriverWait(driver, 1)
        short_wait.until(
            EC.element_to_be_clickable((
                By.CSS_SELECTOR,
                ".login-button .el-button.el-button--primary.el-button--large:not(.is-disabled)",
            ))
        )
        return True
    except Exception:
        try:
            buttons = driver.find_elements(
                By.CSS_SELECTOR, ".login-button .el-button.el-button--primary.el-button--large"
            )
            for btn in buttons:
                if "is-disabled" not in (btn.get_attribute("class") or ""):
                    return True
        except Exception:
            pass
        return False


def click_submit_login(ctx, driver, wait) -> bool:
    """点击提交登录按钮"""
    try:
        login_buttons = driver.find_elements(
            By.CSS_SELECTOR, ".login-button .el-button.el-button--primary.el-button--large"
        )
        for btn in login_buttons:
            if "is-disabled" not in (btn.get_attribute("class") or ""):
                driver.execute_script("arguments[0].click();", btn)
                ctx.log("点击提交登录按钮成功")
                return True
            else:
                return False

        submit_btns = driver.find_elements(By.CSS_SELECTOR, ".el-button--primary")
        for btn in submit_btns:
            if "登录" in btn.text and "is-disabled" not in (btn.get_attribute("class") or ""):
                driver.execute_script("arguments[0].click();", btn)
                ctx.log("点击备用登录按钮成功")
                return True
        return False
    except Exception as e:
        ctx.log(f"点击提交登录按钮失败: {str(e)}")
        return False


def handle_password_reset(ctx, driver, wait) -> bool:
    """处理密码重置弹窗"""
    reset_password = ctx.config.reset_password
    try:
        for i in range(2):
            try:
                reset_dialog = driver.find_elements(
                    By.CSS_SELECTOR,
                    ".el-dialog.el-dialog--center.public-dialog-center.modify-password-dialog",
                )
                if reset_dialog:
                    for dialog in reset_dialog:
                        if dialog.is_displayed():
                            ctx.log("检测到密码重置弹窗，正在重置密码...")
                            password_inputs = dialog.find_elements(By.CSS_SELECTOR, "input[type='password']")
                            if len(password_inputs) >= 2:
                                password_inputs[0].send_keys(reset_password)
                                time.sleep(0.1)
                                password_inputs[1].send_keys(reset_password)
                                time.sleep(0.1)
                                confirm_buttons = dialog.find_elements(By.CSS_SELECTOR, ".el-button--primary")
                                for btn in confirm_buttons:
                                    if "确定" in btn.text or "确认" in btn.text:
                                        btn.click()
                                        ctx.log(f"密码重置成功，新密码: {reset_password}")
                                        time.sleep(0.5)
                                        return True
                            break
            except Exception:
                pass
            if i < 1:
                time.sleep(0.1)
        return False
    except Exception:
        return False


def check_login_success_by_start_conversation(ctx, driver, wait):
    """通过"开始对话"按钮判断登录是否成功。返回 (是否成功, 消息)"""
    try:
        error_selectors = [
            ".el-message--error",
            ".el-message.error",
            ".el-notification--error",
            ".el-notification.error",
            ".el-message",
            ".el-notification",
        ]

        # 1. 检查错误吐司
        try:
            for selector in error_selectors:
                try:
                    for error in driver.find_elements(By.CSS_SELECTOR, selector):
                        if error.is_displayed():
                            error_text = error.text.strip()
                            if error_text:
                                if "账号已被锁定" in error_text or ("锁定" in error_text and "15分钟" in error_text):
                                    return False, error_text
                                if ("账号" in error_text or "账户" in error_text) and (
                                    "不存在" in error_text or "错误" in error_text or "无效" in error_text
                                ):
                                    return False, "账号不存在或错误"
                                if "密码" in error_text and (
                                    "错误" in error_text or "不正确" in error_text or "失败" in error_text
                                ):
                                    return False, "密码错误"
                                if "登录失败" in error_text or "登录错误" in error_text or "验证失败" in error_text:
                                    return False, f"登录失败: {error_text}"
                except Exception:
                    continue

            # XPath 兜底查找错误文本
            for keyword in ["账号已被锁定", "密码错误", "账号不存在", "登录失败", "密码不正确"]:
                try:
                    for error in driver.find_elements(By.XPATH, f"//*[contains(text(), '{keyword}')]"):
                        if error.is_displayed():
                            full_text = error.text.strip()
                            if keyword in full_text:
                                if "账号已被锁定" in full_text or ("锁定" in full_text and "15分钟" in full_text):
                                    return False, full_text
                                if "密码" in full_text and "错误" in full_text:
                                    return False, "密码错误"
                                if "账号" in full_text and "不存在" in full_text:
                                    return False, "账号不存在或错误"
                                return False, full_text
                except Exception:
                    continue
        except Exception as e:
            ctx.log(f"检查错误提示时出错: {str(e)}")

        # 2. 检查"开始对话"按钮
        try:
            for element in driver.find_elements(By.XPATH, "//*[contains(text(), '开始对话')]"):
                if element.is_displayed() and element.is_enabled():
                    return True, "登录成功"
        except Exception:
            pass

        # 3. 轮询复查
        for i in range(2):
            if i > 0:
                time.sleep(0.1)
            try:
                for selector in error_selectors:
                    try:
                        for error in driver.find_elements(By.CSS_SELECTOR, selector):
                            if error.is_displayed():
                                error_text = error.text.strip()
                                if error_text and (
                                    "密码" in error_text or "账号" in error_text
                                    or "错误" in error_text or "锁定" in error_text
                                ):
                                    if "账号已被锁定" in error_text or ("锁定" in error_text and "15分钟" in error_text):
                                        return False, error_text
                                    if "密码" in error_text and "错误" in error_text:
                                        return False, "密码错误"
                                    if "账号" in error_text and ("不存在" in error_text or "错误" in error_text):
                                        return False, "账号不存在或错误"
                    except Exception:
                        continue
            except Exception:
                pass
            try:
                for element in driver.find_elements(By.XPATH, "//*[contains(text(), '开始对话')]"):
                    if element.is_displayed() and element.is_enabled():
                        return True, "登录成功"
            except Exception:
                pass

        return False, "未找到'开始对话'按钮，登录可能失败"
    except Exception as e:
        return False, f"检查登录状态时出错: {str(e)}"


def login_with_student(ctx, driver, wait, student_id: str):
    """使用学生账号登录。

    返回: (成功, 状态码或None, 是否重置密码, 消息, 登录密码)
    状态码: 1=密码错误 4=账号不存在 5=其他错误 6=登录状态检查失败 None=成功
    """
    if not check_driver_session(driver):
        return False, 5, False, "浏览器会话断开，需要重新创建浏览器", ""

    config = ctx.config
    username = f"{config.account_prefix}{student_id}"
    ctx.log(f"正在为学号 {student_id} 登录... 账号: {username}")

    password_reset = False
    login_password = ""
    login_attempts = []

    for password_index, password in enumerate(config.password_options):
        if not check_driver_session(driver):
            error_msg = "浏览器会话断开"
            if login_attempts:
                error_msg += f" ({'; '.join(login_attempts)})"
            return False, 5, password_reset, error_msg, login_password
        try:
            ctx.log(f"尝试使用第{password_index + 1}个密码: {password}")

            if not click_login_button(ctx, driver, wait):
                login_attempts.append(f"密码{password_index + 1}: 无法点击首页登录按钮")
                continue

            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='text']")))
            time.sleep(0.2)

            inputs = driver.find_elements(By.CSS_SELECTOR, "input")
            if len(inputs) >= 2:
                inputs[0].clear()
                inputs[0].send_keys(username)
                time.sleep(0.2)

                inputs[1].clear()
                inputs[1].send_keys(password)
                time.sleep(0.2)

                if check_agreement(ctx, driver, wait):
                    ctx.log("已成功勾选同意协议")

                if not wait_login_button_enabled(ctx, driver, wait):
                    login_attempts.append(f"密码{password_index + 1}: 登录按钮禁用")
                    continue

                if not click_submit_login(ctx, driver, wait):
                    login_attempts.append(f"密码{password_index + 1}: 无法点击登录按钮")
                    continue

                ctx.log("提交登录信息")
                # 吐司检测：点击后0.3秒内无吐司即可点击"开始对话"
                login_success = False
                login_message = ""
                error_found = False
                error_text = ""
                reset_dialog_found = False

                time.sleep(0.3)

                # 1. 快速检查错误吐司
                try:
                    for selector in [".el-message--error", ".el-message.error",
                                     ".el-notification--error", ".el-notification.error"]:
                        try:
                            for error in driver.find_elements(By.CSS_SELECTOR, selector)[:3]:
                                try:
                                    if error.is_displayed():
                                        text = error.text.strip()
                                        if text:
                                            error_found = True
                                            error_text = text
                                            break
                                except Exception:
                                    continue
                            if error_found:
                                break
                        except Exception:
                            continue
                    if not error_found:
                        try:
                            for error in driver.find_elements(By.CSS_SELECTOR, ".el-message")[:2]:
                                try:
                                    if error.is_displayed():
                                        text = error.text.strip()
                                        if text and ("错误" in text or "失败" in text or "不存在" in text):
                                            error_found = True
                                            error_text = text
                                            break
                                except Exception:
                                    continue
                        except Exception:
                            pass
                except Exception:
                    pass

                # 2. 检查密码重置弹窗
                try:
                    for dialog in driver.find_elements(
                        By.CSS_SELECTOR,
                        ".el-dialog.el-dialog--center.public-dialog-center.modify-password-dialog",
                    ):
                        try:
                            if dialog.is_displayed():
                                reset_dialog_found = True
                                break
                        except Exception:
                            continue
                except Exception:
                    pass

                # 3. 无吐司无弹窗 → 直接点"开始对话"
                if not error_found and not reset_dialog_found:
                    try:
                        for element in driver.find_elements(By.XPATH, "//*[contains(text(), '开始对话')]"):
                            try:
                                if element.is_displayed() and element.is_enabled():
                                    try:
                                        driver.execute_script("arguments[0].click();", element)
                                        login_success = True
                                        login_message = "登录成功（0.3秒内无吐司）"
                                        break
                                    except Exception:
                                        login_success = True
                                        login_message = "登录成功（找到'开始对话'按钮）"
                                        break
                            except Exception:
                                continue
                    except Exception:
                        pass

                # 4. 最终检查
                if not error_found and not login_success and not reset_dialog_found:
                    login_success, login_message = check_login_success_by_start_conversation(ctx, driver, wait)

                # ---------- 处理检测结果 ----------
                if error_found:
                    if "账号已被锁定" in error_text or ("锁定" in error_text and "15分钟" in error_text):
                        return False, 5, password_reset, error_text, password
                    if "密码" in error_text and ("错误" in error_text or "不正确" in error_text):
                        login_attempts.append(f"密码{password_index + 1}: 密码错误")
                        if password_index == len(config.password_options) - 1:
                            return False, 1, password_reset, "", "初始密码"
                        continue
                    elif "账号" in error_text and ("不存在" in error_text or "错误" in error_text):
                        return False, 4, password_reset, "账号不存在", password
                    else:
                        if password_index == len(config.password_options) - 1:
                            return False, 5, password_reset, error_text or "登录失败（未知错误）", password
                        login_attempts.append(f"密码{password_index + 1}: {error_text or '未知错误'}")
                        continue

                if login_success:
                    login_password = password
                    return True, None, password_reset, login_message, login_password

                if reset_dialog_found:
                    reset_result = handle_password_reset(ctx, driver, wait)
                    if reset_result:
                        password_reset = True
                        login_password = config.reset_password
                        time.sleep(0.2)
                        try:
                            login_dialog_visible = False
                            for inp in driver.find_elements(By.CSS_SELECTOR, "input[type='text']"):
                                try:
                                    if inp.is_displayed():
                                        login_dialog_visible = True
                                        break
                                except Exception:
                                    pass
                            if not login_dialog_visible:
                                for element in driver.find_elements(By.XPATH, "//*[contains(text(), '开始对话')]"):
                                    if element.is_displayed() and element.is_enabled():
                                        login_success = True
                                        login_message = "登录成功"
                                        break
                        except Exception:
                            pass
                        if not login_success:
                            login_success, login_message = check_login_success_by_start_conversation(ctx, driver, wait)
                    else:
                        login_password = password
                        login_success, login_message = check_login_success_by_start_conversation(ctx, driver, wait)
                else:
                    login_password = password
                    if not login_success:
                        login_success, login_message = check_login_success_by_start_conversation(ctx, driver, wait)

                # ---------- 统一处理登录结果 ----------
                if login_success:
                    return True, None, password_reset, login_message, login_password

                if "账号已被锁定" in login_message or ("锁定" in login_message and "15分钟" in login_message):
                    return False, 5, password_reset, login_message, login_password
                if "账号不存在" in login_message:
                    return False, 4, password_reset, "账号不存在", login_password
                elif "密码错误" in login_message:
                    login_attempts.append(f"密码{password_index + 1}: 密码错误")
                    if password_index == len(config.password_options) - 1:
                        return False, 1, password_reset, "", "初始密码"
                    continue
                else:
                    login_attempts.append(f"密码{password_index + 1}: {login_message}")
                    if password_index == len(config.password_options) - 1:
                        if "密码错误" in login_message:
                            return False, 1, password_reset, "", "初始密码"
                        return False, 6, password_reset, "", login_password
                    continue

        except Exception as e:
            ctx.log(f"第{password_index + 1}个密码登录过程中出现错误: {str(e)}")
            login_attempts.append(f"密码{password_index + 1}: 异常错误 - {str(e)}")
            if password_index == len(config.password_options) - 1:
                return False, 5, password_reset, "", login_password
            continue

    return False, 1, password_reset, "", "初始密码"


def force_change_password_in_settings(ctx, driver, current_password: str = "") -> bool:
    """（激活模式）强制在账号设置中修改密码为 reset_password。

    流程：新标签页打开账号设置 → 点击"修改" → 填写当前/新/确认密码 → 确认 → 检测吐司。
    """
    new_password = ctx.config.reset_password
    if not current_password:
        current_password = new_password
    try:
        ctx.log("开始强制修改密码（在账号设置中）...")

        original_window = driver.current_window_handle

        # 新标签页打开账号设置
        driver.execute_script(f"window.open('{ctx.config.target_url.rstrip('/')}/personal/account', '_blank');")
        time.sleep(1)

        new_window = None
        for window in driver.window_handles:
            if window != original_window:
                new_window = window
                driver.switch_to.window(window)
                break
        if not new_window:
            raise Exception("无法打开新标签页")
        time.sleep(2)

        # 等待并点击"修改"按钮
        try:
            WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "span.xiugai"))
            )
        except Exception:
            try:
                WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.XPATH, "//span[contains(text(),'修改')]"))
                )
            except Exception:
                ctx.log("等待修改按钮超时，继续尝试...")

        modify_button = None
        try:
            modify_button = driver.find_element(By.CSS_SELECTOR, "span.xiugai")
        except Exception:
            try:
                modify_button = driver.find_element(By.XPATH, "//span[contains(text(),'修改')]")
            except Exception:
                for span in driver.find_elements(By.TAG_NAME, "span"):
                    if span.text and "修改" in span.text:
                        modify_button = span
                        break
        if not modify_button:
            raise Exception("未找到修改按钮")
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", modify_button)
        time.sleep(0.3)
        try:
            modify_button.click()
        except Exception:
            driver.execute_script("arguments[0].click();", modify_button)
        time.sleep(1)

        # 等待密码修改弹窗
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((
                By.CSS_SELECTOR, ".el-dialog.password-dialog, .el-dialog.body-setting-pwd"
            ))
        )
        time.sleep(0.2)

        # 填写当前密码
        old_password_field = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((
                By.XPATH, "//input[@type='password' and @placeholder='当前密码']"
            ))
        )
        driver.execute_script("arguments[0].value = arguments[1];", old_password_field, current_password)
        driver.execute_script(
            "arguments[0].dispatchEvent(new Event('input', { bubbles: true }));", old_password_field
        )
        time.sleep(0.1)

        # 填写新密码
        new_password_field = None
        for placeholder in ["新密码", "请输入新密码", "设置新密码"]:
            try:
                new_password_field = driver.find_element(
                    By.XPATH, f"//input[@type='password' and contains(@placeholder, '{placeholder}')]"
                )
                if new_password_field:
                    break
            except Exception:
                continue
        if not new_password_field:
            password_inputs = driver.find_elements(
                By.CSS_SELECTOR, ".password-dialog input[type='password'], .body-setting-pwd input[type='password']"
            )
            if len(password_inputs) >= 2:
                new_password_field = password_inputs[1]
        if not new_password_field:
            raise Exception("未找到新密码输入框")
        driver.execute_script("arguments[0].value = arguments[1];", new_password_field, new_password)
        driver.execute_script(
            "arguments[0].dispatchEvent(new Event('input', { bubbles: true }));", new_password_field
        )
        time.sleep(0.1)

        # 填写确认新密码
        confirm_password_field = None
        for placeholder in ["确认新密码", "请再次输入新密码", "确认密码", "请确认新密码"]:
            try:
                confirm_password_field = driver.find_element(
                    By.XPATH, f"//input[@type='password' and contains(@placeholder, '{placeholder}')]"
                )
                if confirm_password_field:
                    break
            except Exception:
                continue
        if not confirm_password_field:
            password_inputs = driver.find_elements(
                By.CSS_SELECTOR, ".password-dialog input[type='password'], .body-setting-pwd input[type='password']"
            )
            if len(password_inputs) >= 3:
                confirm_password_field = password_inputs[2]
        if not confirm_password_field:
            raise Exception("未找到确认新密码输入框")
        driver.execute_script("arguments[0].value = arguments[1];", confirm_password_field, new_password)
        driver.execute_script(
            "arguments[0].dispatchEvent(new Event('input', { bubbles: true }));", confirm_password_field
        )
        time.sleep(0.1)

        # 点击确认按钮
        confirm_button = None
        try:
            confirm_button = WebDriverWait(driver, 3).until(
                EC.element_to_be_clickable((
                    By.XPATH,
                    "//div[contains(@class, 'password-dialog')]//button[contains(text(),'确认')] | "
                    "//div[contains(@class, 'body-setting-pwd')]//button[contains(text(),'确认')]",
                ))
            )
        except Exception:
            for btn in driver.find_elements(
                By.CSS_SELECTOR, ".password-dialog button, .body-setting-pwd button"
            ):
                if btn.text and "确认" in btn.text:
                    confirm_button = btn
                    break
        if not confirm_button:
            raise Exception("未找到确认按钮")
        confirm_button.click()
        time.sleep(0.3)

        # 检测吐司提示
        try:
            time.sleep(0.2)
            success = False
            toast_message = ""
            for selector in [".el-message--success", ".el-message.success",
                             ".el-notification--success", ".el-notification.success"]:
                try:
                    for elem in driver.find_elements(By.CSS_SELECTOR, selector):
                        if elem.is_displayed() and elem.text:
                            success = True
                            toast_message = elem.text
                            break
                    if success:
                        break
                except Exception:
                    continue
            if not success:
                error_toast = ""
                for selector in [".el-message--error", ".el-message.error",
                                 ".el-notification--error", ".el-notification.error",
                                 ".el-message", ".el-notification"]:
                    try:
                        for elem in driver.find_elements(By.CSS_SELECTOR, selector):
                            if elem.is_displayed() and elem.text:
                                error_toast = elem.text
                                break
                        if error_toast:
                            break
                    except Exception:
                        continue
                if error_toast:
                    raise Exception(f"密码修改失败: {error_toast}")
            if success:
                ctx.log(f"密码修改成功: {toast_message}")
            else:
                ctx.log("未检测到吐司提示，假设修改成功")
        except Exception as e:
            if "密码修改失败" in str(e):
                raise
            ctx.log(f"检测吐司提示时出错: {str(e)}")

        # 修改后可能出现与登录时相同的重置密码弹窗
        try:
            wait = WebDriverWait(driver, 3)
            for dialog in driver.find_elements(
                By.CSS_SELECTOR,
                ".el-dialog.el-dialog--center.public-dialog-center.modify-password-dialog",
            ):
                try:
                    if dialog.is_displayed():
                        handle_password_reset(ctx, driver, wait)
                        time.sleep(1)
                        break
                except Exception:
                    continue
        except Exception:
            pass

        # 关闭新标签页，切回原窗口
        driver.close()
        driver.switch_to.window(original_window)
        ctx.log("账号设置中密码修改完成")
        return True
    except Exception as e:
        ctx.log(f"在账号设置中修改密码时出错: {str(e)}")
        try:
            windows = driver.window_handles
            original_window = driver.current_window_handle
            if len(windows) > 1:
                for window in windows:
                    if window != original_window:
                        try:
                            driver.switch_to.window(window)
                            driver.close()
                        except Exception:
                            pass
                try:
                    driver.switch_to.window(original_window)
                except Exception:
                    if driver.window_handles:
                        driver.switch_to.window(driver.window_handles[0])
        except Exception:
            pass
        return False


def logout(ctx, driver, wait) -> bool:
    """退出登录：关闭多余窗口、清除cookies、回首页"""
    try:
        window_handles = driver.window_handles
        if len(window_handles) > 1:
            original_window = window_handles[0]
            for i in range(1, len(window_handles)):
                try:
                    driver.switch_to.window(window_handles[i])
                    driver.close()
                except Exception:
                    pass
            if original_window:
                driver.switch_to.window(original_window)

        time.sleep(0.5)
        driver.delete_all_cookies()
        driver.get(ctx.config.target_url)
        time.sleep(1)
        ctx.log("通过清除cookies退出登录")
        return True
    except Exception as e:
        ctx.log(f"退出登录失败: {str(e)}")
        return False
