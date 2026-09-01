"""核心层冒烟测试（无 GUI 依赖）。

用法: .venv\\Scripts\\python tests\\smoke_core.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core import content, excel_service, location_service  # noqa: E402
from app.core.config import AppConfig, load_config, save_config  # noqa: E402
from app.core.models import RunMode  # noqa: E402
from app.core.proxy_service import build_requests_proxies, extract_ip_from_proxy  # noqa: E402
from app.services.driver_manager import DriverManager  # noqa: E402
from app.utils import paths  # noqa: E402


def main() -> int:
    # Excel 读取（模板）
    template = paths.resource_path("assets", "templates", "Autouer_模板.xlsx")
    wb, ws, records, headers = excel_service.read_student_data(template)
    assert records and records[0].student_id
    wb.close()
    print("[OK] Excel 模板读取")

    # 备注构建（双模式）
    r = excel_service.build_remark(RunMode.POST, 2, True, "", "A123456a", "1.2.3.4", "北京", "A123456a")
    assert r.startswith("2.发帖成功-已重置[A123456a]-北京-1.2.3.4"), r
    r = excel_service.build_remark(RunMode.ACTIVATE, 1, True, "", "A123456a")
    assert r.startswith("1.激活成功-密码重置成功[A123456a]-"), r
    print("[OK] 备注构建（发帖/激活）")

    # 内容生成与图片处理
    assert "#校友集结号" in content.generate_single_post_content()
    img = content.pick_random_image(paths.resource_path("assets", "img"))
    assert img, "内置图片库为空"
    tmp = content.prepare_temp_upload_file(img, paths.user_data_path("temp_upload_test"))
    assert os.path.exists(tmp)
    content.clean_temp_upload_dir(paths.user_data_path("temp_upload_test"))
    print("[OK] 帖子内容生成 + 图片裁切")

    # 代理解析
    assert extract_ip_from_proxy("1.2.3.4:8080") == "1.2.3.4"
    assert extract_ip_from_proxy("socks5://5.6.7.8:1080") == "5.6.7.8"
    assert build_requests_proxies("1.2.3.4:8080:u:p")["http"] == "http://u:p@1.2.3.4:8080"
    print("[OK] 代理解析")

    # 虚拟定位
    loc = location_service.get_random_location()
    assert 18 < loc["latitude"] < 54 and loc["city_name"]
    print(f"[OK] 虚拟定位（{loc['city_name']}）")

    # 配置持久化
    cfg = AppConfig()
    original = cfg.excel_path
    cfg.excel_path = r"C:\__smoke_test__.xlsx"
    save_config(cfg)
    assert load_config().excel_path == cfg.excel_path
    cfg.excel_path = original
    save_config(cfg)
    print("[OK] 配置持久化")

    # 驱动管理（在线，可能耗时）
    mgr = DriverManager()
    edge = mgr.get_installed_edge_version()
    assert edge, "未检测到 Edge 浏览器"
    driver = mgr.ensure_driver()
    print(f"[OK] 驱动管理: Edge {edge}, driver={driver or 'Selenium Manager 兜底'}")

    print("\n===== smoke_core 全部通过 =====")
    return 0


if __name__ == "__main__":
    sys.exit(main())
