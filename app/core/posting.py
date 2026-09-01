"""发帖服务：导航到芯泉子发帖页、真人化输入、图片上传、发布结果检测"""
from __future__ import annotations

import random
import re
import time

from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from app.core import content as content_service
from app.utils.humanize import human_pause, wait_random_time


def click_element_by_text(ctx, driver, text: str, element_type: str = "*", wait_time: float = 5):
    """通过文本点击元素。返回 (是否成功, 错误消息)"""
    try:
        wait = WebDriverWait(driver, wait_time)
        xpath_expressions = [
            f"//{element_type}[contains(text(), '{text}')]",
            f"//{element_type}[normalize-space(text())='{text}']",
            f"//{element_type}[contains(normalize-space(text()), '{text}')]",
        ]

        element = None
        for xpath in xpath_expressions:
            try:
                element = wait.until(EC.presence_of_element_located((By.XPATH, xpath)))
                if element and element.is_displayed():
                    break
            except Exception:
                continue

        if not element:
            for xpath in xpath_expressions:
                try:
                    for elem in driver.find_elements(By.XPATH, xpath):
                        if elem.is_displayed() and elem.is_enabled():
                            element = elem
                            break
                    if element:
                        break
                except Exception:
                    continue

        if not element:
            return False, f"未找到可点击的'{text}'元素"

        try:
            driver.execute_script(
                "arguments[0].scrollIntoView({block: 'center', behavior: 'smooth'});", element
            )
            time.sleep(0.2)
        except Exception:
            pass

        # 方法1: JS点击
        try:
            driver.execute_script("arguments[0].click();", element)
            return True, ""
        except Exception as e:
            error_msg = f"JavaScript点击失败: {str(e)}"

        # 方法2: 普通点击
        try:
            if element.is_displayed() and element.is_enabled():
                element.click()
                return True, ""
        except Exception as e:
            error_msg = f"普通点击失败: {str(e)}"

        # 方法3: ActionChains
        try:
            ActionChains(driver).move_to_element(element).click().perform()
            return True, ""
        except Exception as e:
            error_msg = f"ActionChains点击失败: {str(e)}"

        return False, error_msg
    except Exception as e:
        return False, f"查找'{text}'元素时出错: {str(e)}"


def navigate_to_post_page(ctx, driver, wait):
    """通过点击方式导航到发帖页面。返回 (是否成功, 状态码或None, 消息)

    状态码: 7=未找到发布按钮 8=无法点击'开始对话' 9=无法点击'芯泉子'
    """
    ctx.log("通过点击方式导航到发帖页面...")
    original_window = driver.current_window_handle

    try:
        wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), '开始对话')]")))
        time.sleep(0.3)
    except Exception as e:
        ctx.log(f"等待'开始对话'按钮出现时出错: {str(e)}，继续尝试点击...")

    # 1. 点击"开始对话"
    start_result, start_error = click_element_by_text(ctx, driver, "开始对话", wait_time=10)
    if not start_result:
        return False, 8, f"无法点击'开始对话': {start_error}"
    time.sleep(0.5)

    # 2. 点击"芯泉子"
    circle_result, circle_error = click_element_by_text(ctx, driver, "芯泉子")
    if not circle_result:
        return False, 9, f"无法点击'芯泉子': {circle_error}"
    time.sleep(1)

    # 3. 处理新窗口
    window_handles = driver.window_handles
    if len(window_handles) > 1:
        for window_handle in window_handles:
            if window_handle != original_window:
                driver.switch_to.window(window_handle)
                ctx.log(f"切换到新窗口: {window_handle}")
                break

    # 4. 验证发帖页面
    try:
        publish_selectors = [
            "button.el-button.el-button--default.publish-btn",
            ".el-button.el-button--default.publish-btn",
            ".publish-btn",
        ]
        for selector in publish_selectors:
            try:
                for element in driver.find_elements(By.CSS_SELECTOR, selector):
                    if element.is_displayed():
                        ctx.log("成功进入发帖页面")
                        return True, None, "成功进入发帖页面"
            except Exception:
                continue
        return False, 7, "未找到发布按钮"
    except Exception as e:
        return False, 7, f"检查发帖页面失败: {str(e)}"


def human_input_title(driver, title_text: str) -> None:
    """真人标题输入（Element Plus 专杀）"""
    title_input = driver.find_element(By.XPATH, "//input[contains(@placeholder,'标题')]")

    title_input.click()
    human_pause(0.2, 0.4)

    title_input.send_keys(Keys.ARROW_RIGHT)
    human_pause(0.1, 0.2)

    title_input.send_keys(Keys.CONTROL, "a")
    human_pause(0.1, 0.2)
    title_input.send_keys(Keys.BACKSPACE)
    human_pause(0.2, 0.3)

    for ch in title_text:
        title_input.send_keys(ch)
        time.sleep(random.uniform(0.05, 0.12))
        if random.random() < 0.15:
            human_pause(0.2, 0.6)

    # Element Plus / 中文输入关键事件
    driver.execute_script("""
        const el = arguments[0];
        el.dispatchEvent(new Event('compositionstart', { bubbles: true }));
        el.dispatchEvent(new Event('compositionend', { bubbles: true }));
        el.dispatchEvent(new Event('input', { bubbles: true }));
        el.dispatchEvent(new Event('change', { bubbles: true }));
    """, title_input)

    driver.find_element(By.CSS_SELECTOR, ".el-dialog__header").click()
    human_pause(0.4, 0.7)


def human_input_editor(driver, text: str) -> None:
    """真人正文输入（contenteditable）"""
    editor = driver.find_element(By.CSS_SELECTOR, ".my-editor")

    editor.click()
    human_pause(0.3, 0.6)

    for ch in text:
        editor.send_keys(ch)
        time.sleep(random.uniform(0.02, 0.08))
        if random.random() < 0.1:
            human_pause(0.1, 0.4)

    if random.random() < 0.3:
        editor.send_keys(Keys.ARROW_LEFT)
        editor.send_keys(Keys.ARROW_RIGHT)

    human_pause(0.3, 0.6)
    driver.find_element(By.CSS_SELECTOR, ".el-dialog__header").click()
    human_pause(0.4, 0.7)


def human_click_publish(driver) -> None:
    """真人点击发布（只点"活按钮"）"""
    buttons = driver.find_elements(By.CSS_SELECTOR, "button.publish-btn")
    buttons = [b for b in buttons if b.is_displayed() and b.is_enabled()]
    if not buttons:
        raise Exception("未找到可用的发布按钮")

    btn = buttons[-1]
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
    human_pause(0.3, 0.7)

    driver.execute_script("""
        arguments[0].dispatchEvent(new MouseEvent('mouseover', {bubbles:true}));
        arguments[0].dispatchEvent(new MouseEvent('mousedown', {bubbles:true}));
    """, btn)
    human_pause(0.1, 0.2)
    driver.execute_script("""
        arguments[0].dispatchEvent(new MouseEvent('mouseup', {bubbles:true}));
        arguments[0].dispatchEvent(new MouseEvent('click', {bubbles:true}));
    """, btn)
    human_pause(0.8, 1.2)


def _upload_post_image(ctx, driver) -> None:
    """在打开发帖弹窗后上传一张随机图片（带随机裁切）"""
    ctx.log("在弹窗中上传图片...")

    img_path = content_service.pick_random_image(ctx.config.effective_img_dir)
    if not img_path:
        ctx.log(f"在 {ctx.config.effective_img_dir} 中未找到图片文件")
        return
    ctx.log(f"随机选择图片: {img_path}")

    temp_upload_dir = ctx.config.temp_upload_dir
    content_service.clean_temp_upload_dir(temp_upload_dir, log=lambda m: ctx.log(m))
    temp_img_path = content_service.prepare_temp_upload_file(
        img_path, temp_upload_dir, log=lambda m: ctx.log(m)
    )

    # 查找"添加图片"元素与文件输入框
    add_img_elements = driver.find_elements(By.XPATH, "//*[contains(text(), '添加图片')]")
    file_input = None
    for add_img_element in add_img_elements:
        if add_img_element.is_displayed():
            parent = add_img_element
            for _ in range(5):
                try:
                    parent = parent.find_element(By.XPATH, "..")
                    file_inputs = parent.find_elements(By.CSS_SELECTOR, "input[type='file']")
                    if file_inputs:
                        file_input = file_inputs[0]
                        break
                except Exception:
                    continue
            if file_input:
                break

    if not file_input:
        for inp in driver.find_elements(By.CSS_SELECTOR, "input[type='file']"):
            try:
                if inp.is_displayed():
                    file_input = inp
                    break
            except Exception:
                continue

    if not file_input:
        ctx.log("未找到可用的文件上传输入框")
        return

    # 点击"添加图片"区域后发送文件路径
    for add_img_element in add_img_elements:
        if add_img_element.is_displayed():
            try:
                driver.execute_script("arguments[0].click();", add_img_element)
                wait_random_time(0.5)
                break
            except Exception:
                pass

    try:
        file_input.send_keys(temp_img_path)
        ctx.log(f"已发送临时图片路径到上传输入框: {temp_img_path}")
    except Exception as e:
        ctx.log(f"图片上传失败: {str(e)}")
        return

    time.sleep(0.5)

    # 等待图片加载完成
    img_loaded = False
    selected_img = img_path.split("\\")[-1].split("/")[-1]
    for _ in range(5):
        time.sleep(0.5)
        try:
            for img in driver.find_elements(By.CSS_SELECTOR, "img"):
                src = img.get_attribute("src") or ""
                alt = img.get_attribute("alt") or ""
                if "upload" in src.lower() or "base64" in src.lower() or selected_img in src or selected_img in alt:
                    img_loaded = True
                    break
            if img_loaded:
                break
        except Exception:
            pass

    if img_loaded:
        time.sleep(0.5)
        ctx.log("图片已确认上传完成")
    else:
        ctx.log("警告: 图片可能未完全上传，但继续执行")


def _handle_topic_popup(ctx, driver, content_text: str) -> None:
    """检查并处理话题选择弹窗"""
    try:
        time.sleep(0.3)
        topic_popup_selectors = [
            ".topic-popover", ".el-popover", ".el-autocomplete-suggestion",
            "[class*='popover']", "[class*='autocomplete']",
        ]
        popup_handled = False
        for selector in topic_popup_selectors:
            try:
                for popup in driver.find_elements(By.CSS_SELECTOR, selector):
                    try:
                        if not popup.is_displayed():
                            continue
                        hashtags = re.findall(r"#\S+", content_text)
                        if not hashtags:
                            break
                        target_hashtag = hashtags[-1]
                        try:
                            for item in popup.find_elements(By.CSS_SELECTOR, ".topic-item"):
                                try:
                                    if item.is_displayed():
                                        item_text = item.text.strip()
                                        if target_hashtag in item_text or item_text == target_hashtag:
                                            driver.execute_script("arguments[0].click();", item)
                                            time.sleep(0.2)
                                            popup_handled = True
                                            ctx.log(f"已点击话题选项: {item_text}")
                                            break
                                except Exception:
                                    continue
                            if not popup_handled:
                                for elem in popup.find_elements(
                                    By.XPATH, f".//*[contains(text(), '{target_hashtag}')]"
                                ):
                                    try:
                                        if elem.is_displayed():
                                            driver.execute_script("arguments[0].click();", elem)
                                            time.sleep(0.2)
                                            popup_handled = True
                                            break
                                    except Exception:
                                        continue
                        except Exception as e:
                            ctx.log(f"查找话题选项时出错: {str(e)}")
                        if popup_handled:
                            break
                    except Exception:
                        continue
                if popup_handled:
                    break
            except Exception:
                continue
        if popup_handled:
            time.sleep(0.2)
    except Exception as e:
        ctx.log(f"检查话题弹窗时出错: {str(e)}")


def _detect_publish_result(ctx, driver):
    """轮询检测发布结果。返回 (是否成功, 消息)。特殊消息 "网络超时" 触发重新登录。"""
    try:
        for check_round in range(5):
            if check_round > 0:
                time.sleep(0.2)

            # 1. 成功吐司
            for selector in [".el-message--success", ".el-message.success",
                             ".el-notification--success", ".el-notification.success"]:
                try:
                    for element in driver.find_elements(By.CSS_SELECTOR, selector):
                        if element.is_displayed():
                            text = element.text.strip()
                            if text and ("成功" in text or "success" in text.lower()):
                                return True, "发布成功"
                except Exception:
                    continue

            try:
                for element in driver.find_elements(By.CSS_SELECTOR, ".el-message"):
                    if element.is_displayed():
                        text = element.text.strip()
                        if text and "成功" in text and "失败" not in text:
                            return True, "发布成功"
            except Exception:
                pass

            # 2. 错误吐司（优先检测网络超时）
            error_found = False
            error_message = ""
            network_timeout_found = False

            for selector in [".el-message--error", ".el-message.error",
                             ".el-notification--error", ".el-notification.error",
                             ".error-message", "[class*='error']"]:
                try:
                    for element in driver.find_elements(By.CSS_SELECTOR, selector):
                        if element.is_displayed():
                            text = element.text.strip()
                            if text:
                                if "网络超时" in text:
                                    network_timeout_found = True
                                    error_found = True
                                    error_message = text
                                    break
                                elif "失败" in text or "错误" in text or "error" in text.lower():
                                    error_found = True
                                    error_message = text
                                    break
                    if error_found:
                        break
                except Exception:
                    continue

            if not error_found:
                try:
                    for error in driver.find_elements(By.XPATH, "//*[contains(text(), '网络超时')]"):
                        if error.is_displayed() and "网络超时" in error.text:
                            network_timeout_found = True
                            error_found = True
                            error_message = error.text.strip()
                            break
                except Exception:
                    pass

            if not error_found:
                for keyword in ["失败", "错误", "无法", "不能", "禁止", "锁定"]:
                    try:
                        for error in driver.find_elements(By.XPATH, f"//*[contains(text(), '{keyword}')]"):
                            if error.is_displayed():
                                full_text = error.text.strip()
                                if keyword in full_text and full_text:
                                    if "成功" not in full_text and "success" not in full_text.lower():
                                        error_found = True
                                        error_message = full_text
                                        break
                        if error_found:
                            break
                    except Exception:
                        continue

            if error_found:
                if network_timeout_found:
                    return False, "网络超时"
                return False, error_message

            # 3. 检查"发布成功"文本 / 弹窗关闭
            success_found = False
            try:
                for element in driver.find_elements(
                    By.CSS_SELECTOR, ".el-message--success, .el-message.success, .el-notification--success"
                ):
                    if element.is_displayed():
                        text = element.text.strip()
                        if text and ("成功" in text or "success" in text.lower()):
                            success_found = True
                            break
            except Exception:
                pass

            if not success_found:
                try:
                    for element in driver.find_elements(
                        By.XPATH, "//*[contains(text(), '发布成功') or contains(text(), '成功')]"
                    ):
                        if element.is_displayed():
                            text = element.text.strip()
                            if text and ("发布成功" in text or ("成功" in text and "失败" not in text)):
                                success_found = True
                                break
                except Exception:
                    pass

            if not success_found:
                try:
                    dialog_still_open = False
                    for element in driver.find_elements(By.XPATH, "//*[contains(text(), '发布动态')]"):
                        if element.is_displayed():
                            dialog_still_open = True
                            break
                    if not dialog_still_open:
                        success_found = True
                except Exception:
                    pass

            if success_found:
                return True, "发布成功"

        # 最后兜底：弹窗是否消失
        try:
            dialog_still_open = False
            for element in driver.find_elements(By.XPATH, "//*[contains(text(), '发布动态')]"):
                if element.is_displayed():
                    dialog_still_open = True
                    break
            if not dialog_still_open:
                return True, "弹窗已关闭，可能发布成功"
        except Exception:
            pass

        return True, "未检测到明确的发布结果，但已尝试发布"
    except Exception as e:
        return False, f"检查发布结果时出错: {str(e)}"


def create_post(ctx, driver, wait, student_id: str):
    """创建帖子。返回 (是否成功, 消息)。特殊消息 "网络超时" 触发重新登录流程。"""
    ctx.log("开始创建帖子...")

    # 1. 点击发布按钮打开"发布动态"弹窗
    try:
        publish_btn = None
        for selector in ["button.el-button.el-button--default.publish-btn",
                         ".el-button.el-button--default.publish-btn", ".publish-btn"]:
            try:
                for element in driver.find_elements(By.CSS_SELECTOR, selector):
                    if element.is_displayed() and element.is_enabled():
                        inner_html = element.get_attribute("innerHTML") or ""
                        if "发布" in inner_html or "发布" in element.text:
                            publish_btn = element
                            break
                if publish_btn:
                    break
            except Exception:
                continue

        if not publish_btn:
            for element in driver.find_elements(By.XPATH, "//button[.//span[contains(text(), '发布')]]"):
                if element.is_displayed() and element.is_enabled():
                    publish_btn = element
                    break

        if not publish_btn:
            return False, "未找到发布按钮"

        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", publish_btn)
        wait_random_time(0.5)
        driver.execute_script("arguments[0].click();", publish_btn)
        ctx.log("已点击发布按钮打开'发布动态'弹窗")
        time.sleep(0.5)
    except Exception as e:
        return False, f"打开弹窗过程中出现错误: {str(e)}"

    # 2. 等待弹窗加载
    try:
        dialog_title_found = False
        for i in range(3):
            for element in driver.find_elements(By.XPATH, "//*[contains(text(), '发布动态')]"):
                if element.is_displayed():
                    dialog_title_found = True
                    break
            if dialog_title_found:
                break
            if i < 2:
                time.sleep(0.2)
        time.sleep(0.3)
    except Exception as e:
        ctx.log(f"等待弹窗时出错: {str(e)}")

    # 3. 上传图片
    try:
        _upload_post_image(ctx, driver)
    except Exception as e:
        ctx.log(f"上传图片时出错: {str(e)}")

    # 4. 输入标题
    try:
        title_text = content_service.random_title()
        ctx.log(f"输入标题: {title_text}")
        human_input_title(driver, title_text)
    except Exception as e:
        ctx.log(f"输入标题失败: {str(e)}")

    # 5. 输入正文
    try:
        content_text = content_service.generate_single_post_content()
        ctx.log(f"输入正文（{len(content_text)}字）")
        human_input_editor(driver, content_text)
        _handle_topic_popup(ctx, driver, content_text)
    except Exception as e:
        ctx.log(f"输入正文失败: {str(e)}")

    # 6. 点击发布
    try:
        human_click_publish(driver)
        ctx.log("已点击发布按钮")
    except Exception as e:
        return False, f"点击发布按钮时出错: {str(e)}"

    # 7. 检测发布结果
    return _detect_publish_result(ctx, driver)
